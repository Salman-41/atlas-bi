import csv
import pytest
import duckdb
from atlas.data import COLUMNS, connect_warehouse, ingest_csv

def write(path, rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS); w.writeheader(); w.writerows(rows)

def row(**kwargs):
    return dict(dict(event_time='2019-10-01 00:00:00 UTC',event_type='purchase',product_id='12',
        category_id='1487580005268456287',category_code='',brand='',price='10.50',user_id='7',user_session='s'),**kwargs)

def test_idempotence_exact_integer_and_global_dedup(tmp_path):
    source=tmp_path/'a.csv'; write(source,[row(),row(),row(price='bad'),row(product_id='13')])
    data=tmp_path/'warehouse'
    result=ingest_csv(source,data,chunk_size=1)
    assert (result['rows_read'],result['rows_inserted'],result['rows_rejected'],result['duplicate_rows']) == (4,2,1,1)
    assert ingest_csv(source,data)['status']=='already_ingested'
    source2=tmp_path/'b.csv'; write(source2,[row(),row(product_id='14',event_time='2019-10-03 00:00:00 UTC')])
    assert ingest_csv(source2,data)['rows_inserted']==1
    con=connect_warehouse(data)
    assert con.execute('SELECT count(*) FROM fact_events').fetchone()[0]==3
    assert con.execute('SELECT max(category_id) FROM fact_events').fetchone()[0]==1487580005268456287
    assert con.execute('SELECT count(*) FROM dim_product').fetchone()[0]==3
    assert str(con.execute('SELECT last_seen FROM dim_customer WHERE user_id=7').fetchone()[0])=='2019-10-03 00:00:00'
    assert con.execute("SELECT count(*) FROM duckdb_constraints() WHERE table_name='dim_customer' AND constraint_type='PRIMARY KEY'").fetchone()[0]==1
    assert con.execute('SELECT sum(purchase_value) FROM daily_metrics').fetchone()[0]==31.5
    con.close()
    fresh=duckdb.connect(str(data/'warehouse.duckdb'),read_only=True)
    assert fresh.execute('SELECT count(*) FROM fact_events').fetchone()[0]==3
    fresh.close()

def test_invalid_source_rollback(tmp_path):
    source=tmp_path/'bad.csv'; source.write_text('hello,world\n1,2\n')
    with pytest.raises(ValueError,match='Missing required'):
        ingest_csv(source,tmp_path/'warehouse')
    con=connect_warehouse(tmp_path/'warehouse')
    assert con.execute('SELECT count(*) FROM ingestion_runs').fetchone()[0]==0
    con.close()

def test_bad_types_are_quarantined_as_counts(tmp_path):
    source=tmp_path/'a.csv'; write(source,[row(event_type='unknown'),row(user_id='1.5'),row(event_time='never'),row(price='-1'),row(category_id='')])
    r=ingest_csv(source,tmp_path/'warehouse',2)
    assert r['rows_rejected']==4
    assert r['rows_inserted']==1
