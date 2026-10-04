"""Bounded, parameterized analytics. Never accepts SQL from clients."""
import os
import json
from pathlib import Path
from contextlib import contextmanager
import duckdb

@contextmanager
def warehouse():
    path = Path(os.getenv('ATLAS_DATA_DIR', 'data')) / 'warehouse.duckdb'
    if not path.exists():
        raise FileNotFoundError('Ingest a dataset before running analytics')
    con = duckdb.connect(str(path), read_only=True)
    con.execute("SET memory_limit='1GB'")
    con.execute('SET threads=2')
    try:
        yield con
    finally:
        con.close()

def rows(con, sql, params=()):
    result = con.execute(sql, params)
    names = [d[0] for d in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]

WHERE = 'event_time >= ? AND event_time < CAST(? AS DATE) + INTERVAL 1 DAY'

def provenance(con, start, end):
    return {'dataset': os.getenv('ATLAS_DATASET_LABEL', 'REES46 event data'), 'start': str(start), 'end': str(end), 'grain': 'events; purchase sessions are a proxy, not orders', 'purchase_value_definition': 'sum of observed purchase-event prices; currency unspecified by source', 'limitations': ['No costs, geography, inventory or true order identifiers', 'Purchase events may repeat; session totals are not verified orders'], 'loaded_events': con.execute('SELECT count(*) FROM fact_events').fetchone()[0]}

def overview(start, end):
    with warehouse() as con:
        kpi = rows(con, f"""SELECT coalesce(sum(price) FILTER(WHERE event_type='purchase'),0) purchase_value,
        coalesce(sum(price) FILTER(WHERE event_type='purchase' AND user_session IS NOT NULL),0) session_purchase_value,
        count(DISTINCT (user_id,user_session)) FILTER(WHERE event_type='purchase' AND user_session IS NOT NULL) purchase_sessions,
        count(DISTINCT user_id) FILTER(WHERE event_type='purchase') customers, count(*) events FROM fact_events WHERE {WHERE}""", [start, end])[0]
        kpi['aov'] = kpi['session_purchase_value'] / kpi['purchase_sessions'] if kpi['purchase_sessions'] else None
        del kpi['session_purchase_value']
        trend = rows(con, f"SELECT CAST(event_time AS DATE) date, sum(price) purchase_value, count(DISTINCT (user_id,user_session)) FILTER(WHERE user_session IS NOT NULL) purchase_sessions FROM fact_events WHERE {WHERE} AND event_type='purchase' GROUP BY 1 ORDER BY 1", [start, end])
        categories = rows(con, f"SELECT coalesce(category_code,'Unknown') category, sum(price) purchase_value FROM fact_events WHERE {WHERE} AND event_type='purchase' GROUP BY 1 ORDER BY 2 DESC LIMIT 20", [start, end])
        return {'kpis': kpi, 'trend': trend, 'categories': categories, 'provenance': provenance(con, start, end)}

def customers(start, end):
    with warehouse() as con:
        rfm = rows(con, f"""SELECT user_id, date_diff('day',CAST(max(event_time) AS DATE),CAST(? AS DATE)) recency,
        count(DISTINCT user_session) frequency, sum(price) monetary FROM fact_events
        WHERE {WHERE} AND event_type='purchase' GROUP BY user_id ORDER BY monetary DESC LIMIT 100""", [end, start, end])
        # Keep source pseudonymous identifiers inside the trusted warehouse.
        rfm = [{'profile': index, 'recency': row['recency'], 'frequency': row['frequency'],
                'monetary': row['monetary']} for index, row in enumerate(rfm, 1)]
        # Cohort is assigned from the entire observed purchase history before the cutoff.
        cohorts = rows(con, """WITH firsts AS (SELECT user_id,date_trunc('month',min(event_time)) cohort FROM fact_events WHERE event_type='purchase' AND event_time < CAST(? AS DATE)+INTERVAL 1 DAY GROUP BY 1), activity AS (SELECT DISTINCT user_id,date_trunc('month',event_time) activity_month FROM fact_events WHERE event_type='purchase' AND event_time >= ? AND event_time < CAST(? AS DATE)+INTERVAL 1 DAY) SELECT CAST(cohort AS DATE) cohort,date_diff('month',cohort,activity_month) month_index,count(*) customers FROM firsts JOIN activity USING(user_id) GROUP BY 1,2 ORDER BY 1,2""", [end, start, end])
        return {'rfm': rfm, 'cohorts': cohorts, 'provenance': provenance(con, start, end)}

