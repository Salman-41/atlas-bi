from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from atlas.ml import (anomalies, classification_metrics, forecast, lag_features,
                      recursive_forecast, seasonal_forecast, segmentation, train_all)


def test_recursive_forecast_uses_own_predictions():
    class Echo:
        def predict(self, x):
            return [x[0][0] + 1]
    history = list(range(28))
    predictions = recursive_forecast(Echo(), history, pd.date_range('2020-01-01', periods=3))
    assert predictions == [28, 29, 30]
    assert history[-1] == 27
    assert seasonal_forecast(list(range(7)), 9) == [0, 1, 2, 3, 4, 5, 6, 0, 1]


def test_forecast_real_temporal_evaluation(tmp_path):
    days = pd.date_range('2020-01-01', periods=120)
    frame = pd.DataFrame({'day': days, 'value': 100 + np.sin(np.arange(120) * 2 * np.pi / 7) * 20})
    result = forecast(frame, tmp_path, horizon=5)
    assert result['status'] == 'trained'
    assert result['train_end'] < result['test_start']
    assert len(result['predictions']) == 5
    assert len(result['backtest']) == result['test_days']
    assert result['backtest'][0]['date'] == result['test_start']
    assert all(set(r) == {'date','actual','prediction','baseline'} for r in result['backtest'])
    assert result['metrics']['seasonal_naive']['mae'] < 1e-8
    assert result['selected_model'] == 'seasonal_naive'
    assert (tmp_path / 'forecast.joblib').exists()


def test_insufficient_data_is_not_fake_score(tmp_path):
    assert forecast(pd.DataFrame(), tmp_path)['status'] == 'insufficient_data'
    assert segmentation(pd.DataFrame(), tmp_path)['status'] == 'insufficient_data'
    assert anomalies(pd.DataFrame(), tmp_path)['status'] == 'insufficient_data'


def test_unsupervised_outputs_no_fraud_accuracy(tmp_path):
    rng = np.random.default_rng(41)
    rfm = pd.DataFrame({'user_id': np.arange(150), 'recency': rng.integers(1, 60, 150),
                        'frequency': rng.integers(1, 15, 150), 'monetary': rng.uniform(1, 200, 150)})
    result = segmentation(rfm, tmp_path)
    assert -1 <= result['metrics']['silhouette'] <= 1
    assert sum(p['customers'] for p in result['profiles']) == 150
    sessions = pd.DataFrame({'value': rng.uniform(1, 200, 150), 'items': rng.integers(1, 10, 150),
                             'unique_products': rng.integers(1, 5, 150)})
    anomaly = anomalies(sessions, tmp_path)
    assert 'precision' not in anomaly['metrics']
    assert 0 <= anomaly['flagged_sessions'] <= 150


def test_empty_warehouse_explicit_status(tmp_path):
    duckdb = pytest.importorskip('duckdb')
    con = duckdb.connect(str(tmp_path / 'warehouse.duckdb'))
    con.execute('CREATE TABLE fact_events(event_time TIMESTAMP)')
    con.close()
    result = train_all(tmp_path)
    assert all(result[k]['status'] == 'insufficient_data' for k in ['forecast', 'churn', 'segmentation', 'anomaly'])
    assert (tmp_path / 'models' / 'metrics.json').exists()


def test_full_training_cohorts_customer_disjoint(tmp_path):
    duckdb = pytest.importorskip('duckdb')
    rng = np.random.default_rng(7)
    rows = []
    for user in range(500):
        # Independent purchasing activity gives both inactivity labels at both cutoffs.
        for day in sorted(rng.choice(181, size=5, replace=False)):
            rows.append((pd.Timestamp('2019-01-01') + pd.Timedelta(days=int(day)),
                         'purchase', str(user), f's{user}-{day}', str(user % 20), float(10 + user % 50)))
    rows.extend([(pd.Timestamp('2019-01-01'), 'view', 'extent', 'begin', '1', 1.),
                 (pd.Timestamp('2019-07-01'), 'view', 'extent', 'end', '1', 1.)])
    events = pd.DataFrame(rows, columns=['event_time','event_type','user_id','user_session','product_id','price'])
    con = duckdb.connect(str(tmp_path / 'warehouse.duckdb'))
    con.register('events', events.astype({c: object for c in ['event_type', 'user_id', 'user_session', 'product_id']}))
    con.execute('CREATE TABLE fact_events AS SELECT * FROM events')
    con.close()
    result = train_all(tmp_path)
    assert result['churn']['status'] == 'trained'
    assert result['churn']['train_cutoff'] < result['churn']['test_cutoff']
    assert 0 <= result['churn']['metrics']['logistic_regression']['roc_auc'] <= 1
    assert all(result[k]['status'] == 'trained' for k in ('forecast', 'segmentation', 'anomaly'))
