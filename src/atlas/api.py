"""ATLAS BI HTTP boundary: authentication, validated contracts and provenance."""
import csv
import io
import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from atlas import analytics
from atlas.auth import current_user, roles, token, verify_password
from atlas.models import User, session

app = FastAPI(title='ATLAS BI', version='0.1.0', description='Observed commerce events, explicitly bounded analytics and scenario planning')
cors_origins = [origin.strip() for origin in os.getenv(
    'CORS_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,http://0.0.0.0:3000',
).split(',') if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['Authorization','Content-Type'])
logger = logging.getLogger('atlas.api')

@app.middleware('http')
async def logging_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(json.dumps({'event':'http_request','method':request.method,'path':request.url.path,'status':response.status_code,'duration_ms':round((time.perf_counter()-started)*1000,2)}))
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(FileNotFoundError)
async def missing_data(request, exc):
    return JSONResponse(status_code=503, content={
        'detail': 'Your analytics dataset has not been loaded yet. Import event data to open this workspace.',
        'code': 'warehouse_missing',
    })

class Dates(BaseModel):
    start: date = date(2019,10,1)
    end: date = date(2020,2,29)
    @model_validator(mode='after')
    def ordered(self):
        if self.end < self.start or (self.end-self.start).days > 3660:
            raise ValueError('Date range must be ordered and no longer than 10 years')
        return self

def dates(start: date=Query(date(2019,10,1)),end: date=Query(date(2020,2,29))):
    if end < start or (end-start).days > 3660:
        raise HTTPException(422,'Invalid date range')
    return Dates(start=start,end=end)

class Credentials(BaseModel):
    username: str = Field(min_length=1,max_length=120)
    password: str = Field(min_length=1,max_length=1024)

@app.get('/health')
def health():
    return {'status':'ok','service':'atlas-bi'}

@app.post('/api/auth/login')
def login(body: Credentials, db=Depends(session)):
    user = db.scalar(select(User).where(User.username==body.username))
    # Constant-cost verification also for unknown users to reduce enumeration.
    from atlas.auth import hasher
    encoded = user.password_hash if user else hasher.hash('unregistered-account-padding')
    valid = verify_password(body.password,encoded)
    if not user or not valid:
        raise HTTPException(401,'Invalid username or password')
    return {'access_token':token(user),'token_type':'bearer','expires_in':1800,'role':user.role}

@app.get('/api/auth/me')
def me(user=Depends(current_user)):
    return {'username':user.username,'role':user.role}

def cached_overview(start,end):
    url=os.getenv('ATLAS_REDIS_URL')
    if not url:
        return analytics.overview(start,end)
    from redis import Redis
    from fastapi.encoders import jsonable_encoder
    path=Path(os.getenv('ATLAS_DATA_DIR','data'))/'warehouse.duckdb'
    key=f'atlas:overview:{path.stat().st_mtime_ns}:{start}:{end}' if path.exists() else 'atlas:missing'
    cache=Redis.from_url(url,socket_connect_timeout=0.3,socket_timeout=0.3)
    try:
        hit=cache.get(key)
        if hit:
            return json.loads(hit)
    except Exception:
        logger.warning('Redis unavailable; querying warehouse')
    result=analytics.overview(start,end)
    try:
        cache.setex(key,120,json.dumps(jsonable_encoder(result)))
    except Exception:
        pass
    return result

@app.get('/api/overview')
def overview(window=Depends(dates),user=Depends(current_user)):
    return cached_overview(window.start,window.end)

@app.get('/api/customers')
def customers(window=Depends(dates),user=Depends(current_user)):
    return analytics.customers(window.start,window.end)

@app.get('/api/insights')
def insights(window=Depends(dates),user=Depends(current_user)):
    return analytics.insights(window.start,window.end)

@app.get('/api/products')
def products(window=Depends(dates),page:int=Query(1,ge=1,le=1000000),page_size:int=Query(25,ge=1,le=100),user=Depends(current_user)):
    return analytics.products(window.start,window.end,page,page_size)

@app.get('/api/baskets')
def baskets(window=Depends(dates),limit:int=Query(50,ge=1,le=100),minimum_baskets:int=Query(2,ge=2,le=1000000),user=Depends(current_user)):
    return analytics.basket_affinity(window.start,window.end,limit,minimum_baskets)

@app.get('/api/predictions')
def predictions(user=Depends(current_user)):
    path=Path(os.getenv('ATLAS_DATA_DIR','data')) /'models'/'metrics.json'
    if not path.exists():
        return {'status':'unavailable','models':{},'limitations':['No trained artifacts. Run the ML command on sufficient observed history.']}
    return {'status':'available','models':json.loads(path.read_text()),'limitations':['Retrospective evaluation does not guarantee future performance.']}

