# Frontend

Run `cd web && npm ci && npm run dev`. Set `NEXT_PUBLIC_API_URL` before a production build; it defaults to `http://localhost:8000`.

The Next.js application has eight sections: Overview, Sales, Customers, Products, Predictions, Inventory, Reports and Data Explorer. The interface opens in a dark analytical studio theme, with a light option, responsive navigation and the custom Atlas brand mark in `web/public/atlas-mark.png`.

ECharts provides daily, weekly and cumulative purchase trends, a seven-day average, range zoom and PNG export. Additional charts show behavior reach, new/returning purchasers, weekday/hour activity, data coverage, stacked daily events, purchase cohorts, RFM profiles, model holdout performance and historical forecast horizons. Model cards render measured metrics and explicit unavailable states.

TanStack Query isolates connected requests by token and date range. Bearer tokens remain in memory, and passwords are cleared after successful login. Demo mode is explicitly synthetic and does not invent customer cohorts or model evidence. Product filtering/sorting operates on the loaded page. Category selection opens product exploration and filters the loaded page by category text.

A missing warehouse produces a guided setup panel. API detail messages are preserved, and network failures receive connection guidance. Source price units, session proxies and historical scope remain visible. Inventory remains an explicitly assumed scenario because the source has no stock ledger.

See [portfolio.md](portfolio.md) for a reviewer walkthrough and the data/model methodology behind the visualizations.
