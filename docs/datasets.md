# Dataset decision and data contract

Research date: 29 September 2026. Selected source: **REES46 eCommerce Events History in Cosmetics Shop**, published by Michael Kechinov. [Publisher catalogue](https://rees46.com/en/datasets) · [Original dataset and usage terms](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop).

## Selection

The publisher describes approximately **20 million behavioral event rows**, covering October 2019 through February 2020. These are views, cart additions, cart removals, and purchase events—not 20 million orders or customers. This size meets the project target without inflating the data. Five months supports short-horizon forecasting, behavioral segments, and explicitly defined inactivity labels; it does not support annual seasonality claims.

| Candidate | Published scale / grain | Business strengths | Decision |
| --- | --- | --- | --- |
| [Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) | About 100,000 orders, 2016–2018 | Relational orders, items, reviews, payments, geography | Strong BI semantics, below 10M target; do not inflate or combine unrelated businesses to claim scale |
| [H&M](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data) | Multi-million purchase rows; transactions file listed as 3.49 GB | Rich customer/article metadata and purchase history | Strong alternative; Kaggle rules acceptance/sign-in required; exact row count not independently verified in this research |
| [Instacart](https://www.kaggle.com/competitions/instacart-market-basket-analysis/data) | More than 3 million orders; more than 30 million order-product links | Genuine basket relationships, repeat purchase | No prices or absolute calendar dates; unsuitable for this project's revenue/date forecasting core |
| [REES46 multi-category](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store) | Publisher catalogue covers Oct 2019–Apr 2020; exact total not verified here | Same behavioral schema, larger scale option | More download/storage cost; optional future adapter, not silently mixed with cosmetics |
| REES46 cosmetics | Publisher headline approximately 20M event rows | Timestamped behavior, product/category/brand, price, user and session | Selected for a manageable full-scale portfolio build |

## Acquisition and licensing

Kaggle dataset reference: `mkechinov/ecommerce-events-history-in-cosmetics-shop`; API metadata identified version **6**, last updated 2020-03-16, with archive size **450,866,572 bytes** on the research date. Pin this version when downloading. Preserve a SHA-256 digest of every downloaded file in the ingestion manifest. Source dates are historical, not live commerce.

```bash
# Install Kaggle separately if using its CLI. Authentication may be required.
kaggle datasets download -d mkechinov/ecommerce-events-history-in-cosmetics-shop -p data/raw/cosmetics
# Extract CSVs locally, then use the project's ingestion command.
```

Verified public GET endpoint for one monthly ZIP (October returned HTTP 200 and a ZIP header without authentication during this research):
`https://www.kaggle.com/api/v1/datasets/download/mkechinov/ecommerce-events-history-in-cosmetics-shop/2019-Oct.csv?datasetVersionNumber=6`

Replace the filename with each listed month. A HEAD request against the entire archive returned 404 in this environment; do not infer that the working per-file GET is unavailable from that HEAD result. File metadata endpoint:
`https://www.kaggle.com/api/v1/datasets/list/mkechinov/ecommerce-events-history-in-cosmetics-shop`

The dataset's license field is **“Data files © Original Authors”**. The original card permits free use with attribution to its dataset page and REES46. This is not a CC0, MIT, or Apache data license. The application code license does not relicense the data. Link both sources in reports and the demo. Keep bulk raw data out of the source repository; retain source/version attribution for any included derived demo. Review the original card for redistribution/commercial requirements before distributing raw files. No Kaggle credentials belong in Git.

## Original counts versus measured counts

All five original version-6 monthly ZIPs were downloaded and their CSV members streamed completely. Observed raw counts, **before validation or analytical deduplication**, are:

| Original file | Raw event rows | Raw purchase-event rows | Sample event rows |
| --- | ---: | ---: | ---: |
| `2019-Oct.csv` | 4,102,283 | 245,624 | 38,199 |
| `2019-Nov.csv` | 4,635,837 | 322,417 | 46,025 |
| `2019-Dec.csv` | 3,533,286 | 213,176 | 32,146 |
| `2020-Jan.csv` | 4,264,752 | 263,797 | 35,821 |
| `2020-Feb.csv` | 4,156,682 | 241,993 | 37,891 |
| **Total** | **20,692,840** | **1,287,007** | **190,082** |

These are event counts, not distinct orders or customers. The source publisher's 20M headline is rounded. The 190,082-row development sample selects complete observed histories for users whose SHA-256 hash meets the sampling rule; it is not 1% of every day's rows. An approximately 1% user selection can produce a different event proportion because users differ in activity. No synthetic rows were added to this sample.

`data/acquisition.json` records each original ZIP SHA-256, uncompressed CSV SHA-256, download URL, version, compressed size and measured counts. Total downloaded ZIP size is 450,866,660 bytes. The sample CSV SHA-256 is:

```
475c0ed833182a67bbcda0a39cc69ce6806b00d7d2afe3aba3f6f6ea784fa600
```

The full raw scan establishes authentic dataset scale. It does **not** constitute a full 20.7M-row warehouse, API or ML performance benchmark. Analytical counts after validation and duplicate handling may differ; the corresponding data quality report is authoritative for those counts. Benchmarks must state whether they use the raw full source or the customer sample.

## Data dictionary

| Source column | Meaning | Warehouse treatment |
| --- | --- | --- |
| `event_time` | Event timestamp, UTC | Parse UTC; reject invalid/missing; derive calendar dimension |
| `event_type` | `view`, `cart`, `remove_from_cart`, `purchase` | Validate enum; purchase measures filter explicitly |
| `product_id` | Product identifier | Preserve as identifier; product dimension key |
| `category_id` | Category identifier | Preserve numeric-looking ID as string; nullable unknown category |
| `category_code` | Optional category taxonomy | Retain null/unknown; never infer an unobserved category |
| `brand` | Optional brand label | Retain unknown separately |
| `price` | Product price at event time | Validate finite numeric value; retain event-time value; do not sum non-purchase prices as sales |
| `user_id` | Persistent source user identifier | Pseudonymous observed user, not proven person |
| `user_session` | Temporary session identifier | Nullable session key; missing session excluded from order proxy denominator and reported |

The original data card contains an inconsistent table description saying purchase-only; its explicit event-type section lists four types. The pipeline validates the actual event enum instead of assuming purchase-only.

## Business definitions and limitations

- **Purchase-event value** is the sum of valid purchase-event prices. It is a proxy for gross sales, not audited revenue: returns, tax, shipping, discounts and payment settlement are absent.
- **Purchasing sessions** count distinct non-null user/session pairs containing purchase events. The source describes multiple purchase events in a session as one order, but supplies no independent order identifier. Display this proxy explicitly. Its average value uses only purchase events with a valid session in both numerator and denominator.
- **Customers** means observed distinct purchasing user identifiers. All visitors is a different metric.
- **Profit and margin** are unavailable because cost of goods is absent. Do not invent cost percentages.
- **Geographic performance** is unavailable because country, city and coordinates are absent. Do not generate maps from invented locations.
- **Inventory** lacks on-hand stock, replenishments, lead times, stockouts and supplier constraints. Forecast demand proxies and allow labeled user-entered what-if assumptions; do not claim operational inventory optimization from this source alone.
- **Churn** has no subscription cancellation label. Define a forecast horizon for purchase inactivity and require complete future observation; censor incomplete labels at the dataset end. Behavior-based inactivity is not proof of permanent churn.
- **Anomalies** mean statistical outliers, not confirmed fraud. No labeled fraud outcomes exist.
- **Basket analysis** groups purchase events by user/session. It describes co-occurrence, not causation; missing sessions cannot form baskets.
- **Duplicates** have no unique source event ID. Exact repeated source rows may be repeated telemetry or legitimate repeated actions. Report them and document the chosen analytical deduplication policy; do not silently equate row equality with proven fraud or duplicate orders.
- **Time limits**: only five months, one anonymous cosmetics business. No annual seasonality, causal explanations or broad market representativeness claims.

## Local development and provenance

Run `python scripts/acquire.py --modulus 100` to download the five version-6 ZIPs sequentially, stream their rows, and sample complete customer histories using the first eight SHA-256 bytes of `user_id` modulo 100. Outputs are `data/sample.csv` and `data/acquisition.json`; the manifest stores exact raw event and purchase counts plus ZIP/CSV SHA-256 hashes. The script never extracts all CSVs onto disk or loads them into memory. Raw ZIPs total approximately 450 MB. Use a deterministic bounded sample for an 8 GB laptop. A first-N-rows sample is useful for schema tests but chronologically biased; it is not suitable for retention or forecast evaluation. Prefer bounded samples across all monthly files with reproducible rules, and disclose whether sampling keeps whole user histories. Keep synthetic fixtures under a separately named fixture/demo source and never count them toward authentic scale or business results.

The data quality report and manifest—not this document's rounded source headline—are authoritative for executed counts. A successful small-data test demonstrates code behavior, not a 20M-row performance result.
