"""Reproduce the LA County tract-level rent comparison from saved Census inputs.

Run with the project environment: python code/analyze.py
The script resolves its own directory; it makes no network requests.
"""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import numpy as np
import pandas as pd
import pyproj
import shapely
from matplotlib.patches import Patch, Rectangle
from shapely.geometry import box


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results"
OUT.mkdir(parents=True, exist_ok=True)
PERIOD = "2020–2024 ACS 5-year estimates"
MIN_HOUSEHOLDS = 100
PROJECTED_CRS = "EPSG:3310"
BAND_LABELS = ["Under $1,500", "$1,500–1,999", "$2,000–2,499", "$2,500 or more"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False})


def load_acs(filename: str) -> pd.DataFrame:
    raw = json.loads((RAW / filename).read_text(encoding="utf-8-sig"))
    assert isinstance(raw, list) and len(raw) > 1, f"Invalid ACS input: {filename}"
    frame = pd.DataFrame(raw[1:], columns=raw[0])
    assert not frame.columns.duplicated().any()
    for name in frame.columns:
        if name.endswith(("E", "M")) and name.startswith("B"):
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
            if name.endswith("M"):
                frame.loc[frame[name] == -555555555, name] = 0
            frame.loc[frame[name] < 0, name] = np.nan
    return frame


