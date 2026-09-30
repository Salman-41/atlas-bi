"""Bounded-memory REES46 ingestion with auditable, idempotent source manifests."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import pandas as pd
import duckdb

COLUMNS = ['event_time','event_type','product_id','category_id','category_code','brand','price','user_id','user_session']
EVENT_TYPES = {'view','cart','remove_from_cart','purchase'}

def connect_warehouse(data_dir: str | Path | None = None):
    root = Path(data_dir or os.getenv('ATLAS_DATA_DIR','data')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    spill = root / 'spill'; spill.mkdir(exist_ok=True)
    con = duckdb.connect(str(root / 'warehouse.duckdb'))
    con.execute("SET threads=2")
    con.execute("SET memory_limit='1GB'")
    con.execute("SET temp_directory=?", [str(spill)])
    con.execute('''CREATE TABLE IF NOT EXISTS fact_events (
        event_time TIMESTAMP NOT NULL, event_type VARCHAR NOT NULL,
        product_id BIGINT NOT NULL, category_id BIGINT, category_code VARCHAR,
        brand VARCHAR, price DOUBLE NOT NULL, user_id BIGINT NOT NULL,
        user_session VARCHAR, event_id VARCHAR PRIMARY KEY)''')
    con.execute('''CREATE TABLE IF NOT EXISTS ingestion_runs (
        checksum VARCHAR PRIMARY KEY, source_name VARCHAR, status VARCHAR,
        started_at TIMESTAMP, completed_at TIMESTAMP, rows_read BIGINT,
        rows_valid BIGINT, rows_rejected BIGINT, rows_inserted BIGINT,
        duplicate_rows BIGINT, parquet_path VARCHAR, report_json VARCHAR)''')
    con.execute('''CREATE TABLE IF NOT EXISTS dim_product (
        product_id BIGINT PRIMARY KEY, category_id BIGINT, category_code VARCHAR, brand VARCHAR)''')
    con.execute('CREATE TABLE IF NOT EXISTS dim_customer (user_id BIGINT PRIMARY KEY, first_seen TIMESTAMP, last_seen TIMESTAMP)')
    con.execute('CREATE TABLE IF NOT EXISTS dim_date (date DATE PRIMARY KEY, year INTEGER, month INTEGER, day INTEGER, weekday INTEGER)')
    con.execute('''CREATE OR REPLACE VIEW daily_metrics AS SELECT CAST(event_time AS DATE) event_date,
        event_type, COUNT(*) events, SUM(CASE WHEN event_type='purchase' THEN price ELSE 0 END) purchase_value,
        COUNT(DISTINCT user_id) customers, COUNT(DISTINCT (user_id,user_session)) FILTER(WHERE user_session IS NOT NULL) sessions
        FROM fact_events GROUP BY 1,2''')
    return con

def _checksum(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''): digest.update(block)
    return digest.hexdigest()

def _clean(frame: pd.DataFrame):
    out = frame.copy()
    reasons: dict[str, int] = {}
    invalid = pd.Series(False, index=out.index)
    def reject(name, mask):
        nonlocal invalid
        mask = mask.fillna(True)
        reasons[name] = int(mask.sum()); invalid |= mask
    out['event_time'] = pd.to_datetime(out['event_time'], utc=True, errors='coerce', format='mixed').dt.tz_localize(None)
    reject('invalid_event_time', out.event_time.isna())
    reject('invalid_event_type', ~out.event_type.isin(EVENT_TYPES))
    for col in ['product_id','category_id','user_id']:
        # Parse nullable integers directly; float intermediates destroy 64-bit category IDs.
        parsed = []
        bad = []
        for value in out[col]:
            try:
                if pd.isna(value) or str(value).strip() == '':
                    parsed.append(pd.NA); bad.append(col != 'category_id'); continue
                number = int(str(value))
                if number < 0 or number > 9223372036854775807: raise ValueError()
                parsed.append(number); bad.append(False)
            except (ValueError, TypeError): parsed.append(pd.NA); bad.append(True)
        out[col] = pd.array(parsed, dtype='Int64')
        reject('invalid_' + col, pd.Series(bad, index=out.index))
    out['price'] = pd.to_numeric(out.price, errors='coerce')
    reject('invalid_price', out.price.isna() | ~out.price.between(0, 1e12))
    for col in ['category_code','brand','user_session']:
        out[col] = out[col].astype('string').str.strip().replace('', pd.NA)
    out = out.loc[~invalid, COLUMNS].copy()
    # Canonical JSON makes missing values explicit and unambiguous across columns.
    def identity(row):
        values = [None if pd.isna(v) else (v.isoformat() if isinstance(v,pd.Timestamp) else str(v)) for v in row]
        return hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()
    out['event_id'] = [identity(row) for row in out.itertuples(index=False,name=None)]
    return out, reasons, int(invalid.sum())

def ingest_csv(path: str | Path, data_dir: str | Path | None = None, chunk_size: int = 100000):
    if not 1 <= chunk_size <= 1000000: raise ValueError('chunk_size must be between 1 and 1,000,000')
    source = Path(path).resolve()
    if not source.is_file(): raise FileNotFoundError(source)
    root = Path(data_dir or os.getenv('ATLAS_DATA_DIR','data')).resolve()
    con = connect_warehouse(root)
    checksum = _checksum(source)
    existing = con.execute("SELECT report_json FROM ingestion_runs WHERE checksum=? AND status='completed'",[checksum]).fetchone()
    if existing:
        con.close(); return dict(json.loads(existing[0]), status='already_ingested')
    synthetic = 'synthetic' in source.name.lower()
    prior = con.execute('SELECT report_json FROM ingestion_runs LIMIT 1').fetchone()
    if prior and json.loads(prior[0]).get('lineage',{}).get('synthetic',False) != synthetic:
        con.close()
        raise ValueError('Authentic and synthetic sources require separate warehouse directories')
    started = time.monotonic()
    staging = root / 'parquet' / ('.staging-' + uuid.uuid4().hex)
    final = root / 'parquet' / checksum
    staging.mkdir(parents=True)
    report = dict(checksum=checksum,source_name=source.name,status='completed',rows_read=0,rows_valid=0,
                  rows_rejected=0,rows_inserted=0,duplicate_rows=0,quality={},parquet_path=str(final),
                  lineage={'transform_version':'rees46-v1','grain':'deduplicated observed event',
                           'synthetic': 'synthetic' in source.name.lower()})
    import shutil
    committed = False
    try:
        con.execute('BEGIN TRANSACTION')
        for index, frame in enumerate(pd.read_csv(source,dtype='string',chunksize=chunk_size,compression='infer')):
            absent = set(COLUMNS)-set(frame.columns)
            if absent: raise ValueError('Missing required columns: ' + ', '.join(sorted(absent)))
            clean, reasons, rejected = _clean(frame)
            report['rows_read'] += len(frame); report['rows_valid'] += len(clean); report['rows_rejected'] += rejected
            for reason,count in reasons.items(): report['quality'][reason] = report['quality'].get(reason,0)+count
            if clean.empty: continue
            # Normalize extension strings before DuckDB binds the frame. This
            # keeps nullable pandas string inference from changing by version.
            for column in clean.columns:
                if pd.api.types.is_string_dtype(clean[column].dtype):
                    clean[column] = clean[column].astype(object).where(clean[column].notna(), None)
            con.register('incoming_frame',clean)
            con.execute('''CREATE OR REPLACE TEMP TABLE accepted AS SELECT DISTINCT i.* FROM incoming_frame i
                WHERE NOT EXISTS (SELECT 1 FROM fact_events f WHERE f.event_id=i.event_id)''')
            inserted = con.execute('SELECT count(*) FROM accepted').fetchone()[0]
            report['rows_inserted'] += inserted; report['duplicate_rows'] += len(clean)-inserted
            con.execute('INSERT INTO fact_events SELECT * FROM accepted')
            target = str(staging / f'part-{index:06d}.parquet').replace("'","''")
            con.execute(f"COPY accepted TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            con.unregister('incoming_frame')
        # Rebuild dimensions once per committed file. Repeated conflict updates
        # can invalidate indexed column segments within a large transaction.
        # Transactional replacement preserves visibility and primary keys.
        for table, definition, query in [
            ('dim_product', 'product_id BIGINT PRIMARY KEY, category_id BIGINT, category_code VARCHAR, brand VARCHAR',
             'SELECT product_id, min(category_id), min(category_code), min(brand) FROM fact_events GROUP BY product_id'),
            ('dim_customer', 'user_id BIGINT PRIMARY KEY, first_seen TIMESTAMP, last_seen TIMESTAMP',
             'SELECT user_id, min(event_time), max(event_time) FROM fact_events GROUP BY user_id'),
            ('dim_date', 'date DATE PRIMARY KEY, year INTEGER, month INTEGER, day INTEGER, weekday INTEGER',
             'SELECT DISTINCT CAST(event_time AS DATE),year(event_time),month(event_time),day(event_time),isodow(event_time) FROM fact_events')]:
            con.execute(f'DROP TABLE {table}')
            con.execute(f'CREATE TABLE {table} ({definition})')
            con.execute(f'INSERT INTO {table} {query}')
        report['elapsed_seconds'] = round(time.monotonic()-started,3)
        # Rename before committing: a crash can leave an unreferenced directory, never a committed missing file.
        if final.exists(): shutil.rmtree(final)
        staging.rename(final)
        con.execute('''INSERT INTO ingestion_runs VALUES (?,?,'completed',current_timestamp,current_timestamp,?,?,?,?,?,?,?)''',
                    [checksum,source.name,report['rows_read'],report['rows_valid'],report['rows_rejected'],report['rows_inserted'],
                     report['duplicate_rows'],str(final),json.dumps(report)])
        con.execute('COMMIT')
        committed = True
        (root / 'quality').mkdir(exist_ok=True)
        (root / 'quality' / f'{checksum}.json').write_text(json.dumps(report,indent=2))
        return report
    except Exception:
        if not committed: con.execute('ROLLBACK')
        if staging.exists(): shutil.rmtree(staging)
        raise
    finally: con.close()

def load_postgres(data_dir: str | Path, database_url: str, chunk_size: int = 10000):
    """Mirror committed facts with bounded-memory psycopg COPY and idempotent merge.

    PostgreSQL is optional for local analytical development. A dedicated schema
    keeps warehouse migrations separate from operational application tables.
    """
    from sqlalchemy import create_engine
    engine = create_engine(database_url)
    con = connect_warehouse(data_dir)
    total = 0
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('CREATE SCHEMA IF NOT EXISTS atlas_warehouse')
            connection.exec_driver_sql('''CREATE TABLE IF NOT EXISTS atlas_warehouse.fact_events (
                event_time TIMESTAMP NOT NULL, event_type TEXT NOT NULL,
                product_id BIGINT NOT NULL, category_id BIGINT, category_code TEXT,
                brand TEXT, price DOUBLE PRECISION NOT NULL, user_id BIGINT NOT NULL,
                user_session TEXT, event_id TEXT PRIMARY KEY)''')
            connection.exec_driver_sql('CREATE INDEX IF NOT EXISTS fact_events_time_type ON atlas_warehouse.fact_events (event_time,event_type)')
            connection.exec_driver_sql('CREATE INDEX IF NOT EXISTS fact_events_user_time ON atlas_warehouse.fact_events (user_id,event_time)')
            connection.exec_driver_sql('CREATE INDEX IF NOT EXISTS fact_events_product_time ON atlas_warehouse.fact_events (product_id,event_time)')
            connection.exec_driver_sql('CREATE TEMP TABLE atlas_stage (LIKE atlas_warehouse.fact_events) ON COMMIT DROP')
            cursor = connection.connection.driver_connection.cursor()
            reader = con.execute('SELECT * FROM fact_events')
            while True:
                batch = reader.fetchmany(chunk_size)
                if not batch: break
                with cursor.copy('COPY atlas_stage FROM STDIN') as copy:
                    for record in batch: copy.write_row(record)
                cursor.execute('INSERT INTO atlas_warehouse.fact_events SELECT * FROM atlas_stage ON CONFLICT(event_id) DO NOTHING')
                total += cursor.rowcount
                cursor.execute('TRUNCATE atlas_stage')
            # Dimension refresh is atomic with the facts. No customer identifiers leave the trusted warehouse.
            for table,definition,query in [
                ('dim_product','product_id BIGINT PRIMARY KEY,category_id BIGINT,category_code TEXT,brand TEXT',
                 'SELECT product_id,min(category_id),min(category_code),min(brand) FROM atlas_warehouse.fact_events GROUP BY product_id'),
                ('dim_customer','user_id BIGINT PRIMARY KEY,first_seen TIMESTAMP,last_seen TIMESTAMP',
                 'SELECT user_id,min(event_time),max(event_time) FROM atlas_warehouse.fact_events GROUP BY user_id'),
                ('dim_date','date DATE PRIMARY KEY,year INTEGER,month INTEGER,day INTEGER,weekday INTEGER',
                 'SELECT DISTINCT event_time::date,extract(year from event_time),extract(month from event_time),extract(day from event_time),extract(isodow from event_time) FROM atlas_warehouse.fact_events')]:
                connection.exec_driver_sql(f'CREATE TABLE IF NOT EXISTS atlas_warehouse.{table} ({definition})')
                connection.exec_driver_sql(f'TRUNCATE atlas_warehouse.{table}')
                connection.exec_driver_sql(f'INSERT INTO atlas_warehouse.{table} {query}')
            cursor.close()
        return {'rows_inserted':total,'schema':'atlas_warehouse'}
    finally:
        con.close(); engine.dispose()
