# ATLAS BI

**Retail event intelligence with a traceable data pipeline and CPU-friendly machine learning.**

ATLAS BI turns five months of real e-commerce behavior events into an auditable analytics platform. It combines chunked ingestion, Parquet, a DuckDB star warehouse, a role-protected FastAPI service, a responsive Next.js interface, and four scikit-learn workflows. The local path is designed for an 8 GB, CPU-only laptop.

> This source contains about 20 million behavior events, not 20 million orders. “Purchase value” sums observed purchase-event prices; a “purchasing session” is an order proxy. The source has no costs, returns, stock records, order ID, or location, so ATLAS BI does not report profit or geographic performance. Five historical months cannot establish annual seasonality or current market behavior.

## Implemented capabilities

| Area | Capability |
| --- | --- |
| Ingestion | Version-pinned downloads, checksums, deterministic whole-customer sample, chunk validation, exact-field deduplication, quality/lineage manifests, Parquet, DuckDB facts and dimensions |
| Analytics | Date-bounded overview, sales/category trends, customer RFM/cohort indicators, paginated products, session-based basket affinity, data provenance |
| Predictive | Seasonal naive versus recursive HistGradientBoosting forecast; inactivity proxy with temporal/customer-disjoint split; K-Means RFM segments; Isolation Forest session triage |
| Intelligent queries | Allowlisted natural-language intent router over validated analytical methods; no generated SQL execution |
| Reporting | Restricted metrics/dimensions with CSV and PDF exports; spreadsheet formula characters escaped |
| Scenarios | User-entered stock and lead-time assumptions yield a labeled demand-proxy reorder scenario |
| Application | Next.js, TypeScript, Tailwind, ECharts, TanStack Query/Table, accessible controls, themes and synthetic demonstration mode |
| Platform | FastAPI, JWT and Argon2, admin/analyst/viewer roles, migrations, optional Redis/Celery, Docker, tests and GitHub Actions |

See the [architecture decisions](docs/architecture.md), [data pipeline](docs/data-engineering.md), [dataset notes](docs/datasets.md), [API reference](docs/api.md), and [ML methods](docs/ml-methodology.md).

## Architecture

    Source archives → streaming validation → Parquet → DuckDB facts/dimensions
                                                    ├→ bounded analytics → FastAPI → Next.js
                                                    └→ bounded ML → Joblib/metrics → FastAPI
    PostgreSQL stores operational users; Redis provides disposable cache/task queue; Celery runs training.

DuckDB and Parquet handle local analytical scans with bounded memory; PostgreSQL stores operational identity metadata and can receive an indexed warehouse mirror. They are not dual-write synchronized. A refresh should build a separate snapshot and promote it after readers stop. Redis is never the system of record.

## Dataset and rights