def rss(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    values = frame[columns]
    return np.sqrt(values.pow(2).sum(axis=1, min_count=len(columns)))


def derived_share_moe(numerator, denominator, numerator_moe, denominator_moe):
    """Census subset-proportion approximation; ratio fallback if radicand < 0.

    The inputs and output are 90% margins of error. Multiplication by 100
    converts a proportion MOE to percentage points. Covariances are unavailable.
    """
    p = np.asarray(numerator) / np.asarray(denominator)
    a = np.asarray(numerator_moe) ** 2
    b = p**2 * np.asarray(denominator_moe) ** 2
    return 100 * np.sqrt(np.where(a - b >= 0, a - b, a + b)) / np.asarray(denominator)


def derive(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    component_cols = [f"B25070_{i:03d}E" for i in range(2, 12)]
    complete = frame[component_cols + ["B25070_001E"]].notna().all(axis=1)
    discrepancy = frame.loc[complete, component_cols].sum(axis=1) - frame.loc[complete, "B25070_001E"]
    assert discrepancy.abs().le(1).all(), "Rent-income components do not reconcile"
    frame["renters_total"] = frame["B25070_001E"]
    frame["not_computed"] = frame["B25070_011E"]
    frame["eligible_renters"] = frame["renters_total"] - frame["not_computed"]
    frame["burdened_renters"] = frame[[f"B25070_{i:03d}E" for i in range(7, 11)]].sum(axis=1, min_count=4)
    frame["severely_burdened_renters"] = frame["B25070_010E"]
    frame["eligible_moe"] = rss(frame, ["B25070_001M", "B25070_011M"])
    frame["burdened_moe"] = rss(frame, [f"B25070_{i:03d}M" for i in range(7, 11)])
    frame["severely_burdened_moe"] = frame["B25070_010M"]
    valid_denominator = frame["eligible_renters"] > 0
    frame["burden_pct"] = np.where(valid_denominator, 100 * frame["burdened_renters"] / frame["eligible_renters"], np.nan)
    frame["severe_pct"] = np.where(valid_denominator, 100 * frame["severely_burdened_renters"] / frame["eligible_renters"], np.nan)
    for prefix, count, moe in [("burden", "burdened_renters", "burdened_moe"), ("severe", "severely_burdened_renters", "severely_burdened_moe")]:
        with np.errstate(divide="ignore", invalid="ignore"):
            frame[f"{prefix}_moe_pp"] = derived_share_moe(frame[count], frame["eligible_renters"], frame[moe], frame["eligible_moe"])
        frame.loc[~valid_denominator, f"{prefix}_moe_pp"] = np.nan
    frame["median_gross_rent"] = frame["B25064_001E"]
    annotation = frame.get("B25064_001EA", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["rent_upper_censored"] = annotation.str.contains("+", regex=False) | frame["median_gross_rent"].eq(3501)
    frame["rent_plot_value"] = frame["median_gross_rent"].where(~frame["rent_upper_censored"], 3500)
    frame["rent_band"] = pd.cut(frame["rent_plot_value"], [0, 1500, 2000, 2500, np.inf], labels=BAND_LABELS, right=False)
    valid = frame[["burden_pct", "severe_pct"]].notna().all(axis=1)
    assert frame.loc[valid, "severe_pct"].le(frame.loc[valid, "burden_pct"] + 1e-8).all()
    assert frame.loc[valid, ["burden_pct", "severe_pct"]].ge(0).all().all()
    assert frame.loc[valid, ["burden_pct", "severe_pct"]].le(100 + 1e-8).all().all()
    frame["included"] = (frame["eligible_renters"] >= MIN_HOUSEHOLDS) & frame["median_gross_rent"].gt(0) & valid
    frame["exclusion_reason"] = ""
    frame.loc[frame["eligible_renters"].lt(MIN_HOUSEHOLDS) | frame["eligible_renters"].isna(), "exclusion_reason"] = "Fewer than 100 estimated renters with computable ratio"
    frame.loc[~frame["median_gross_rent"].gt(0), "exclusion_reason"] += "; Median gross rent unavailable"
    frame.loc[~valid, "exclusion_reason"] += "; Rent-income counts unavailable"
    frame["exclusion_reason"] = frame["exclusion_reason"].str.strip("; ")
    return frame


def summarize_bands(frame: pd.DataFrame, threshold: int) -> pd.DataFrame:
    selected = frame.loc[frame["eligible_renters"].ge(threshold) & frame["median_gross_rent"].gt(0) & frame["burden_pct"].notna()].copy()
    output = []
    for band in BAND_LABELS:
        group = selected.loc[selected["rent_band"] == band]
        n = float(group["eligible_renters"].sum())
        burdened = float(group["burdened_renters"].sum())
        severe = float(group["severely_burdened_renters"].sum())
        if n == 0:
            continue
        dm = float(np.sqrt(group["eligible_moe"].pow(2).sum()))
        bm = float(np.sqrt(group["burdened_moe"].pow(2).sum()))
        sm = float(np.sqrt(group["severely_burdened_moe"].pow(2).sum()))
        output.append({"rent_band": band, "tracts": len(group), "eligible_renters": n, "burdened_renters": burdened, "severely_burdened_renters": severe, "burden_pct": 100 * burdened / n, "severe_pct": 100 * severe / n, "burden_moe_pp": float(derived_share_moe(burdened, n, bm, dm)), "severe_moe_pp": float(derived_share_moe(severe, n, sm, dm))})
    result = pd.DataFrame(output)
    assert int(result["tracts"].sum()) == len(selected)
    assert np.isclose(result["eligible_renters"].sum(), selected["eligible_renters"].sum())
    return result


def map_figure(geo: gpd.GeoDataFrame, metric: str, path: str):
    rent = metric == "rent_plot_value"
    bins = [0, 1500, 2000, 2500, 3000, np.inf] if rent else [0, 40, 50, 60, 70, np.inf]
    labels = ["Under $1,500", "$1,500–1,999", "$2,000–2,499", "$2,500–2,999", "$3,000 or more"] if rent else ["Under 40%", "40–49.9%", "50–59.9%", "60–69.9%", "70% or more"]
    colors = ["#e2f0ee", "#b8d8d3", "#7db6ac", "#418f83", "#126255"] if rent else ["#fff0dc", "#f6d0a2", "#e9a86a", "#cc743d", "#91451f"]
    categories = pd.cut(geo[metric], bins, labels=False, right=False)
    plot_colors = [colors[int(c)] if included and pd.notna(c) else "#dedede" for c, included in zip(categories, geo["included"])]
    fig = plt.figure(figsize=(12, 8.5), facecolor="white")
    ax = fig.add_axes([0.035, 0.13, 0.70, 0.74])
    inset = fig.add_axes([0.765, 0.53, 0.22, 0.34])
    fig.text(0.04, 0.95, "Monthly rents are not the same as rent pressure" if rent else "Where rent takes a larger share of income", fontsize=17, weight="bold", color="#243746")
    subtitle = "Median monthly gross rent · 2024 dollars" if rent else "Renters spending at least 30% of household income on gross rent"
    fig.text(0.04, 0.908, f"Los Angeles County · {subtitle}", fontsize=11, color="#52616b")
    zoom = gpd.GeoSeries([box(-118.78, 33.68, -117.66, 34.40)], crs="EPSG:4326").to_crs(PROJECTED_CRS).total_bounds
    geo.plot(ax=ax, color=plot_colors, linewidth=0.12, edgecolor="white")
    ax.set_xlim(zoom[0], zoom[2])
    ax.set_ylim(zoom[1], zoom[3])
    ax.set_axis_off()
    ax.set_title("Urban-area detail", fontsize=10, loc="left", pad=4, color="#52616b")
    geo.plot(ax=inset, color=plot_colors, linewidth=0, edgecolor="none")
    inset.add_patch(Rectangle((zoom[0], zoom[1]), zoom[2] - zoom[0], zoom[3] - zoom[1], fill=False, lw=1.0, edgecolor="#283e4a"))
    inset.set_axis_off()
    inset.set_title("Full county", fontsize=11, loc="left", pad=4)
    places = [("Santa Monica", -118.4912, 34.0195, -55, -13), ("Downtown LA", -118.2437, 34.0522, 6, 5), ("Pasadena", -118.1445, 34.1478, 6, 5), ("Long Beach", -118.1937, 33.7701, 6, 4), ("San Fernando", -118.43897, 34.2819, 6, 5)]
    tx = pyproj.Transformer.from_crs("EPSG:4326", PROJECTED_CRS, always_xy=True)
    for name, lon, lat, dx, dy in places:
        x, y = tx.transform(lon, lat)
        ax.scatter([x], [y], s=10, c="#243746", edgecolors="white", linewidths=0.5, zorder=4)
        text = ax.annotate(name, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=9, color="#172e3a", weight="normal", zorder=5)
        text.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground="white", alpha=0.9)])
    handles = [Patch(facecolor=color, edgecolor="none", label=label) for color, label in zip(colors, labels)]
    handles.append(Patch(facecolor="#dedede", label="Unavailable / below cutoff"))
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.755, 0.18), frameon=False, fontsize=10, labelspacing=0.8, title="Gross rent per month" if rent else "Share of eligible renters", title_fontsize=10)
    fig.text(0.04, 0.075, f"{PERIOD}. Tracts with at least 100 estimated renter households with a computable rent–income ratio.", fontsize=9, color="#52616b")
    fig.text(0.04, 0.045, "Sources: U.S. Census Bureau, ACS B25064/B25070 and 2024 cartographic boundaries. California Albers projection.", fontsize=9, color="#52616b")
    fig.savefig(OUT / path, dpi=150, facecolor="white")
    plt.close(fig)


