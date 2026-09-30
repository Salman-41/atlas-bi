"""Measure real local ingestion/query/RSS. No network or fabricated baselines."""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import time

from atlas.data import connect_warehouse, ingest_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--csv', help='Optional ingestion source; use a fresh directory for cold ingestion')
    parser.add_argument('--output', default='docs/benchmark-results.json')
    parser.add_argument('--repetitions', type=int, default=10)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error('repetitions must be positive')
    result = {'recorded_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'python': platform.python_version(), 'platform': platform.platform(),
              'cpu_count': os.cpu_count(), 'scope': 'local measured run; not a full-dataset capacity claim'}
    if args.csv:
        start = time.perf_counter()
        result['ingestion'] = ingest_csv(Path(args.csv), Path(args.data_dir))
        result['ingestion_seconds'] = time.perf_counter() - start
    con = connect_warehouse(Path(args.data_dir))
    result['warehouse_events'] = con.execute('select count(*) from fact_events').fetchone()[0]
    timings = []
    for _ in range(args.repetitions):
        start = time.perf_counter()
        con.execute("select date_trunc('day',event_time),sum(price) from fact_events where event_type='purchase' group by 1 order by 1").fetchall()
        timings.append((time.perf_counter()-start)*1000)
    con.close()
    result['daily_purchase_query_ms'] = {'runs': len(timings), 'median': statistics.median(timings), 'max': max(timings), 'first': timings[0]}
    result['process_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 if platform.system() != 'Darwin' else 1024**2)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, default=str)+'\n')
    print(json.dumps(result, indent=2, default=str))

if __name__ == '__main__':
    main()
