"""Download and parse the Minneapolis Fed's published annual CPI-U table."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = 'https://www.minneapolisfed.org/about-us/monetary-policy/inflation-calculator/consumer-price-index-1913-'

class TableRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []
    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None

def fetch_annual(output_dir, source_snapshot=None):
    """Write annual CPI values for 1980-2020 and exact source provenance.

    The Federal Reserve table publishes annual averages to one decimal place.
    These are publisher-provided annual values, not a fresh monthly aggregation.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if source_snapshot is None:
        request = Request(SOURCE_URL, headers={'User-Agent': 'AEDS6400 reproducible data tutorial'})
        with urlopen(request, timeout=45) as response:
            source_bytes = response.read()
            last_modified = response.headers.get('Last-Modified')
        retrieved_utc = datetime.now(timezone.utc).isoformat()
    else:
        source_snapshot = Path(source_snapshot)
        source_bytes = source_snapshot.read_bytes()
        retrieved_utc = datetime.fromtimestamp(source_snapshot.stat().st_mtime, timezone.utc).isoformat()
        last_modified = None
    parser = TableRows()
    parser.feed(source_bytes.decode('utf-8'))
    values = {}
    for row in parser.rows:
        if len(row) >= 2 and row[0].isdigit():
            year = int(row[0])
            if 1980 <= year <= 2020:
                if year in values:
                    raise ValueError(f'Duplicate year: {year}')
                values[year] = float(row[1].replace(',', ''))
    assert set(values) == set(range(1980, 2021)), 'Missing annual CPI values'
    assert all(v > 0 for v in values.values())
    assert abs(values[2020] - 258.811) < 0.05, 'Unexpected 2020 CPI benchmark'
    with (output_dir / 'cpi_annual.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, lineterminator='\n')
        writer.writerow(['year', 'cpi'])
        writer.writerows((year, f'{values[year]:.1f}') for year in sorted(values))
    (output_dir / 'cpi_source.html').write_bytes(source_bytes)
    provenance = {
        'source_url': SOURCE_URL,
        'publisher': 'Federal Reserve Bank of Minneapolis',
        'underlying_source': 'U.S. Bureau of Labor Statistics',
        'measure': 'Annual average CPI-U, all items, U.S. city average',
        'series_correspondence': 'CUUR0000SA0 / CPIAUCNS annual averages',
        'seasonal_adjustment': 'Not seasonally adjusted annual averages',
        'retrieved_utc': retrieved_utc,
        'http_last_modified': last_modified,
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'output_sha256': hashlib.sha256((output_dir / 'cpi_annual.csv').read_bytes()).hexdigest(),
        'precision': 'One decimal place, as published in the annual table',
        'aggregation': 'Published annual averages; not independently recomputed from twelve monthly readings',
        'checks': {'unique_years': len(values), 'first_year': min(values), 'last_year': max(values), 'cpi_2020': values[2020], 'missing_years': []}
    }
    (output_dir / 'cpi-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    return values

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='post6-cache')
    parser.add_argument('--source-snapshot')
    args = parser.parse_args()
    values = fetch_annual(args.output_dir, args.source_snapshot)
    print(f'Saved {len(values)} annual CPI-U values, 1980-2020; 2020={values[2020]:.1f}.')