def products(start, end, page, page_size):
    with warehouse() as con:
        data = rows(con, f"""SELECT product_id,coalesce(max(category_code),'Unknown') category,
        count(*) events,count(*) FILTER(WHERE event_type='purchase') purchases,
        coalesce(sum(price) FILTER(WHERE event_type='purchase'),0) purchase_value
        FROM fact_events WHERE {WHERE} GROUP BY product_id ORDER BY purchase_value DESC,product_id LIMIT ? OFFSET ?""", [start,end,page_size,(page-1)*page_size])
        total = con.execute(f'SELECT count(DISTINCT product_id) FROM fact_events WHERE {WHERE}', [start,end]).fetchone()[0]
        return {'items': data, 'total': total, 'page': page, 'page_size': page_size, 'provenance': provenance(con,start,end)}

def basket_affinity(start, end, limit=50, minimum_baskets=2):
    """Co-purchased product pairs within observed customer/session proxies."""
    with warehouse() as con:
        data = rows(con, f"""WITH items AS (
            SELECT DISTINCT user_id,user_session,product_id
            FROM fact_events WHERE {WHERE} AND event_type='purchase' AND user_session IS NOT NULL
        ), counts AS (
            SELECT product_id,count(*) AS basket_count FROM items GROUP BY product_id
        ), total AS (
            SELECT count(*) AS basket_count FROM (SELECT DISTINCT user_id,user_session FROM items)
        ), pairs AS (
            SELECT a.product_id product_a,b.product_id product_b,count(*) AS pair_count
            FROM items a JOIN items b ON a.user_id=b.user_id AND a.user_session=b.user_session
                AND a.product_id<b.product_id
            GROUP BY 1,2 HAVING count(*)>=?
        )
        SELECT p.product_a,p.product_b,p.pair_count,
            round(p.pair_count::DOUBLE/ca.basket_count,4) confidence_a_to_b,
            round(p.pair_count::DOUBLE*total.basket_count/(ca.basket_count*cb.basket_count),4) lift
        FROM pairs p JOIN counts ca ON ca.product_id=p.product_a
        JOIN counts cb ON cb.product_id=p.product_b CROSS JOIN total
        ORDER BY p.pair_count DESC,p.product_a,p.product_b LIMIT ?""",
        [start,end,minimum_baskets,limit])
        return {'items':data,'limit':limit,'minimum_baskets':minimum_baskets,
                'provenance':provenance(con,start,end),
                'limitations':['Basket is a customer/session proxy, not an order ID.',
                               'Co-occurrence does not establish causation or recommendation uplift.']}

METRICS = {'purchase_value': "coalesce(sum(price) FILTER(WHERE event_type='purchase'),0)", 'events': 'count(*)', 'purchase_sessions': "count(DISTINCT (user_id,user_session)) FILTER(WHERE event_type='purchase' AND user_session IS NOT NULL)"}
DIMENSIONS = {'day': 'CAST(event_time AS DATE)', 'category': "coalesce(category_code,'Unknown')", 'brand': "coalesce(brand,'Unknown')", 'event_type': 'event_type'}

def report(start,end,metric,dimension):
    with warehouse() as con:
        data = rows(con, f'SELECT {DIMENSIONS[dimension]} dimension,{METRICS[metric]} AS "value" FROM fact_events WHERE {WHERE} GROUP BY 1 ORDER BY 2 DESC LIMIT 1000', [start,end])
        return {'metric': metric, 'dimension': dimension, 'rows': data, 'row_limit': 1000, 'provenance': provenance(con,start,end)}


