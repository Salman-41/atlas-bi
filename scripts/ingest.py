"""Run with python -m scripts.ingest SOURCE.csv[.gz] --data-dir data."""
import argparse
import json
import os
from atlas.data import ingest_csv, load_postgres

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('--data-dir',default='data')
    parser.add_argument('--chunk-size',type=int,default=100000)
    parser.add_argument('--load-postgres',action='store_true',help='Mirror warehouse using DATABASE_URL (psycopg driver)')
    args = parser.parse_args()
    print(json.dumps(ingest_csv(args.source,args.data_dir,args.chunk_size),indent=2))
    if args.load_postgres:
        print(json.dumps(load_postgres(args.data_dir,os.environ['DATABASE_URL']),indent=2))
if __name__ == '__main__': main()