class Report(Dates):
    metric: Literal['purchase_value','events','purchase_sessions']='purchase_value'
    dimension: Literal['day','category','brand','event_type']='day'
    format: Literal['json','csv','pdf']='json'

@app.post('/api/reports')
def reports(body:Report,user=Depends(roles('admin','analyst'))):
    result=analytics.report(body.start,body.end,body.metric,body.dimension)
    if body.format=='json':
        return result
    if body.format=='csv':
        output=io.StringIO()
        writer=csv.writer(output)
        writer.writerow([body.dimension,body.metric])
        for item in result['rows']:
            label=str(item['dimension'])
            # Prevent spreadsheet formula execution when source text is exported.
            if label.startswith(('=','+','-','@','\t','\r')):
                label="'"+label
            writer.writerow([label,item['value']])
        return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="atlas-report.csv"'})
    from reportlab.pdfgen.canvas import Canvas
    output=io.BytesIO()
    canvas=Canvas(output)
    canvas.setTitle('ATLAS BI analytical report')
    canvas.drawString(40,800,f'ATLAS BI | {body.metric} by {body.dimension}')
    canvas.drawString(40,780,f'{body.start} to {body.end}; observed event data')
    y=750
    for item in result['rows']:
        canvas.drawString(40,y,f"{str(item['dimension'])[:70]}: {item['value']:.2f}")
        y-=16
        if y<50:
            canvas.showPage(); y=790
    canvas.save()
    return Response(output.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="atlas-report.pdf"'})

class Question(Dates):
    question:str=Field(min_length=5,max_length=500)

@app.post('/api/ask')
def ask(body:Question,user=Depends(current_user)):
    question=body.question.lower()
    if any(word in question for word in ['forecast','next quarter','predict']):
        model=predictions(user)
        return {'intent':'forecast','answer':'Forecast artifacts are available for inspection.' if model['status']=='available' else 'No trained forecast is available. Train on sufficient observed history first.','evidence':model,'provenance':{'source':'local model artifacts'}}
    if 'segment' in question:
        raise HTTPException(422,'Segment attribution is not yet supported. Ask about categories, products, revenue or events.')
    if any(word in question for word in ['product','demand']):
        result=analytics.products(body.start,body.end,1,10)
        return {'intent':'product_performance','answer':'These products have the highest observed purchase value in the selected period. This ranking does not establish demand decline.','evidence':result['items'],'provenance':result['provenance']}
    if any(word in question for word in ['revenue','sales','purchase','category','events']):
        result=analytics.overview(body.start,body.end)
        return {'intent':'purchase_performance','answer':'Observed purchase value and daily trends are shown below. These describe activity; event data alone cannot establish why a change occurred.','evidence':{'kpis':result['kpis'],'trend':result['trend'],'categories':result['categories']},'provenance':result['provenance']}
    raise HTTPException(422,'Supported questions concern revenue, purchase events, product performance and forecast availability.')

class Inventory(Dates):
    product_id:str=Field(min_length=1,max_length=100)
    stock_on_hand:float=Field(ge=0,le=1e9)
    lead_time_days:float=Field(gt=0,le=365)
    service_factor:float=Field(default=1.65,ge=0,le=5)

@app.post('/api/inventory')
def inventory(body:Inventory,user=Depends(current_user)):
    import math
    with analytics.warehouse() as con:
        count=con.execute(f"SELECT count(*) FROM fact_events WHERE {analytics.WHERE} AND event_type='purchase' AND CAST(product_id AS VARCHAR)=?",[body.start,body.end,body.product_id]).fetchone()[0]
        daily=count/((body.end-body.start).days+1)
        reorder=math.ceil(daily*body.lead_time_days+body.service_factor*math.sqrt(daily*body.lead_time_days))
        return {'scenario':True,'daily_demand':daily,'reorder_point':reorder,'recommended_order':max(0,reorder-body.stock_on_hand),'assumptions':{'stock_on_hand':body.stock_on_hand,'lead_time_days':body.lead_time_days,'service_factor':body.service_factor,'method':'Poisson purchase-event proxy; no source inventory or quantity data'},'provenance':analytics.provenance(con,body.start,body.end)}

@app.post('/api/jobs/train',status_code=202)
def train(user=Depends(roles('admin'))):
    from atlas.tasks import train_models
    job=train_models.delay()
    return {'job_id':job.id,'status':'queued'}
