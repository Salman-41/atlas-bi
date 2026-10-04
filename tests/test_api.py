import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from atlas.api import app
from atlas.models import Base,User,engine
from atlas.auth import hasher

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('ATLAS_DATABASE_URL',f'sqlite:///{tmp_path}/app.db')
    monkeypatch.setenv('ATLAS_JWT_SECRET','test-only-secret-that-is-at-least-32-characters')
    monkeypatch.setenv('ATLAS_DATA_DIR',str(tmp_path))
    Base.metadata.create_all(engine())
    with Session(engine()) as db:
        for role in ['admin','analyst','viewer']:
            db.add(User(username=role,password_hash=hasher.hash('test-password'),role=role))
        db.commit()
    with TestClient(app) as client: yield client

def auth(client,role='viewer'):
    response=client.post('/api/auth/login',json={'username':role,'password':'test-password'})
    assert response.status_code==200
    return {'Authorization':'Bearer '+response.json()['access_token']}

@pytest.mark.parametrize('origin', [
    'http://localhost:3000', 'http://127.0.0.1:3000', 'http://0.0.0.0:3000',
])
def test_login_preflight(client, origin):
    response = client.options('/api/auth/login', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin
    response = client.post('/api/auth/login', headers={'Origin': origin},
                           json={'username': 'admin', 'password': 'test-password'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin

def test_login_preflight_rejects_unlisted_origin(client):
    response = client.options('/api/auth/login', headers={
        'Origin': 'https://untrusted.example',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers

def test_auth_and_no_warehouse(client):
    assert client.get('/health').status_code==200
    assert client.get('/api/overview').status_code==401
    assert client.get('/api/overview',headers=auth(client)).status_code==503
    assert client.post('/api/auth/login',json={'username':'viewer','password':'wrong'}).status_code==401

def test_rbac_and_allowlist(client):
    body={'metric':'purchase_value','dimension':'day'}
    assert client.post('/api/reports',json=body,headers=auth(client)).status_code==403
    assert client.post('/api/jobs/train',headers=auth(client,'analyst')).status_code==403
    body['dimension']='day; DROP TABLE users'
    assert client.post('/api/reports',json=body,headers=auth(client,'analyst')).status_code==422

def test_dates_and_pagination(client):
    headers=auth(client)
    assert client.get('/api/overview?start=2020-02-01&end=2020-01-01',headers=headers).status_code==422
    assert client.get('/api/products?page_size=10000',headers=headers).status_code==422
    assert client.get('/api/predictions',headers=headers).json()['status']=='unavailable'

def test_report_and_inventory(client,tmp_path):
    import duckdb
    con=duckdb.connect(str(tmp_path/'warehouse.duckdb'))
    con.execute('CREATE TABLE fact_events(event_time TIMESTAMP,event_type VARCHAR,product_id VARCHAR,category_code VARCHAR,brand VARCHAR,price DOUBLE,user_id VARCHAR,user_session VARCHAR)')
    con.execute("INSERT INTO fact_events VALUES ('2019-10-01','purchase','1','=evil','brand',10,'u1','s1'),('2019-10-02','view','1','=evil','brand',10,'u1','s2')")
    con.close()
    headers=auth(client,'analyst')
    overview=client.get('/api/overview',headers=headers).json()
    assert overview['kpis']['purchase_value']==10
    assert overview['kpis']['purchase_sessions']==1
    assert overview['kpis']['events']==2
    csv=client.post('/api/reports',headers=headers,json={'dimension':'category','format':'csv'})
    assert "'=evil" in csv.text
    pdf=client.post('/api/reports',headers=headers,json={'format':'pdf'})
    assert pdf.content.startswith(b'%PDF')
    scenario=client.post('/api/inventory',headers=headers,json={'product_id':'1','stock_on_hand':0,'lead_time_days':5})
    assert scenario.json()['scenario'] is True

def test_purchase_session_proxy_uses_user_and_session_pair(client,tmp_path):
    import duckdb
    con=duckdb.connect(str(tmp_path/'warehouse.duckdb'))
    con.execute('CREATE TABLE fact_events(event_time TIMESTAMP,event_type VARCHAR,product_id VARCHAR,category_code VARCHAR,brand VARCHAR,price DOUBLE,user_id VARCHAR,user_session VARCHAR)')
    con.execute("INSERT INTO fact_events VALUES ('2019-10-01','purchase','1','c','b',10,'u1','shared'),('2019-10-01','purchase','2','c','b',5,'u2','shared'),('2019-10-01','purchase','3','c','b',7,'u3',NULL)")
    con.close()
    result=client.get('/api/overview',headers=auth(client,'analyst')).json()['kpis']
    assert result['customers']==3
    assert result['purchase_value']==22
    assert result['purchase_sessions']==2
    assert result['aov']==7.5

def test_market_basket_uses_session_proxy_and_reports_pair_metrics(client,tmp_path):
    import duckdb
    con=duckdb.connect(str(tmp_path/'warehouse.duckdb'))
    con.execute('CREATE TABLE fact_events(event_time TIMESTAMP,event_type VARCHAR,product_id VARCHAR,category_code VARCHAR,brand VARCHAR,price DOUBLE,user_id VARCHAR,user_session VARCHAR)')
    con.execute("""INSERT INTO fact_events VALUES
      ('2019-10-01','purchase','1','c','b',10,'u1','s1'),
      ('2019-10-01','purchase','2','c','b',12,'u1','s1'),
      ('2019-10-02','purchase','1','c','b',10,'u2','s2'),
      ('2019-10-02','purchase','2','c','b',12,'u2','s2'),
      ('2019-10-02','purchase','3','c','b',5,'u3','s3'),
      ('2019-10-02','view','4','c','b',1,'u3','s3')""")
    con.close()
    response=client.get('/api/baskets?minimum_baskets=2',headers=auth(client))
    assert response.status_code==200
    pair=response.json()['items'][0]
    assert (pair['product_a'],pair['product_b'],pair['pair_count'])==('1','2',2)
    assert pair['confidence_a_to_b']==1
    assert pair['lift']==1.5
    assert 'not an order ID' in response.json()['limitations'][0]