Selected source: [REES46 eCommerce Events History in Cosmetics Shop](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop), listed in the [publisher catalogue](https://rees46.com/en/datasets). Source months are October 2019 through February 2020. The publisher advertises approximately **20 million behavior events**. Acquisition manifests separately count raw rows, purchase-event rows, sampled rows, accepted/rejected and inserted rows, plus source checksums. Never substitute sample counts for original event counts.

Kaggle identifies files as © original authors and allows free use with source and REES46 attribution. This is not a permissive software license. Raw downloads remain outside Git; verify source terms before redistribution or commercial use. The code's MIT license does not apply to the dataset. See [dataset documentation](docs/datasets.md) for the candidate comparison, dictionary, definitions and limitations.

## Get a local sample

Python 3.12 is required. The downloader streams monthly records, preserving complete event histories for a deterministic hash sample of users.

    python -m venv .venv
    source .venv/bin/activate
    pip install -e '.[dev]'
    python scripts/acquire.py --modulus 100
    python scripts/ingest.py data/sample.csv --data-dir data --chunk-size 100000
    python scripts/train.py --data-dir data

On Windows, activate with .venv\Scripts\activate and set the .env values in PowerShell before running commands. The customer sample spans all five months and supports temporal labels better than taking the first rows, but it is not a random event sample. To process the complete dataset, extract and ingest each monthly CSV sequentially into one authentic warehouse. Keep synthetic fixtures in a separate data directory.

The standalone website demo uses clearly labeled synthetic data. It is not a real business result or model benchmark.

## Run the application

Copy .env.example to .env, generate a unique signing secret of at least 32 characters, set the local paths and never commit .env. Python commands automatically load the project .env; exported environment variables take precedence. CORS permits localhost, 127.0.0.1 and 0.0.0.0 on port 3000 by default. Set CORS_ORIGINS to a comma-separated list of exact frontend origins for other hosts or ports.

    cp .env.example .env
    mkdir -p data
    alembic upgrade head
    python -m atlas.auth salman --role admin
    uvicorn atlas.api:app --reload

In a second terminal:

    cd web
    npm ci
    npm run dev

Open http://localhost:3000 and sign in with the account you created. The Explore demonstration path does not need a database account. GET /health is public; analytics require a short-lived token. Reports require analyst/admin role and training requires admin. API details are in [docs/api.md](docs/api.md).

Docker Compose starts the API, Next.js, PostgreSQL, Redis and one Celery worker. Set a unique POSTGRES_PASSWORD in the ignored .env first. Bring up storage, migrate and create an admin before starting the full stack:

    docker compose up -d db redis
    docker compose run --rm api alembic upgrade head
    docker compose run --rm -it api python -m atlas.auth salman --role admin
    docker compose up --build -d

Dataset download, ingestion and training remain explicit operator steps.

## Resource limits and benchmarks

Ingestion defaults to 100,000-row pandas chunks. DuckDB uses two threads and a 1 GB cap with disk spill. ML limits feature tables to 30,000 customers and 50,000 purchase sessions, with a 512 MB query budget. Measure a fresh ingest with:

Measured local sample run (30 September 2026): **190,082** authentic input events; **181,296** accepted into the deduplicated warehouse; **8,786** exact duplicates; **0** rejected; **10.71 seconds** end-to-end ingestion; **465.6 MiB** process peak RSS; ten daily aggregate queries had a **1.52 ms median**. This ran on a 9-vCPU Linux cloud runner with DuckDB 1.3.2, Python 3.12.14 and the source sample hash in the benchmark artifact. It is a reproducible sample measurement, not a full-data or 8 GB laptop capacity claim. Details: [benchmark-results.json](docs/benchmark-results.json).

The authentic sample model run compared seasonal naive against HistGradientBoosting on a 30-day time holdout. MAE was 232.88 versus 346.52 source price units, so the baseline was selected. The inactivity classifier's ROC-AUC was 0.494 versus a 0.500 prior baseline on 94 held-out customers, with 90.4% label prevalence; this result has weak discrimination and should not drive actions. Three-cluster RFM silhouette was 0.332 on 457 sampled customers. Isolation Forest flagged 30 of 1,477 purchase sessions for review; no fraud labels exist, so this is not fraud accuracy. These results describe the selected sample only. See [sample-model-evaluation.json](docs/sample-model-evaluation.json) and [methodology](docs/ml-methodology.md).

    python scripts/benchmark.py --data-dir data --csv data/sample.csv

For authenticated API latency, supply a short-lived token in ATLAS_BENCHMARK_TOKEN:

    python scripts/benchmark_api.py --requests 30

Store measurements with hardware, dependencies, source hashes, and sample/full scope. No throughput, latency, memory or model score is claimed until a run produces those values. Cloud build environment results do not represent the user's laptop or a production cluster.

## Verification

    pytest -q
    cd web
    npm run typecheck
    npm run build
    npm run test:e2e

GitHub Actions runs Python tests and frontend build/browser tests on pushes and pull requests. Docker, PostgreSQL, Redis and Chromium are required for their integration paths.

## Security and limitations

- Use a unique signing key and TLS before internet exposure. Keep database and Redis private and restrict CORS.
- Users are created interactively; Argon2 hashes passwords. Never seed shared credentials.
- Dates, identifiers, roles and report dimensions are constrained. Natural-language interpretation selects fixed services, never arbitrary SQL.
- Public demos expose aggregates or fixtures only. The source contains pseudonymous stable customer identifiers; do not publish customer-level rows.
- No third-party security audit, service-level guarantee, multi-tenant isolation or cloud deployment is claimed.
- The source is one anonymous historical cosmetics shop. Profit, geographic analysis, inventory optimization, validated cancellation and fraud classification are impossible without additional labels and columns.
- RFM/churn are behavioral proxies, session identity is not order identity, and forecast uncertainty is not calibrated.
- Measure full-data resource use before setting service targets.

## Next improvements

Build immutable warehouse snapshots and promotion, calibrated forecast intervals, inventory feeds with stockout corrections, labeled fraud/churn outcomes, tenant isolation, telemetry, managed identity and a measured cloud capacity/cost report.

## Repository layout

    src/atlas/          API, authentication, warehouse access and ML
    scripts/            acquisition, ingestion, training and benchmarks
    alembic/            application database migrations
    docs/               data rights, architecture, API and methods
    tests/              ingestion, API and model validation
    web/                Next.js analytics application
    .github/workflows/  automated verification
