"""Download the ACS 2024 five-year snapshot and official 2024 tract geometry.

Run: python code/fetch.py [--refresh]. Existing snapshots are reused by default.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
BASE = 'https://api.census.gov/data/2024/acs/acs5'
SUMMARY = 'https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/'
GEOMETRY_URL = 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_tract_500k.zip'
VARIABLES = ['NAME', 'B25064_001E', 'B25064_001M', 'B25064_001EA', 'B25064_001MA']
VARIABLES += [f'B25070_{i:03d}{suffix}' for i in range(1, 12) for suffix in ['E', 'M']]


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'LA-rent-pressure-course-project/1.0'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                content = response.read(250_000_001)
                if len(content) > 250_000_000:
                    raise ValueError('Unexpectedly large source file')
                return content
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    if not args.refresh and all((RAW / name).exists() for name in ['acs_tracts.json', 'acs_county.json', 'la_tracts.geojson', 'provenance.json']):
        print('Reusing the saved snapshot and its original retrieval record; use --refresh to download again.')
        return
    receipts = []
    if args.refresh or not all((RAW / f'acs_{level}.json').exists() for level in ['tracts', 'county']):
        tables = {}
        for table in ['B25064', 'B25070']:
            url = SUMMARY + f'acsdt5y2024-{table.lower()}.dat'
            content = download(url)
            reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')), delimiter='|')
            selected = {r['GEO_ID']: r for r in reader if r['GEO_ID'].startswith('1400000US06037') or r['GEO_ID'] == '0500000US06037'}
            assert len(selected) > 2000
            tables[table] = selected
            receipts.append({'table': table, 'url': url, 'source_sha256': hashlib.sha256(content).hexdigest(),
                             'operation': 'Filter LA County census tracts and county total; normalize published table column names'})
            print(f'{table}: selected {len(selected)} tract/county records', flush=True)
        assert set(tables['B25064']) == set(tables['B25070'])
        for level in ['tracts', 'county']:
            header = VARIABLES + ['state', 'county'] + (['tract'] if level == 'tracts' else [])
            rows = [header]
            for geo in sorted(tables['B25064']):
                is_tract = geo.startswith('140')
                if is_tract != (level == 'tracts'):
                    continue
                tract = geo[-6:] if is_tract else None
                name = f'Census Tract {int(tract[:4])}.{tract[4:]}; Los Angeles County; California' if is_tract else 'Los Angeles County, California'
                result = {'NAME': name}
                for table, source in tables.items():
                    for key, value in source[geo].items():
                        if key == 'GEO_ID':
                            continue
                        prefix, suffix = key.split('_')
                        result[prefix + '_' + suffix[1:] + suffix[0]] = value
                rent = result['B25064_001E']
                annotation = None
                if '+' in rent or rent == '3501':
                    annotation = '3,500+'
                    result['B25064_001E'] = '3501'
                result['B25064_001EA'] = annotation
                result['B25064_001MA'] = None
                rows.append([result.get(v) for v in VARIABLES] + ['06', '037'] + ([tract] if is_tract else []))
            target = RAW / f'acs_{level}.json'
            target.write_text(json.dumps(rows, separators=(',', ':')), encoding='utf-8')
    for level in ['tracts', 'county']:
        target = RAW / f'acs_{level}.json'
        receipts.append({'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        print(f'{target.name}: {len(json.loads(target.read_bytes())) - 1} observations', flush=True)

    geometry_target = RAW / 'la_tracts.geojson'
    if args.refresh or not geometry_target.exists():
        import geopandas as gpd
        source_dir = RAW / 'source-boundaries'
        source_dir.mkdir(exist_ok=True)
        archive_path = source_dir / 'cb_2024_06_tract_500k.zip'
        if args.refresh or not archive_path.exists():
            archive_path.write_bytes(download(GEOMETRY_URL))
        with zipfile.ZipFile(io.BytesIO(archive_path.read_bytes())) as archive:
            assert sum(x.file_size for x in archive.infolist()) < 250_000_000
            for member in archive.infolist():
                name = Path(member.filename)
                if name.is_absolute() or '..' in name.parts or member.file_size > 100_000_000:
                    raise ValueError('Unexpected boundary archive entry')
                if name.suffix.lower() in {'.shp', '.shx', '.dbf', '.prj', '.cpg', '.xml', '.txt'}:
                    (source_dir / name.name).write_bytes(archive.read(member))
        california = gpd.read_file(source_dir / 'cb_2024_06_tract_500k.shp', engine='pyogrio')
        assert california.crs is not None
        county = california.loc[california['COUNTYFP'] == '037'].copy()
        assert len(county) > 2000 and county['GEOID'].is_unique
        columns = [c for c in ['GEOID', 'NAME', 'STATEFP', 'COUNTYFP', 'TRACTCE', 'ALAND', 'AWATER', 'geometry'] if c in county]
        county[columns].to_file(geometry_target, driver='GeoJSON', engine='pyogrio')
        boundary_receipt = {'source_url': GEOMETRY_URL, 'source_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                            'operation': 'Filter COUNTYFP=037; preserve source geometry without simplification',
                            'source_crs': str(california.crs), 'tract_count': len(county)}
        (RAW / 'geometry-provenance.json').write_text(json.dumps(boundary_receipt, indent=2), encoding='utf-8')
    receipts.append({'file': geometry_target.name, 'url': GEOMETRY_URL,
                     'sha256': hashlib.sha256(geometry_target.read_bytes()).hexdigest()})
    provenance = {'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                  'acquisition': 'Official public table-based Summary Files; no API key needed',
                  'survey': '2024 ACS 5-year estimates, 2020–2024 period, dollars in 2024 purchasing power',
                  'geography': 'Los Angeles County, California (06037), census tracts',
                  'sources': receipts}
    (RAW / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    print('Snapshot ready; run code/analyze.py next.')


if __name__ == '__main__':
    main()
