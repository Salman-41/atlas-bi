# Frontend

Run `cd web && npm ci && npm run dev`. Set `NEXT_PUBLIC_API_URL` before the production build to the FastAPI origin. The default is `http://localhost:8000`.

The Next.js App Router application has seven in-workspace sections, dark/light themes, a tablet/mobile navigation drawer, global date inputs, dynamically loaded ECharts, TanStack Query loading and error states, a TanStack product table, reports, and an allowlisted question panel. Local shadcn-style button/card primitives are owned in `src/components/ui`; the button supports Radix Slot composition. Authentication holds the bearer token in memory only and clears the password after success. Refreshing requires sign-in again.

The explicit **Explore demonstration** mode runs without an API and is permanently labeled synthetic. It is a deterministic interface fixture, not an authentic dataset sample, a model benchmark, or a claim of business performance. Values use source price units because the event source does not specify currency. There is no claimed profit, verified order count, stock ledger, or geographic information.

Connected overview, product pagination, basket-affinity pairs, reports, and questions call the API. The customer section renders connected RFM rows and cohort evidence. The prediction section renders registered model evidence returned by the API; methodology cards never invent metrics. Inventory is a local, explicitly assumed lead-time-demand calculator, not a real inventory optimizer. Product table sorting is on the loaded page only. Category selection navigates to product exploration but does not apply category filtering. These are documented product limitations.

Validation: production `npm run build` and `npm run typecheck` passed. `npm run test:e2e` was attempted but the environment has no Chromium executable; installing Chromium returned truncated CDN archives, so browser assertions remain unverified here. Playwright tests cover demonstration provenance, invalid dates, theme, CSV export, PDF availability messaging, inventory assumptions, question behavior, and failed login.
