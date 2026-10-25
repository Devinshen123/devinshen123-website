"""Read the IPUMS fixed-width extract using its original DDI layout.

This is a data-readiness check and descriptive preview, not a finished article.
All outputs contain aggregate data; raw microdata remain in data/raw/.
"""

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("No telework", "Some hours teleworked", "All hours teleworked",
          "Telework hours invalid or missing", "Telework status unavailable")


def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run():
    raw, out = ROOT / "data/raw", ROOT / "results"
    out.mkdir(parents=True, exist_ok=True)
    ns = {"d": "ddi:codebook:2_5"}
    tree = ET.parse(raw / "cps_00002.xml")
    layout, variables = {}, []
    for node in tree.findall(".//d:var", ns):
        loc = node.find("d:location", ns)
        name = node.attrib["name"]
        layout[name] = (int(loc.attrib["StartPos"]) - 1, int(loc.attrib["EndPos"]))
        variables.append({"name": name, "label": node.findtext("d:labl", namespaces=ns),
                          "start": layout[name][0] + 1, "end": layout[name][1],
                          "implied_decimals": int(node.attrib.get("dcml", 0))})
    required = ("YEAR", "MONTH", "SERIAL", "PERNUM", "ASECFLAG", "AGE",
                "EMPSTAT", "WTFINL", "AHRSWORKT", "TELWRKPAY", "TELWRKHR")
    assert set(required) <= set(layout)
    assert next(v for v in variables if v["name"] == "WTFINL")["implied_decimals"] == 4
    pay_node = tree.find(".//d:var[@name='TELWRKPAY']", ns)
    pay_codes = {int(c.findtext("d:catValu", namespaces=ns)):
                 c.findtext("d:labl", namespaces=ns)
                 for c in pay_node.findall("d:catgry", ns)}
    assert pay_codes[1] == "Yes" and pay_codes[2] == "No"
    width = max(end for _, end in layout.values())

    samples, flags, pay_counts, issues = Counter(), Counter(), Counter(), Counter()
    seen = defaultdict(set)
    monthly = defaultdict(lambda: [0, 0])
    by_age = defaultdict(lambda: [0, 0])
    hours_hist = defaultdict(lambda: [0, 0])
    fraction_hist = defaultdict(lambda: [0, 0])
    eligible = 0
    with gzip.open(raw / "cps_00002.dat.gz", "rt", encoding="ascii") as stream:
        for line in stream:
            record = line.rstrip("\r\n")
            assert len(record) == width, "Unexpected record width"
            row = {}
            for name in required:
                a, b = layout[name]
                text = record[a:b].strip()
                if name == "ASECFLAG" and text == "":
                    text = "0"  # Structurally blank outside March, not missing data.
                assert text != "", f"Unexpected blank in {name}"
                row[name] = int(text)
            assert row["YEAR"] == 2024 and 1 <= row["MONTH"] <= 12
            month = row["MONTH"]
            samples[month] += 1
            flags[row["ASECFLAG"]] += 1
            person_key = row["SERIAL"] * 100 + row["PERNUM"]
            if person_key in seen[month]:
                issues["duplicate_sample_person_key"] += 1
            seen[month].add(person_key)

            # Telework universe: civilians 16+ employed and actually at work last week.
            if row["AGE"] < 16 or row["EMPSTAT"] != 10:
                continue
            assert row["WTFINL"] > 0
            eligible += 1
            weight = row["WTFINL"]  # Integer units of 0.0001 people.
            telework, actual, remote = row["TELWRKPAY"], row["AHRSWORKT"], row["TELWRKHR"]
            pay_counts[telework] += 1
            if telework == 2:
                category = LABELS[0]
            elif telework == 1:
                if not (1 <= actual <= 198 and 1 <= remote <= 198):
                    category = LABELS[3]
                    issues["telework_yes_invalid_hours"] += 1
                elif remote > actual:
                    category = LABELS[3]
                    issues["telework_hours_exceed_total"] += 1
                else:
                    category = LABELS[2] if remote == actual else LABELS[1]
                    for key in ((category, remote),):
                        hours_hist[key][0] += 1
                        hours_hist[key][1] += weight
                    fraction = remote / actual
                    band = ("100%" if fraction == 1 else "75%-<100%" if fraction >= .75
                            else "50%-<75%" if fraction >= .5 else "25%-<50%"
                            if fraction >= .25 else ">0%-<25%")
                    fraction_hist[band][0] += 1
                    fraction_hist[band][1] += weight
            else:
                category = LABELS[4]
                issues["telework_status_unavailable"] += 1
            bucket = monthly[(month, category)]
            bucket[0] += 1
            bucket[1] += weight
            age = row["AGE"]
            age_group = ("16-24" if age < 25 else "25-34" if age < 35 else "35-44"
                         if age < 45 else "45-54" if age < 55 else "55-64"
                         if age < 65 else "65+")
            by_age[(age_group, category)][0] += 1
            by_age[(age_group, category)][1] += weight

    assert set(samples) == set(range(1, 13))
    assert 1 not in flags, "ASEC must not be included"
    assert issues["duplicate_sample_person_key"] == 0
    save_csv(out / "variables.csv", variables)
    save_csv(out / "sample_counts.csv", [
        {"year": 2024, "month": month, "person_month_records": count}
        for month, count in sorted(samples.items())])
    monthly_rows = []
    totals = defaultdict(lambda: [0, 0])
    for month in range(1, 13):
        denominator = sum(monthly[(month, label)][1] for label in LABELS)
        for label in LABELS:
            count, weight = monthly[(month, label)]
            monthly_rows.append({"month": month, "category": label,
                                 "person_month_records": count, "weighted_people": weight / 10000,
                                 "share_of_people_at_work_pct": 100 * weight / denominator})
            totals[label][0] += count
            totals[label][1] += weight
    save_csv(out / "monthly_summary.csv", monthly_rows)
    total_weight = sum(weight for _, weight in totals.values())
    remote_weight = totals[LABELS[1]][1] + totals[LABELS[2]][1]
    annual_rows = []
    for label in LABELS:
        count, weight = totals[label]
        annual_rows.append({"year": 2024, "category": label,
                            "person_month_records": count,
                            "annual_average_people": weight / 10000 / 12,
                            "share_of_people_at_work_pct": 100 * weight / total_weight,
                            "share_of_classifiable_teleworkers_pct":
                            100 * weight / remote_weight if label in LABELS[1:3] else None})
    assert abs(sum(row["share_of_people_at_work_pct"] for row in annual_rows) - 100) < 1e-8
    save_csv(out / "annual_summary.csv", annual_rows)
    age_rows = []
    for age in sorted({age for age, _ in by_age}):
        denominator = sum(by_age[(age, label)][1] for label in LABELS)
        for label in LABELS:
            count, weight = by_age[(age, label)]
            age_rows.append({"age_group": age, "category": label,
                             "person_month_records": count,
                             "annual_average_people": weight / 10000 / 12,
                             "share_of_people_at_work_pct": 100 * weight / denominator})
    save_csv(out / "age_summary.csv", age_rows)
    save_csv(out / "remote_hours_distribution.csv", [
        {"category": label, "weekly_remote_hours": hours, "person_month_records": count,
         "annual_average_people": weight / 10000 / 12}
        for (label, hours), (count, weight) in sorted(hours_hist.items())])
    save_csv(out / "remote_fraction_distribution.csv", [
        {"share_of_actual_hours_remote": band, "person_month_records": count,
         "annual_average_people": weight / 10000 / 12,
         "share_of_classifiable_teleworkers_pct": 100 * weight / remote_weight}
        for band, (count, weight) in sorted(fraction_hist.items())])

    files = []
    for path in (raw / "cps_00002.dat.gz", raw / "cps_00002.xml"):
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha})
    inventory = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "extract_number": 2, "files": files, "year": 2024, "monthly_samples": len(samples),
        "person_month_records": sum(samples.values()), "variables": len(variables),
        "at_work_age_16_plus_records": eligible,
        "observed_asec_flags": dict(flags), "observed_telework_codes_at_work": dict(pay_counts),
        "checks": dict(issues), "annual_preview": annual_rows,
        "sources": ["https://cps.ipums.org/cps-action/variables/TELWRKPAY",
                    "https://cps.ipums.org/cps-action/variables/TELWRKHR",
                    "https://cps.ipums.org/cps-action/variables/AHRSWORKT",
                    "https://cps.ipums.org/cps-action/variables/WTFINL",
                    "https://www.bls.gov/cps/telework.htm"],
        "limitations": [
            "Person-month records are not distinct people; CPS respondents recur across months.",
            "The data describe the reference week, not a permanent remote/hybrid employment contract.",
            "Some hours teleworked does not prove that remaining work occurred in an office.",
            "Telework hours cover all jobs; remote work cannot be assigned to a specific job.",
            "Employed people absent all week are outside the telework universe.",
            "Unknown telework status/hours remain separate from no telework.",
            "Rates are unadjusted ratios of annual-average weighted levels; no inference is estimated.",
        ],
    }
    (out / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: inventory[key] for key in (
        "year", "monthly_samples", "person_month_records", "variables",
        "at_work_age_16_plus_records", "checks", "annual_preview")}, ensure_ascii=False, indent=2))
    return inventory


if __name__ == "__main__":
    run()