def band_figure(bands: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 6.3), facecolor="white")
    y = np.arange(len(bands))
    for shift, metric, color, label in [(-0.18, "burden", "#216b6b", "At least 30% of income"), (0.18, "severe", "#b15d2a", "At least 50% of income")]:
        values = bands[f"{metric}_pct"].to_numpy()
        errors = bands[f"{metric}_moe_pp"].to_numpy()
        ax.barh(y + shift, values, height=0.30, color=color, label=label)
        ax.errorbar(values, y + shift, xerr=np.vstack([np.minimum(values, errors), np.minimum(100-values, errors)]), fmt="none", ecolor="#273e49", elinewidth=1.0, capsize=3)
        for i, value in enumerate(values):
            ax.text(value + errors[i] + 1.1, y[i] + shift, f"{value:.1f}%", va="center", fontsize=11, color="#243746")
    ax.set_yticks(y, bands["rent_band"])
    ax.invert_yaxis()
    ax.set_xlim(0, min(100, max(bands["burden_pct"] + bands["burden_moe_pp"]) + 13))
    ax.set_xlabel("Share of renter households with a computable rent–income ratio (%)")
    ax.set_ylabel("Tract median monthly gross rent")
    ax.grid(axis="x", color="#e4e9eb", lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, fontsize=10)
    fig.suptitle("Compare burdens across rent levels", x=0.08, y=0.96, ha="left", fontsize=17, weight="bold", color="#243746")
    fig.text(0.08, 0.905, f"Los Angeles County · {PERIOD}", fontsize=11, color="#52616b")
    fig.subplots_adjust(left=0.20, right=0.94, bottom=0.22, top=0.85)
    fig.text(0.08, 0.08, "Rates pool household counts within fixed rent bands; they are not averages of tract percentages.", fontsize=9, color="#52616b")
    fig.text(0.08, 0.04, "Whiskers: approximate 90% margins of error. Same 100-household cutoff as maps. Source: Census ACS B25064/B25070.", fontsize=9, color="#52616b")
    fig.savefig(OUT / "rent-bands.png", dpi=150, facecolor="white")
    plt.close(fig)


