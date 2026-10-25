"""Download official cohort archives and retain the documented column subset."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'mothers': {
        'url': 'https://nlsinfo.org/cohort-data/nlsy79_all_1979-2022.zip',
        'sha256': 'efb3bbd17ed602abf100be44802778ef88fad68aa80913cd07dce778ebda72d7',
    },
    'children': {
        'url': 'https://nlsinfo.org/cohort-data/nlscya_all_1979-2020.zip',
        'sha256': '3c9834bcab972edf41413ce950590c4a39a76f9f034584c1adcae38163785c27',
    },
}

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def download(cohort: str, cache: Path) -> Path:
    source = SOURCES[cohort]
    target = cache / (cohort + '.zip')
    if not target.exists():
        partial = target.with_suffix('.partial')
        request = urllib.request.Request(source['url'], headers={'User-Agent': 'AEDS6400 replication'})
        with urllib.request.urlopen(request, timeout=120) as remote, partial.open('wb') as output:
            shutil.copyfileobj(remote, output, length=1024 * 1024)
        partial.replace(target)
    actual = sha256(target)
    if actual != source['sha256']:
        raise ValueError(f'{cohort}: archive changed; review the codebook before using a new release.')
    return target

def extract(cohort: str, archive: Path, columns: list[str]) -> pd.DataFrame:
    with zipfile.ZipFile(archive) as source:
        name = next(name for name in source.namelist() if name.endswith('.csv'))
        print(f'Reading selected {cohort} columns; the archive stays compressed.', flush=True)
        with source.open(name) as csv_file:
            frame = pd.read_csv(csv_file, usecols=columns, dtype=str, keep_default_na=False)
    return frame[columns]

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, default=ROOT / 'data/source-cache')
    args = parser.parse_args()
    cache = args.cache_dir.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    raw = ROOT / 'data/raw'
    raw.mkdir(parents=True, exist_ok=True)
    crosswalk = json.loads((raw / 'variable-crosswalk.json').read_text(encoding='utf-8'))
    sources = {cohort: download(cohort, cache) for cohort in SOURCES}
    child = extract('children', sources['children'], crosswalk['header_validation']['children']['selected_columns'])
    child_id = crosswalk['children']['id']['column']
    mother_id = crosswalk['children']['mother_id']['column']
    assert pd.to_numeric(child[child_id]).is_unique
    mother_ids = set(pd.to_numeric(child[mother_id]))
    mother = extract('mothers', sources['mothers'], crosswalk['header_validation']['mothers']['selected_columns'])
    all_mother_rows = len(mother)
    mother = mother.loc[pd.to_numeric(mother[crosswalk['mothers']['id']['column']]).isin(mother_ids)].copy()
    assert pd.to_numeric(mother[crosswalk['mothers']['sex']['column']]).eq(2).all()
    for cohort, frame in [('mothers', mother), ('children', child)]:
        frame.to_csv(raw / (cohort + '.csv.gz'), index=False, lineterminator='\n', compression={'method': 'gzip', 'mtime': 0})
    provenance = {
        'retrieved_utc': datetime.now(timezone.utc).isoformat(),
        'data_page': 'https://www.nlsinfo.org/content/access-data-investigator/accessing-data-cohorts',
        'sources': SOURCES,
        'source_rows': {'mothers_full_cohort': all_mother_rows, 'mothers_with_child_id': len(mother), 'children': len(child)},
        'selected_csv_sha256': {cohort: hashlib.sha256(gzip.open(raw / (cohort + '.csv.gz'), 'rb').read()).hexdigest() for cohort in SOURCES},
        'selection': 'Only documented columns; mothers retained when their public ID occurs in the child MPUBID column. No outcome-based selection at acquisition.',
    }
    (raw / 'source-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(provenance['source_rows']), flush=True)

if __name__ == '__main__':
    main()
