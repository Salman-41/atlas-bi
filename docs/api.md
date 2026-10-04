# API contracts and security

Start with `alembic upgrade head`, then `python -m atlas.auth yourname --role admin` (interactive password). Set `ATLAS_JWT_SECRET` to at least 32 random characters. API process: `uvicorn atlas.api:app --host 0.0.0.0 --port 8000`. OpenAPI lives at `/docs`. Export environment values before running; Compose loads `.env`.

Local operational storage uses SQLite; production uses `ATLAS_DATABASE_URL=postgresql+psycopg://...`. `ATLAS_REDIS_URL` enables overview caching and background tasks. `ATLAS_DATA_DIR` defaults to `data`. Worker: `celery -A atlas.tasks:celery worker --concurrency=1 --loglevel=info`.

`POST /api/auth/login` accepts `{username,password}` and returns a bearer access token expiring after 30 minutes. Send it as `Authorization: Bearer TOKEN`. Tokens contain user identity; roles are reloaded from the database on every request. No default account or signing key is provided. Roles: viewer reads analytics, analyst also exports reports, admin also enqueues training. Reverse proxy TLS and distributed login rate limiting are deployment requirements; password reset and SSO are not implemented.

All analytical GET routes accept ISO `start` and `end` (inclusive dates); reversed ranges and ranges longer than ten years fail with 422. Defaults cover October 2019 through February 2020. Warehouse absence returns 503, never fabricated data.

| Route | Result |
|---|---|
| GET /health | Public liveness only |
| GET /api/overview | kpis, trend, categories, provenance |
| GET /api/products | items, total, page, page_size, provenance; page_size max 100 |
| GET /api/baskets | top product-pair co-occurrences, session-proxy confidence and lift, provenance; minimum support and result limit are bounded |
| GET /api/customers | top 100 RFM customers, monthly observed cohorts, provenance |
| GET /api/predictions | status, models from models/metrics.json, limitations |
| POST /api/reports | metric, dimension, format=json/csv/pdf, start, end; max 1000 aggregate rows |
| POST /api/ask | question, start, end; deterministic supported intents with evidence |
| POST /api/inventory | product_id, stock_on_hand, lead_time_days, service_factor, start, end |
| POST /api/jobs/train | Admin only; returns queued Celery job ID |

Report metrics are purchase_value/events/purchase_sessions; dimensions day/category/brand/event_type. These values select constant SQL fragments. User dates, product identifiers and pagination use bound parameters. CSV source strings starting with spreadsheet formula prefixes are escaped. Reports are computed and exported, not persisted as saved dashboards.

Inventory is explicitly a Poisson purchase-event scenario using user-supplied stock and lead time. The dataset has neither quantity nor warehouse inventory. No cost/profit or geography is inferred. The ask endpoint provides observed purchase performance, product ranking and model availability; it refuses unsupported questions. It does not establish causality, segment attribution, or an unsupported forecast horizon.

Four API tests cover authentication, role restrictions, allowlist injection, date/pagination bounds, missing warehouse, observed aggregate calculations, CSV escaping, PDF generation and inventory scenario labeling. Redis outages bypass cache. Deployment must serialize ingestion with analytical readers because DuckDB is a single-process writer; serve immutable warehouse snapshots for concurrent production refreshes.

`GET /api/insights?start=YYYY-MM-DD&end=YYYY-MM-DD` requires authentication and returns an equally sized previous-period comparison, distinct-customer reach by event type, daily event mix, weekday/hour activity, brand purchase contribution, first-observed versus returning purchasers, coverage, warehouse scope and provenance. `comparison.available` is false if the preceding window extends beyond the dataset's observed bounds. The endpoint executes predefined, parameterized analytical queries.
