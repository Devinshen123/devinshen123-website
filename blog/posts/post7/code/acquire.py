"""Rebuild the matched weekly data from saved EIA tables, or refresh official HTML."""
from __future__ import annotations
import argparse, csv, hashlib, json, re, urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
SERIES = {"ca": "EMM_EPMR_PTE_SCA_DPG", "us": "EMM_EPMR_PTE_NUS_DPG"}
URLS = {key: "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=" + value
        for key, value in SERIES.items()}

class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cells, self.cell, self.in_cell = [], [], [], False
    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.cells = []
        if tag in ("td", "th"): self.cell, self.in_cell = [], True
    def handle_data(self, data):
        if self.in_cell: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        if tag == "tr" and self.cells: self.rows.append(self.cells)

def parse_rows(lines):
    observations = {}
    for line in lines:
        match = re.search(r"\b(202[0-5])-[A-Za-z]{3}\s*\|(.*)", line)
        if not match: continue
        year = int(match[1])
        for day, value in re.findall(r"(\d{2}/\d{2})\s*\|\s*([0-9]+\.[0-9]+|--|NA|W|-)(?=\s*\||\s*$)", match[2]):
            stamp = date.fromisoformat(f"{year}-{day[:2]}-{day[3:]}")
            if value in ("-", "--", "NA", "W"):
                raise ValueError(f"Missing/suppressed observation at {stamp}")
            mills = int(Decimal(value) * 1000)
            if stamp in observations and observations[stamp] != mills:
                raise ValueError(f"Conflicting duplicate: {stamp}")
            observations[stamp] = mills
    return observations

def from_html(text):
    parser = TableRows()
    parser.feed(text)
    candidates = [" | ".join(row) for row in parser.rows]
    return parse_rows(candidates)

def write_csv(ca, us):
    expected = set()
    stamp = date(2020, 1, 6)
    while stamp <= date(2025, 12, 31):
        expected.add(stamp)
        stamp += timedelta(days=7)
    assert set(ca) == expected, "California source does not contain every expected Monday."
    assert set(us) == expected, "U.S. source does not contain every expected Monday."
    assert len(expected) == 313
    path = ROOT / "data/processed/weekly_prices.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date", "ca_price", "us_price"])
        for stamp in sorted(expected):
            assert ca[stamp] > 0 and us[stamp] > 0
            writer.writerow([stamp.isoformat(), f"{Decimal(ca[stamp])/1000:.3f}",
                             f"{Decimal(us[stamp])/1000:.3f}"])
    return path

def main():
    args = argparse.ArgumentParser()
    args.add_argument("--refresh", action="store_true", help="Download official HTML; requires network.")
    options = args.parse_args()
    values = {}
    input_paths = []
    if options.refresh:
        for key in SERIES:
            request = urllib.request.Request(URLS[key], headers={"User-Agent": "Course-blog-data-replication"})
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
            path = RAW / f"{key}_history.html"
            path.write_bytes(content)
            input_paths.append(path)
            values[key] = from_html(content.decode("utf-8-sig", errors="strict"))
        refresh = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                   "urls": URLS, "format": "Official EIA HTML history tables"}
        (RAW / "refresh_provenance.json").write_text(json.dumps(refresh, indent=2) + "\n", encoding="utf-8")
    else:
        for key, filename in [("ca", "california_history_extracted.txt"), ("us", "us_history_extracted.txt")]:
            path = RAW / filename
            input_paths.append(path)
            values[key] = parse_rows(path.read_text(encoding="utf-8").splitlines())
    output = write_csv(values["ca"], values["us"])
    locked = input_paths + [output, ROOT / "assets/plotly-basic-3.0.1.min.js"]
    lock = {"sha256": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in locked}, "observations": 313, "source": "EIA"}
    (ROOT / "data/source-lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"observations": 313, "first": "2020-01-06", "last": "2025-12-29",
                      "sha256": lock["sha256"][output.relative_to(ROOT).as_posix()]}))

if __name__ == "__main__": main()
