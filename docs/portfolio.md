# Atlas BI — portfolio walkthrough

Atlas turns a five-month cosmetics commerce event history into an auditable analytics product. The portfolio story is the full workflow: raw source files → deterministic customer sampling → validated, deduplicated events → DuckDB and Parquet → authenticated analytics → interactive charts → evaluated models.

## A useful demonstration route

1. **Overview:** inspect purchase value, session proxies and purchasing customers. Switch the trend between daily, weekly and cumulative views. Toggle the seven-day moving average and zoom into a date range.
2. **Sales:** choose November to compare against an equally sized preceding period. Explore daily event mix, customer reach and leading brands. Comparisons outside the loaded history are marked unavailable.
3. **Customers:** inspect monthly purchase cohorts and RFM profiles. Retention divides a month's observed purchasing customers by the cohort's first-month purchasers. Unobserved future months remain blank.
4. **Products:** inspect contribution, sort the loaded page, search products/categories and review co-purchased pairs with support, confidence and lift.
5. **Predictions:** compare forecast holdout errors with a seasonal baseline, inspect observed-versus-predicted values, and read the model limitations. Inspect inactivity classification, RFM clustering and anomaly review metrics.
6. **Data Explorer:** inspect source scope, exact loaded counts, coverage and activity by weekday/hour. Chart downloads produce standalone PNGs; reporting supports CSV and PDF.

## What the charts establish

- Source price units are not an assumed currency. Purchase-event value is not audited revenue or profit.
- A customer/session pair is a proxy, not a verified order identifier.
- View/cart/purchase counts describe overlapping customer reach, not a sequential funnel conversion rate.
- A new customer means the first purchase observed in this dataset, not necessarily a first purchase ever.
- Activity heatmaps use the source timestamps without guessing a customer's local timezone.
- A historical forecast begins after the dataset cutoff; it is not a forecast for the present date.
- Model holdout scores and baselines matter more than presenting a complex model as automatically better.

## Reproduce the expanded dataset

The acquisition pipeline uses version 6 of the REES46 cosmetics source and retains complete event histories for a deterministic user sample across October 2019–February 2020. `--modulus 10` selects roughly 10% of user identifiers. Exact sample counts differ from 10% of events because users have different activity levels.

```bash
python scripts/acquire.py --modulus 10
python scripts/ingest.py data/sample.csv --data-dir data --chunk-size 100000
python scripts/train.py --data-dir data --output-dir data/models
```

The acquisition manifest records original row counts and source checksums. Ingestion records rejected rows, duplicate counts, the canonical event identity transformation and the Parquet snapshot path. Preserve the existing warehouse while preparing a larger snapshot in a separate directory; promote only a completed, closed database file.

Raw downloads, databases and model binaries stay out of Git. The dataset is attributed to REES46 and its original authors; it is separate from the code's MIT license. See [datasets.md](datasets.md) for source context and limitations.