def insights(start, end):
    """Observed behavior, equally sized comparisons and warehouse coverage."""
    from datetime import timedelta
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = start - timedelta(days=days)
    with warehouse() as con:
        aggregate = f"""SELECT count(*) events, count(DISTINCT user_id) active_customers,
            count(DISTINCT user_id) FILTER(WHERE event_type='purchase') purchasing_customers,
            coalesce(sum(price) FILTER(WHERE event_type='purchase'),0) purchase_value,
            count(DISTINCT (user_id,user_session)) FILTER(WHERE event_type='purchase' AND user_session IS NOT NULL) purchase_sessions
            FROM fact_events WHERE {WHERE}"""
        current = rows(con, aggregate, [start, end])[0]
        previous = rows(con, aggregate, [previous_start, previous_end])[0]
        bounds = rows(con, 'SELECT min(CAST(event_time AS DATE)) first_date, max(CAST(event_time AS DATE)) last_date, count(*) events, count(DISTINCT product_id) products, count(DISTINCT user_id) customers FROM fact_events')[0]
        coverage = rows(con, f"""SELECT count(DISTINCT CAST(event_time AS DATE)) observed_days,
            count(*) FILTER(WHERE brand IS NOT NULL) branded_events,
            count(*) FILTER(WHERE category_code IS NOT NULL) categorized_events,
            count(*) FILTER(WHERE user_session IS NOT NULL) session_events
            FROM fact_events WHERE {WHERE}""", [start, end])[0]
        behavior = rows(con, f"SELECT event_type, count(*) events, count(DISTINCT user_id) customers FROM fact_events WHERE {WHERE} GROUP BY 1", [start, end])
        activity = rows(con, f"SELECT CAST(event_time AS DATE) date, event_type, count(*) events FROM fact_events WHERE {WHERE} GROUP BY 1,2 ORDER BY 1", [start, end])
        heatmap = rows(con, f"""SELECT isodow(event_time)-1 weekday, hour(event_time) hour,
            count(*) events, count(*) FILTER(WHERE event_type='purchase') purchases
            FROM fact_events WHERE {WHERE} GROUP BY 1,2 ORDER BY 1,2""", [start, end])
        brands = rows(con, f"""SELECT coalesce(brand,'Unspecified') brand, sum(price) purchase_value,
            count(*) purchases FROM fact_events WHERE {WHERE} AND event_type='purchase'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10""", [start, end])
        acquisition = rows(con, f"""WITH firsts AS (
            SELECT user_id,min(event_time) first_purchase FROM fact_events WHERE event_type='purchase' GROUP BY 1
        ) SELECT count(DISTINCT e.user_id) FILTER(WHERE f.first_purchase>=?) new_customers,
            count(DISTINCT e.user_id) FILTER(WHERE f.first_purchase<?) returning_customers
            FROM fact_events e JOIN firsts f USING(user_id)
            WHERE e.event_time>=? AND e.event_time<CAST(? AS DATE)+INTERVAL 1 DAY AND e.event_type='purchase'""", [start, start, start, end])[0]
        comparison_available = bounds['first_date'] is not None and bounds['first_date'] <= previous_start and bounds['last_date'] >= previous_end
        manifest_path = Path(os.getenv('ATLAS_DATA_DIR','data')) / 'acquisition.json'
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        return {'current':current, 'previous':previous,
                'comparison':{'start':str(previous_start),'end':str(previous_end),'available':comparison_available},
                'behavior':behavior,'activity':activity,'heatmap':heatmap,'brands':brands,'acquisition':acquisition,
                'coverage':dict(coverage, selected_days=days),
                'dataset':dict(bounds, sample_rows=manifest.get('sample_rows'), original_rows=manifest.get('original_event_rows'), sampling=manifest.get('sampling'), source=manifest.get('source')),
                'provenance':provenance(con,start,end)}
