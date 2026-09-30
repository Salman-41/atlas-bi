# Data engineering

`python -m scripts.ingest SOURCE.csv.gz --data-dir data --chunk-size 100000` ingests a locally acquired REES46 file. The source is streamed twice: once for SHA-256 provenance, once for chunked parsing. No complete CSV is held in RAM. Compressed gzip CSV is supported. Exact column names are required; unexpected extra columns are ignored.

## Contracts and integrity

The warehouse is `ATLAS_DATA_DIR/warehouse.duckdb` (default `data/warehouse.duckdb`). DuckDB uses two threads, a 1 GB execution memory budget, and a disk spill directory. The pandas chunk and Python runtime are additional memory, so the 1 GB setting is not a process RSS limit. Default 100,000 rows can be lowered on constrained systems.

Each event has timestamp (UTC normalized, stored without timezone), event type, product and customer identifiers, optional category/brand/session, observed nonnegative price and SHA-256 canonical event identity. Category IDs are parsed as integers directly, never through floating point. Missing category/brand/session values are preserved, not imputed into invented categories. Missing identifiers, malformed timestamps, invalid prices and unknown event types are rejected and counted by reason. Reason counts can overlap. No rejected raw customer records are exported.

The fact table primary key deduplicates identical canonical events across chunks and source files. The dataset lacks an authoritative event ID, so two genuinely distinct identical events may collapse: this is a documented measurement limitation. Source checksums ensure an identical file is skipped regardless of its filename. A changed source is merged as new events; updates/deletions to earlier observations are not inferred. This is append-only incremental ingestion, not CDC.

`dim_product`, `dim_customer` and `dim_date` provide a star schema. Product attributes use deterministic minimum non-null values, not historical slowly changing dimensions. Dimensions rebuild once after each file within the same transaction, retaining primary keys. This avoids repeated indexed updates in DuckDB 1.2.x; full dimension refresh is a scalability trade-off. Customer first/last observation times derive from committed facts. `daily_metrics` is a consistent aggregate view rather than a stale cached table. High-volume deployments should materialize frequently requested aggregates according to their refresh SLA.

## Storage, lineage and recovery

Only newly accepted events enter source-specific Zstandard Parquet partitions. A single database transaction encloses each file load and dimension updates. The staging Parquet directory is renamed before the ingestion ledger commits. A failure rolls back database changes; a crash between rename and commit can leave an unreferenced directory. Retrying the same checksum safely replaces that orphan. Readers should use the committed `ingestion_runs.parquet_path` manifest, not blindly glob all directories. Do not run concurrent writers: serialize ingests through the worker queue.

The committed ledger contains source basename, content checksum, counts, transformation version and quality report. JSON quality artifacts mirror that ledger. The checksum directory is source lineage, not a time partition; it avoids producing thousands of tiny per-day files from chronological chunks. Raw source files remain immutable and separate from derived outputs.

The synthetic fixture generator requires `synthetic` in its output filename and exists solely for repeatable integration tests. Synthetic data must live in a separate warehouse directory. Synthetic outcomes are never portfolio business findings or evidence of model quality.

## Scale boundaries

Parquet and DuckDB provide a practical local analytical warehouse with no PostgreSQL server required for sample mode. Full-file transactions and exact global deduplication need sufficient disk, including temporary spill and transaction storage. Millions-of-row throughput has to be measured with the included benchmark procedure; code structure alone is not a benchmark. Production deployments should enforce disk quotas, schedule ingestion, retain backups and restrict raw IDs to trusted analysts. Customer identifiers are pseudonymous, not proof that a dataset is non-personal.

## Optional PostgreSQL warehouse

`DATABASE_URL=postgresql+psycopg://... python -m scripts.ingest SOURCE.csv.gz --load-postgres` mirrors the DuckDB facts into a dedicated `atlas_warehouse` schema using bounded 10,000-row psycopg COPY batches. Fact event IDs provide an idempotent merge; timestamp/event type, customer/timestamp and product/timestamp indexes support common filters. Star dimensions refresh transactionally. This export currently scans all local facts and ignores previously existing IDs; it is correct but intentionally conservative. A production incremental export should maintain a per-destination source-manifest watermark. PostgreSQL dimensions use deterministic minimum non-null product attributes (not temporal SCD). This path requires a running PostgreSQL service and psycopg v3; it is not claimed verified when those services are unavailable.
