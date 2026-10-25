"""Exact-decimal calculations and source checks. No third-party Python dependencies."""
from __future__ import annotations
import csv, hashlib, json, statistics
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
D = Decimal

def check_sources():
    lock = json.loads((ROOT / "data/source-lock.json").read_text(encoding="utf-8"))
    for name, expected in lock["sha256"].items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert actual == expected, f"Source changed: {name}. Review it before rebuilding."
    return lock

def load_rows():
    with (ROOT / "data/processed/weekly_prices.csv").open(encoding="utf-8", newline="") as handle:
        rows = []
        for item in csv.DictReader(handle):
            ca, us = D(item["ca_price"]), D(item["us_price"])
            gap = ca - us
            rows.append({"date": item["date"], "ca_price": ca, "us_price": us,
                         "gap_per_gallon": gap, "extra_15_gallons": gap * 15,
                         "premium_pct": gap / us * 100})
    return rows

def summarize(rows):
    values = [r["extra_15_gallons"] for r in rows]
    smallest = min(rows, key=lambda r: r["extra_15_gallons"])
    largest = max(rows, key=lambda r: r["extra_15_gallons"])
    return {"weeks": len(rows), "first_date": rows[0]["date"], "last_date": rows[-1]["date"],
            "mean_extra": sum(values) / len(values), "median_extra": statistics.median(values),
            "min_extra": smallest["extra_15_gallons"], "min_date": smallest["date"],
            "max_extra": largest["extra_15_gallons"], "max_date": largest["date"],
            "mean_ca_price": sum(r["ca_price"] for r in rows) / len(rows),
            "mean_us_price": sum(r["us_price"] for r in rows) / len(rows)}

def json_ready(value):
    if isinstance(value, D): return float(value)
    if isinstance(value, dict): return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, list): return [json_ready(v) for v in value]
    return value

def main():
    check_sources()
    rows = load_rows()
    dates = [date.fromisoformat(r["date"]) for r in rows]
    assert len(rows) == len(set(dates)) == 313
    assert dates == sorted(dates)
    assert dates[0] == date(2020, 1, 6) and dates[-1] == date(2025, 12, 29)
    assert all((b-a) == timedelta(days=7) for a, b in zip(dates, dates[1:]))
    assert all(r["ca_price"] > 0 and r["us_price"] > 0 for r in rows)
    assert all(r["extra_15_gallons"] == (r["ca_price"] - r["us_price"]) * 15 for r in rows)
    yearly = [dict(year=year, **summarize([r for r in rows if r["date"].startswith(str(year))]))
              for year in range(2020, 2026)]
    overall = summarize(rows)
    highest_ca = max(rows, key=lambda r: r["ca_price"])
    highest_us = max(rows, key=lambda r: r["us_price"])
    max_gap = max(rows, key=lambda r: r["extra_15_gallons"])
    summary = {"overall": overall, "yearly": yearly,
               "highest_ca_price": highest_ca, "highest_us_price": highest_us,
               "largest_gap": max_gap, "all_weeks_ca_above_us": all(r["gap_per_gallon"] > 0 for r in rows),
               "gallons": 15, "currency": "Nominal U.S. dollars",
               "period_weighting": "Each observed week has equal weight; no transaction-volume weighting across weeks.",
               "population": "EIA regular gasoline, all formulations, including taxes. U.S. includes California."}
    RESULTS.mkdir(exist_ok=True)
    for name, items in [("weekly_comparison.csv", rows), ("yearly_summary.csv", yearly)]:
        with (RESULTS / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(items[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(items)
    (RESULTS / "summary.json").write_text(json.dumps(json_ready(summary), indent=2) + "\n", encoding="utf-8")
    diagnostics = {"checks": {"313_unique_dates": True, "complete_monday_panel": True,
                              "positive_observed_prices": True, "exact_decimal_formula": True,
                              "source_hashes_verified": True, "no_missing_observations": True},
                   "source_precision": "$0.001 per gallon", "zero_filling": False,
                   "interpolation": False}
    (RESULTS / "data_checks.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(json_ready(summary), indent=2))
    return summary

if __name__ == "__main__": main()