def main():
    tracts = derive(load_acs("acs_tracts.json"))
    tracts["GEOID"] = tracts["state"] + tracts["county"] + tracts["tract"]
    assert tracts["GEOID"].str.len().eq(11).all()
    assert tracts["GEOID"].is_unique
    county = derive(load_acs("acs_county.json"))
    assert len(county) == 1
    boundaries = gpd.read_file(RAW / "la_tracts.geojson", engine="pyogrio")
    assert boundaries.crs is not None
    assert boundaries["GEOID"].is_unique
    assert boundaries.geometry.notna().all() and not boundaries.geometry.is_empty.any()
    assert boundaries.geometry.is_valid.all(), "Invalid source geometry; inspect before repair"
    missing_geometry = sorted(set(tracts["GEOID"]) - set(boundaries["GEOID"]))
    missing_acs = sorted(set(boundaries["GEOID"]) - set(tracts["GEOID"]))
    assert not missing_acs, f"Boundary features without ACS data: {missing_acs}"
    no_geometry = tracts.loc[tracts["GEOID"].isin(missing_geometry)]
    # Cartographic boundary layers omit some water-only statistical tracts.
    # Permit omissions only after proving that no renter estimate is lost.
    assert no_geometry["renters_total"].eq(0).all() and not no_geometry["included"].any(), f"Populated renter areas without geometry: {missing_geometry}"
    geo = boundaries[["GEOID", "geometry"]].merge(tracts, on="GEOID", validate="one_to_one").to_crs(PROJECTED_CRS)
    assert geo.geometry.is_valid.all() and len(geo) == len(boundaries)
    bands = summarize_bands(tracts, MIN_HOUSEHOLDS)
    bands50 = summarize_bands(tracts, 50)
    tracts.to_csv(OUT / "tract_results.csv", index=False)
    bands.to_csv(OUT / "rent_bands.csv", index=False)
    bands50.to_csv(OUT / "sensitivity_50.csv", index=False)
    map_figure(geo, "rent_plot_value", "rent-map.png")
    map_figure(geo, "burden_pct", "burden-map.png")
    band_figure(bands)
    selected = tracts.loc[tracts["included"]]
    c = county.iloc[0]
    summary = {"period": "2020–2024", "scope": "Los Angeles County census tracts", "tracts_total": len(tracts), "tracts_included": len(selected), "tracts_excluded": len(tracts)-len(selected), "rent_topcoded_tracts_included": int(selected["rent_upper_censored"].sum()), "county": {name: float(c[name]) for name in ["median_gross_rent", "renters_total", "not_computed", "eligible_renters", "burdened_renters", "severely_burdened_renters", "burden_pct", "severe_pct", "burden_moe_pp", "severe_moe_pp"]}, "included_renters": float(selected["eligible_renters"].sum()), "included_share_of_county_eligible_renters": float(selected["eligible_renters"].sum()/c["eligible_renters"]), "rent_band_results": bands.to_dict(orient="records"), "sensitivity_cutoff_50": bands50.to_dict(orient="records"), "descriptive_tract_spearman_censored_rent_ties": float(selected["rent_plot_value"].rank().corr(selected["burden_pct"].rank())), "share_top_burden_quartile_also_top_rent_quartile": float((selected.loc[selected["burden_pct"].ge(selected["burden_pct"].quantile(.75)), "rent_plot_value"] >= selected["rent_plot_value"].quantile(.75)).mean())}
    audit = {"inputs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [RAW / "acs_tracts.json", RAW / "acs_county.json", RAW / "la_tracts.geojson"]}, "versions": {"python": platform.python_version(), "geopandas": gpd.__version__, "pandas": pd.__version__, "matplotlib": matplotlib.__version__, "shapely": shapely.__version__, "pyproj": pyproj.__version__}, "source_crs": str(boundaries.crs), "map_crs": PROJECTED_CRS, "join": "one-to-one on 11-digit GEOID; every boundary feature matched; ACS-only areas verified to contain zero renter households", "tracts": len(tracts), "boundary_features": len(boundaries), "included_tracts": len(selected), "missing_geometry": missing_geometry, "missing_geometry_renters_total": float(no_geometry["renters_total"].sum()), "missing_acs": missing_acs, "invalid_geometry": 0, "geometry_repair": "none", "minimum_estimated_eligible_renters": MIN_HOUSEHOLDS, "precision_note": "Cutoff is an author stability rule on estimated households, not an unweighted survey sample-size test.", "moe_note": "90% MOEs; sums/differences use root-sum-of-squares approximation; subset share formula uses ratio fallback for negative radicand. Grouped approximations ignore unavailable covariances and rent-band assignment uncertainty.", "censoring_note": "B25064_001E=3501 or + annotation is treated as $3,500 or more; no exact upper rent is inferred.", "geographic_note": "Main map zoom is -118.78,33.68,-117.66,34.40 in WGS84. Full-county inset includes all source boundary features. Place points are orientation labels, not neighborhood boundaries."}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    (OUT / "audit.json").write_text(json.dumps(audit, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
