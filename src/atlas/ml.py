"""CPU-only, bounded training with explicit observational-data limitations."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, recall_score,
                             roc_auc_score, silhouette_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler

SEED = 41
CUSTOMER_CAP = 30_000
EVENT_CAP = 50_000
FEATURES = ['recency', 'frequency', 'monetary']


def unavailable(reason: str) -> dict:
    return {'status': 'insufficient_data', 'reason': reason}


def regression_metrics(actual, predicted) -> dict:
    return {'mae': float(mean_absolute_error(actual, predicted)),
            'rmse': float(np.sqrt(mean_squared_error(actual, predicted)))}


def lag_features(history: list[float], day: pd.Timestamp) -> list[float]:
    """All features use values strictly before the prediction day."""
    return [history[-1], history[-7], history[-14], float(np.mean(history[-7:])),
            float(np.mean(history[-28:])), day.dayofweek, day.month]


def recursive_forecast(model, history, dates) -> list[float]:
    history = list(map(float, history))
    predictions = []
    for day in dates:
        value = max(0.0, float(model.predict([lag_features(history, day)])[0]))
        predictions.append(value)
        history.append(value)
    return predictions


def seasonal_forecast(history, horizon) -> list[float]:
    values = list(map(float, history))
    for _ in range(horizon):
        values.append(values[-7])
    return values[-horizon:]


def forecast(daily: pd.DataFrame, output: Path, horizon: int = 30) -> dict:
    if len(daily) < 90:
        return unavailable('At least 90 observed calendar days are required for a temporal holdout.')
    daily = daily.sort_values('day').set_index('day')
    daily.index = pd.to_datetime(daily.index)
    # Missing days within the observed interval mean no recorded purchases; not proven store closure.
    series = daily['value'].asfreq('D', fill_value=0).astype(float)
    test_days = min(30, len(series) // 5)
    training = series.iloc[:-test_days]
    holdout = series.iloc[-test_days:]
    x = [lag_features(training.iloc[:i].tolist(), training.index[i]) for i in range(28, len(training))]
    y = training.iloc[28:].to_numpy()
    if len(y) < 30:
        return unavailable('Not enough training days after lag generation.')
    # Tune only inside training; recursive validation never consumes held-out targets.
    split = max(20, len(y) - 14)
    candidate_results = []
    for leaves in (7, 15):
        candidate = HistGradientBoostingRegressor(max_leaf_nodes=leaves, max_iter=100,
                    min_samples_leaf=5, l2_regularization=1, random_state=SEED)
        candidate.fit(np.asarray(x[:split]), y[:split])
        values = recursive_forecast(candidate, training.iloc[:28 + split], training.index[28 + split:])
        score = float(mean_absolute_error(y[split:], values))
        candidate_results.append((score, leaves))
    selected_leaves = min(candidate_results)[1]
    model = HistGradientBoostingRegressor(max_leaf_nodes=selected_leaves, max_iter=100,
                min_samples_leaf=5, l2_regularization=1, random_state=SEED).fit(x, y)
    predicted = recursive_forecast(model, training, holdout.index)
    baseline = seasonal_forecast(training, len(holdout))
    metrics = {'seasonal_naive': regression_metrics(holdout, baseline),
               'hist_gradient_boosting': regression_metrics(holdout, predicted)}
    winner = min(metrics, key=lambda name: metrics[name]['mae'])
    full_x = [lag_features(series.iloc[:i].tolist(), series.index[i]) for i in range(28, len(series))]
    model.fit(full_x, series.iloc[28:])
    dates = pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=horizon)
    future = (recursive_forecast(model, series, dates) if winner == 'hist_gradient_boosting'
              else seasonal_forecast(series, horizon))
    joblib.dump({'model': model, 'selected': winner, 'history': series.iloc[-28:].tolist()}, output / 'forecast.joblib')
    return {'status': 'trained', 'metrics': metrics, 'selected_model': winner,
            'backtest': [{'date': str(d.date()), 'actual': round(float(a), 2),
                          'prediction': round(float(p), 2), 'baseline': round(float(b), 2)}
                         for d, a, p, b in zip(holdout.index, holdout, predicted, baseline)],
            'train_end': str(training.index[-1].date()), 'test_start': str(holdout.index[0].date()),
            'test_days': len(holdout), 'horizon': horizon, 'selected_max_leaf_nodes': selected_leaves,
            'predictions': [{'date': str(d.date()), 'prediction': round(v, 2)} for d, v in zip(dates, future)],
            'limitations': ['Observed purchase value, not audited revenue.',
                           'No confidence intervals; short seasonal history; zero-filled unobserved days.']}


def rfm(connection, cutoff, customers: pd.DataFrame, lookback: int = 60) -> pd.DataFrame:
    connection.register('selected_customers', customers[['user_id']].astype({'user_id': object}))
    result = connection.execute("""
        SELECT e.user_id, date_diff('day', max(e.event_time), CAST(? AS TIMESTAMP)) AS recency,
          count(*) AS frequency, sum(e.price) AS monetary
        FROM fact_events e INNER JOIN selected_customers c USING(user_id)
        WHERE e.event_type='purchase' AND e.event_time < CAST(? AS TIMESTAMP)
          AND e.event_time >= CAST(? AS TIMESTAMP) - INTERVAL '1 day' * ?
        GROUP BY e.user_id
    """, [cutoff, cutoff, cutoff, lookback]).df()
    connection.unregister('selected_customers')
    return result


def classification_metrics(y, probabilities) -> dict:
    predicted = np.asarray(probabilities) >= 0.5
    return {'precision': float(precision_score(y, predicted, zero_division=0)),
            'recall': float(recall_score(y, predicted, zero_division=0)),
            'f1': float(f1_score(y, predicted, zero_division=0)),
            'roc_auc': float(roc_auc_score(y, probabilities)),
            'average_precision': float(average_precision_score(y, probabilities))}


def churn(connection, start, end, customers, output) -> dict:
    if (end - start).days < 150:
        return unavailable('150 calendar days are required: 60-day features, two separated cutoffs, 30-day labels.')
    # Train labels stop before the test cutoff. Evaluation users never enter training.
    train_cutoff = end - pd.Timedelta(days=90)
    test_cutoff = end - pd.Timedelta(days=30)
    frames = []
    for cutoff, test_group in ((train_cutoff, False), (test_cutoff, True)):
        cohort = customers[customers['holdout'].astype(bool) == test_group]
        frame = rfm(connection, cutoff.to_pydatetime(), cohort)
        connection.register('cohort', frame[['user_id']].astype({'user_id': object}))
        returning = connection.execute("""SELECT DISTINCT e.user_id FROM fact_events e
            INNER JOIN cohort c USING(user_id) WHERE event_type='purchase'
            AND event_time >= CAST(? AS TIMESTAMP)
            AND event_time < CAST(? AS TIMESTAMP) + INTERVAL '30 days'""", [cutoff.to_pydatetime(), cutoff.to_pydatetime()]).df()
        connection.unregister('cohort')
        frame['inactive'] = (~frame.user_id.isin(returning.user_id)).astype(int)
        frames.append(frame)
    train, test = frames
    if len(train) < 100 or len(test) < 30 or train.inactive.nunique() < 2 or test.inactive.nunique() < 2:
        return unavailable('Both classes and at least 100 training / 30 held-out customers are required.')
    x_train = np.log1p(train[FEATURES])
    x_test = np.log1p(test[FEATURES])
    candidate = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
                               LogisticRegression(class_weight='balanced', max_iter=1000, random_state=SEED))
    baseline = DummyClassifier(strategy='prior').fit(x_train, train.inactive)
    candidate.fit(x_train, train.inactive)
    metrics = {'prior_baseline': classification_metrics(test.inactive, baseline.predict_proba(x_test)[:, 1]),
               'logistic_regression': classification_metrics(test.inactive, candidate.predict_proba(x_test)[:, 1])}
    # Preserve evaluated model rather than silently refit against held-out users.
    joblib.dump({'pipeline': candidate, 'features': FEATURES, 'transform': 'log1p'}, output / 'churn.joblib')
    return {'status': 'trained', 'metrics': metrics, 'training_customers': len(train),
            'test_customers': len(test), 'test_prevalence': float(test.inactive.mean()),
            'train_cutoff': str(train_cutoff.date()), 'test_cutoff': str(test_cutoff.date()),
            'label': 'No observed purchase in subsequent 30 days',
            'limitations': ['Inactivity proxy is not contractual churn.',
                           'Customer-disjoint future cohort; threshold fixed at 0.5; no calibration guarantee.']}


def segmentation(frame: pd.DataFrame, output: Path) -> dict:
    if len(frame) < 50:
        return unavailable('At least 50 purchasing customers are required.')
    scaler = StandardScaler()
    features = scaler.fit_transform(np.log1p(frame[FEATURES]))
    candidates = []
    for k in (3, 4, 5):
        model = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(features)
        if len(np.unique(model.labels_)) < 2:
            continue
        score = float(silhouette_score(features, model.labels_, sample_size=min(2000, len(frame)), random_state=SEED))
        candidates.append((score, model))
    if not candidates:
        return unavailable('Insufficient feature variation to identify clusters.')
    score, model = max(candidates, key=lambda item: item[0])
    frame = frame.copy()
    frame['segment'] = model.labels_
    profiles = frame.groupby('segment').agg(customers=('user_id', 'size'), recency=('recency', 'mean'),
                                             frequency=('frequency', 'mean'), monetary=('monetary', 'mean')).reset_index()
    joblib.dump({'scaler': scaler, 'model': model, 'features': FEATURES, 'transform': 'log1p'}, output / 'segmentation.joblib')
    return {'status': 'trained', 'metrics': {'silhouette': score}, 'k': model.n_clusters,
            'candidates': [{'k': m.n_clusters, 'silhouette': s} for s, m in candidates],
            'customers': len(frame), 'profiles': profiles.to_dict('records'),
            'limitations': ['Exploratory snapshot; cluster IDs have no intrinsic business meaning.',
                           'Silhouette is internal validation, not future predictive performance.']}


def anomalies(frame: pd.DataFrame, output: Path) -> dict:
    if len(frame) < 100:
        return unavailable('At least 100 purchase sessions are required.')
    columns = ['value', 'items', 'unique_products']
    pipeline = make_pipeline(RobustScaler(), IsolationForest(n_estimators=150, max_samples=min(2048, len(frame)),
                             contamination=0.02, random_state=SEED, n_jobs=1))
    values = np.log1p(frame[columns])
    pipeline.fit(values)
    scores = pipeline.decision_function(values)
    flags = scores < 0
    joblib.dump({'pipeline': pipeline, 'features': columns, 'transform': 'log1p'}, output / 'anomaly.joblib')
    return {'status': 'trained', 'sessions': len(frame), 'flagged_sessions': int(flags.sum()),
            'metrics': {'flagged_fraction': float(flags.mean()), 'score_min': float(scores.min()),
                        'score_median': float(np.median(scores))},
            'limitations': ['No fraud labels: precision/recall cannot be measured.',
                           'Contamination 2% is a review-budget assumption, not a measured fraud rate.',
                           'Sessions are proxies, not source order identifiers.']}


def train_all(data_dir: str | Path, output_dir: str | Path | None = None) -> dict:
    import duckdb
    data_dir = Path(data_dir)
    output = Path(output_dir or data_dir / 'models')
    output.mkdir(parents=True, exist_ok=True)
    # Avoid carrying a previous run's trained artifact into an insufficient-data run.
    for name in ('forecast', 'churn', 'segmentation', 'anomaly'):
        (output / f'{name}.joblib').unlink(missing_ok=True)
    db = data_dir / 'warehouse.duckdb'
    result = {'trained_at': datetime.now(timezone.utc).isoformat(), 'source': str(db),
              'caps': {'customers': CUSTOMER_CAP, 'sessions': EVENT_CAP, 'duckdb_memory': '512MB', 'threads': 2}}
    connection = duckdb.connect(str(db), read_only=True)
    connection.execute("SET memory_limit='512MB'")
    connection.execute('SET threads=2')
    try:
        bounds = connection.execute('SELECT min(event_time), max(event_time), count(*) FROM fact_events').fetchone()
        if not bounds or bounds[0] is None:
            for key in ('forecast', 'churn', 'segmentation', 'anomaly'):
                result[key] = unavailable('Warehouse contains no events.')
        else:
            start, end = pd.Timestamp(bounds[0]), pd.Timestamp(bounds[1]).normalize()
            result['source_rows'] = bounds[2]
            result['observed_start'] = str(start)
            result['observed_end'] = str(bounds[1])
            # Discard incomplete final day for targets/labels.
            daily = connection.execute("""SELECT CAST(event_time AS DATE) AS day,
                sum(CASE WHEN event_type='purchase' THEN price ELSE 0 END) AS value
                FROM fact_events WHERE event_time < ? GROUP BY 1 ORDER BY 1""", [end.to_pydatetime()]).df()
            customers = connection.execute(f"""SELECT user_id, (hash(user_id) % 5 = 0) AS holdout
                FROM fact_events WHERE event_type='purchase' AND user_id IS NOT NULL
                GROUP BY user_id ORDER BY hash(user_id) LIMIT {CUSTOMER_CAP}""").df()
            current = rfm(connection, end.to_pydatetime(), customers)
            sessions = connection.execute(f"""SELECT user_id, user_session, sum(price) AS value,
                count(*) AS items, count(DISTINCT product_id) AS unique_products FROM fact_events
                WHERE event_type='purchase' AND user_session IS NOT NULL AND event_time < ?
                GROUP BY user_id, user_session ORDER BY hash(user_id || user_session) LIMIT {EVENT_CAP}""",
                [end.to_pydatetime()]).df()
            result['forecast'] = forecast(daily, output)
            result['churn'] = churn(connection, start, end, customers, output)
            result['segmentation'] = segmentation(current, output)
            result['anomaly'] = anomalies(sessions, output)
    finally:
        connection.close()
    (output / 'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False, default=str))
    if os.getenv('MLFLOW_TRACKING_URI'):
        import mlflow
        mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
        mlflow.set_experiment('atlas-bi')
        with mlflow.start_run():
            mlflow.log_params(result['caps'])
            mlflow.log_artifact(str(output / 'metrics.json'))
            def log_numeric_metrics(prefix, value):
                if isinstance(value, dict):
                    for key, nested in value.items():
                        log_numeric_metrics(f'{prefix}.{key}', nested)
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    mlflow.log_metric(prefix, float(value))
            for name in ('forecast', 'churn', 'segmentation', 'anomaly'):
                log_numeric_metrics(name, result[name].get('metrics', {}))
            for path in output.glob('*.joblib'):
                mlflow.log_artifact(str(path))
    return result
