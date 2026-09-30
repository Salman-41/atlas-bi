# Modeling observed commerce behavior

ATLAS BI trains on the canonical `fact_events` warehouse. `python scripts/train.py --data-dir data` writes serialized models and a machine-readable `data/models/metrics.json`. Install the project first (`pip install -e '.[mlops]'` enables the optional MLflow integration). Set `MLFLOW_TRACKING_URI` to enable MLflow artifact logging. Without that variable, training uses local Joblib artifacts and JSON; no tracking service is required.

A successful training status means an artifact and measured evaluation exist. An `insufficient_data` status describes the missing history, sample size, or classes. A short downloaded development slice is not evidence that a full dataset model has been validated. Never present synthetic fixture metrics as business results. Joblib artifacts must come from trusted sources; deserializing an untrusted model can execute code.

## Forecasting

Target: total observed purchase-line value per day, not audited revenue or profit. Use all observed calendar days, inserting zero for missing days inside the interval; this assumes no recorded events means no observed purchases. Drop the final date because a partial ingest may leave that day incomplete. Require at least 90 days.

Features are lags 1, 7 and 14, prior 7/28-day means, weekday and month. The final 20% (at most 30 days) is the untouched temporal test. Two HistGradientBoosting leaf-size candidates are selected on an internal 14-day validation tail. Every multi-day prediction recursively appends predictions, never actual holdout targets. Compare MAE and RMSE with weekly seasonal naive. The better holdout MAE selects the deployed approach; retrain gradient boosting on all available complete dates. The serialized artifact records the selected baseline or model, and last 28 observations. Thirty-day forecasts are emitted; no unsupported quarterly forecast or confidence intervals are invented. A longer business deployment should use several rolling-origin test folds and an untouched final production acceptance window.

## Customer inactivity prediction

The label is **no observed purchase in the next 30 days**, an inactivity proxy, not proof that a customer has left. Recency, purchase-line frequency and observed spend come from the previous 60 days. At least 150 calendar days are required. Training cutoff is 90 days before the final complete boundary; test cutoff is 30 days before it. The training outcome window closes 30 days before the test cutoff. Customers are deterministically assigned by hash: 80% training and 20% held out, with no shared customers across evaluations. Training and test feature periods may overlap in calendar time, but customers are disjoint and each feature window ends before its own labels begin.

Compare a prior-frequency DummyClassifier to a log-transformed, imputed, scaled, class-weighted logistic regression. Fit transforms on training data only. Report precision, recall, F1 at a fixed 0.5 threshold, ROC-AUC, average precision and test prevalence. Require two classes in each split and at least 100 training/30 test customers; otherwise skip explicitly. This conservative cohort test evaluates new customers at a later cutoff, not performance on returning known customers. The model is not claimed calibrated, causal or ready to automatically contact customers.

## Customer segmentation

Use current trailing 60-day RFM for at most 30,000 deterministically selected purchasing customers. Log-transform skewed features and standardize them. Compare KMeans k=3,4,5 with 10 initializations; choose silhouette on a reproducible sample of at most 2,000. Export each cluster's size and mean raw RFM so the business interpretation is transparent. Cluster identifiers are arbitrary. Silhouette measures geometric cohesion, not business uplift or future behavior. Selection on silhouette is exploratory internal validation, not a held-out predictive score.

## Anomaly triage

Group observed purchases by customer/session, because the source has no order ID. Null sessions are excluded. At most 50,000 deterministic session samples are brought into Python. Log-transform session value, item lines and unique products; robust-scale then fit Isolation Forest (150 trees, 2,048 subsamples, one worker). Set contamination to 2% as an explicit analyst review-budget assumption. Report score distribution and flagged fraction; without labels it is invalid to report fraud precision, recall or accuracy. An unusual session is not established fraud.

## Resource controls and reproducibility

DuckDB aggregate queries scan on disk with a 512 MB memory limit and two threads. Python receives bounded customer/session feature tables, not the raw event stream. The limits target an 8 GB laptop; DuckDB can still require temporary disk space for full-data group-bys. Stable selection hashes and seed 41 support repeatability within pinned dependency versions. Model training is CPU-only, does not use a GPU, and intentionally omits XGBoost/Optuna because these compact baselines do not justify extra infrastructure. Set `OMP_NUM_THREADS=2` / `OPENBLAS_NUM_THREADS=2` when running alongside the complete stack. MLflow integration is optional and logs measured metrics JSON and model artifacts.

Each run records source path, row count, observed bounds, UTC run time and caps. Upstream ingestion manifests retain hashes and lineage. A source with incomplete month coverage or truncated ingestion can invalidate absence labels: inspect quality/coverage before interpreting results. No full-data benchmark or model performance is claimed until its output has been produced on that data.
