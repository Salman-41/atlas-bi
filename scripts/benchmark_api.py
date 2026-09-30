"""Authenticated HTTP latency benchmark against a running API."""
import argparse
import json
import os
import statistics
import time
import httpx

p = argparse.ArgumentParser()
p.add_argument('--url', default='http://localhost:8000')
p.add_argument('--requests', type=int, default=30)
a = p.parse_args()
if not 1 <= a.requests <= 10000:
    p.error('requests must be 1..10000')
token = os.environ.get('ATLAS_BENCHMARK_TOKEN')
if not token:
    p.error('set ATLAS_BENCHMARK_TOKEN to an existing short-lived access token')
latencies = []
with httpx.Client(base_url=a.url, headers={'Authorization': f'Bearer {token}'}, timeout=60) as c:
    for _ in range(a.requests):
        t = time.perf_counter()
        r = c.get('/api/overview')
        r.raise_for_status()
        latencies.append((time.perf_counter()-t)*1000)
print(json.dumps({'endpoint':'/api/overview','requests':len(latencies),'median_ms':statistics.median(latencies),'p95_ms':sorted(latencies)[int(.95*(len(latencies)-1))],'cache':'depends on server configuration; report separately'},indent=2))
