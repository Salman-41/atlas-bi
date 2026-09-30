"""Deterministic synthetic fixture ONLY; never evidence for business/model claims."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
from atlas.data import COLUMNS

def generate(path, days=180, customers=240, seed=41):
    if 'synthetic' not in str(path).lower(): raise ValueError('Synthetic output filename must include synthetic')
    rng = np.random.default_rng(seed); path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    start = datetime(2020,1,1,tzinfo=timezone.utc)
    with path.open('w',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=COLUMNS); writer.writeheader()
        for day in range(days):
            for customer in range(1,customers+1):
                if customer % 5 == 0 and day > 85: continue
                if rng.random() > 0.12 + 0.04 * np.sin(day/7): continue
                session = f'synthetic-{day}-{customer}'
                for item in range(int(rng.integers(1,4))):
                    product = int(rng.integers(1,81))
                    row = dict(event_time=(start+timedelta(days=day,minutes=customer*3+item)).isoformat(),
                        product_id=product,category_id=100+product%8,category_code=f'category.{product%8}',
                        brand=f'brand-{product%12}',price=round(4+product*1.3,2),user_id=customer,user_session=session)
                    for event in ['view','cart','purchase']:
                        writer.writerow(dict(row,event_type=event))
    return path

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output',default='data/synthetic-events.csv')
    p.add_argument('--days',type=int,default=180); p.add_argument('--customers',type=int,default=240)
    a=p.parse_args(); print(generate(a.output,a.days,a.customers))
