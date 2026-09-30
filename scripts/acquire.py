"""Download pinned genuine REES46 files and keep complete sampled user histories.

Run: python scripts/acquire.py --modulus 100
Raw ZIPs remain local; CSV processing streams without materializing all records.
"""
import argparse
import csv
import hashlib
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

MONTHS = ('2019-Oct','2019-Nov','2019-Dec','2020-Jan','2020-Feb')
BASE = 'https://www.kaggle.com/api/v1/datasets/download/mkechinov/ecommerce-events-history-in-cosmetics-shop/'


def acquire(root: Path, modulus: int):
    raw = root / 'data' / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    output = root / 'data' / 'sample.csv'
    manifest = {'source': 'mkechinov/ecommerce-events-history-in-cosmetics-shop', 'version': 6,
                'license': 'Data files © Original Authors; free use with source and REES46 attribution',
                'sampling': f'int.from_bytes(sha256(user_id)[:8], big) % {modulus} == 0',
                'grain': 'behavior event', 'files': [], 'sample_rows': 0}
    started = time.monotonic()
    with output.open('w', newline='') as target:
        writer = None
        for month in MONTHS:
            name = month + '.csv'
            path = raw / (name + '.zip')
            url = BASE + name + '?datasetVersionNumber=6'
            if not path.exists():
                partial = path.with_suffix('.partial')
                with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as f:
                    while block := response.read(1024 * 1024):
                        f.write(block)
                # Validate archive before committing resumable local cache.
                with zipfile.ZipFile(partial) as z:
                    if name not in z.namelist():
                        raise ValueError(f'Missing expected member {name}')
                partial.replace(path)
            checksum = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
            count = selected = purchases = 0
            csv_hash = hashlib.sha256()
            with zipfile.ZipFile(path) as z:
                # A separate streaming pass computes exact uncompressed source hash.
                with z.open(name) as f:
                    while block := f.read(1024 * 1024):
                        csv_hash.update(block)
                with z.open(name) as binary:
                    reader = csv.DictReader(io.TextIOWrapper(binary, encoding='utf-8-sig', newline=''))
                    if writer is None:
                        writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
                        writer.writeheader()
                    for row in reader:
                        count += 1
                        purchases += row['event_type'] == 'purchase'
                        uid = row['user_id']
                        if uid and int.from_bytes(hashlib.sha256(uid.encode()).digest()[:8], 'big') % modulus == 0:
                            writer.writerow(row)
                            selected += 1
            target.flush()
            manifest['files'].append({'name': name, 'url': url, 'rows': count,
                'purchase_event_rows': purchases, 'sample_rows': selected,
                'zip_sha256': checksum, 'csv_sha256': csv_hash.hexdigest(), 'zip_bytes': path.stat().st_size})
            manifest['sample_rows'] += selected
            manifest['elapsed_seconds'] = round(time.monotonic() - started, 3)
            (root / 'data' / 'acquisition.json').write_text(json.dumps(manifest, indent=2) + '\n')
            print(json.dumps(manifest['files'][-1]), flush=True)
    manifest['sample_sha256'] = hashlib.file_digest(output.open('rb'), 'sha256').hexdigest()
    manifest['original_event_rows'] = sum(f['rows'] for f in manifest['files'])
    (root / 'data' / 'acquisition.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'rows': manifest['original_event_rows'], 'sample_rows': manifest['sample_rows']}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--modulus', type=int, default=100)
    args = parser.parse_args()
    if args.modulus < 1:
        parser.error('--modulus must be positive')
    acquire(args.root, args.modulus)
