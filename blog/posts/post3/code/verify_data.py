"""Independent pandas reconciliation of the raw records and article inputs."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def run():
    ns = {"d": "ddi:codebook:2_5"}
    tree = ET.parse(ROOT / "data/raw/cps_00002.xml")
    columns = ["YEAR", "MONTH", "AGE", "EMPSTAT", "WTFINL", "AHRSWORKT", "TELWRKPAY", "TELWRKHR"]
    specifications = []
    for name in columns:
        loc = tree.find(f".//d:var[@name='{name}']/d:location", ns)
        specifications.append((int(loc.attrib["StartPos"]) - 1, int(loc.attrib["EndPos"])))
    totals = {name: 0 for name in ("population", "no", "some", "all", "unknown", "eligible_records")}
    unknown_hours = {}
    for frame in pd.read_fwf(ROOT / "data/raw/cps_00002.dat.gz", colspecs=specifications,
                             names=columns, dtype="int64", chunksize=100000, compression="gzip"):
        assert set(frame.YEAR) == {2024}
        base = frame.loc[(frame.AGE >= 16) & (frame.EMPSTAT == 10)].copy()
        yes = base.TELWRKPAY == 1
        valid = (base.AHRSWORKT.between(1, 198) & base.TELWRKHR.between(1, 198)
                 & (base.TELWRKHR <= base.AHRSWORKT))
        definitions = {
            "no": base.TELWRKPAY == 2,
            "some": yes & valid & (base.TELWRKHR < base.AHRSWORKT),
            "all": yes & valid & (base.TELWRKHR == base.AHRSWORKT),
        }
        definitions["unknown"] = ~(definitions["no"] | definitions["some"] | definitions["all"])
        totals["eligible_records"] += len(base)
        totals["population"] += int(base.WTFINL.sum())
        for name, condition in definitions.items():
            totals[name] += int(base.loc[condition, "WTFINL"].sum())
        for actual, remote in base.loc[yes & ~valid, ["AHRSWORKT", "TELWRKHR"]].itertuples(index=False, name=None):
            key = f"total_hours={actual}, telework_hours={remote}"
            unknown_hours[key] = unknown_hours.get(key, 0) + 1
    annual = pd.read_csv(ROOT / "results/annual_summary.csv").set_index("category")
    labels = {"no": "No telework", "some": "Some hours teleworked",
              "all": "All hours teleworked", "unknown": "Telework hours invalid or missing"}
    differences = {}
    for name, label in labels.items():
        recomputed = totals[name] / 10000 / 12
        differences[name] = abs(recomputed - annual.loc[label, "annual_average_people"])
    assert max(differences.values()) < 1e-6
    assert totals["population"] == sum(totals[name] for name in labels)
    remote = totals["some"] + totals["all"]
    report = {"passed": True, "method": "Separate pandas fixed-width import and vectorized masks",
              "eligible_records": totals["eligible_records"],
              "maximum_absolute_difference_annual_average_people": max(differences.values()),
              "some_hours_share_pct": 100 * totals["some"] / remote,
              "all_hours_share_pct": 100 * totals["all"] / remote,
              "unclassifiable_hours": unknown_hours,
              "inference": "No confidence intervals or tests of monthly differences were estimated."}
    (ROOT / "results/independent_reconciliation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()

