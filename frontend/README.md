# PSE Pulse frontend

This is the Next.js 14 App Router website for PSE Pulse. It reads generated operational JSON from `public/forecasts/`; model training and inference run in the repository's backend automation, not in Vercel or the browser.

The current public website is [https://pse-pulse.vercel.app/](https://pse-pulse.vercel.app/).

Legacy package and browser-storage identifiers containing `forecastph` remain unchanged for compatibility.

## Local development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Routes

Primary navigation:

- `/` — Home / market overview
- `/companies` — Companies directory
- `/watchlist` — My Watchlist, stored locally in the browser
- `/learn-stocks` — Learn Stocks educational guide
- `/about` — About, project architecture, and limitations

Additional routes:

- `/companies/<SYMBOL>` — company forecast, metrics, and charts
- `/compare` — model comparison / Models dashboard
- `/learn` — redirect to `/learn-stocks`

The `/compare` route remains available but is not part of the primary desktop or mobile navigation.

The AI assistant receives page-aware context built from the same operational forecast documents.

## Forecast data

```text
public/forecasts/
├── companies.json
├── dashboard.json
├── latest.json
├── metrics.json
├── company/<SYMBOL>.json
└── history/<SYMBOL>.json
```

The backend exporter generates and validates this complete tree. See `../docs/frontend-forecast-contract.md` for schemas and cross-file invariants.

The Models page reports the best principal model separately from the best evaluated method, which also includes Naive. Cross-company views use median MASE, within-company ranks, and win counts; raw peso RMSE/MAE do not select an overall winner. Holdout R² is supplementary and may be negative.

Company charts label the latest 60 evaluation sessions as a presentation subset. New company exports carry the complete evaluation session count and date range beside that subset. Full metrics and statistical tests are calculated from the complete aligned evaluation, not from the chart window. Previously published payloads remain readable, but the UI does not invent missing full-evaluation metadata.

Ask AI is grounded in the same operational documents. It distinguishes principal and evaluated winners, applies the development-scale interpretation of MASE, treats R² as supplementary, and does not make statistical-significance claims without finalized formal-run evidence.

Daily publication is driven externally through the backend workflow's `update-pse-data` `repository_dispatch` event (or manual dispatch). The daily path resolves prior prospective outcomes, runs persisted-model inference, appends new ledger forecasts, reports drift evidence, and exports JSON without training or refitting.

## Production validation

```bash
npm run build
npx tsc --noEmit
```

## Vercel

Set the Vercel project Root Directory to `frontend/`. Forecast JSON is committed by the GitHub Actions pipelines before Vercel builds the site. The application does not need a forecasting API or Python runtime.

The AI route requires its configured provider credentials in the deployment environment. Forecast pages themselves read only repository JSON.
