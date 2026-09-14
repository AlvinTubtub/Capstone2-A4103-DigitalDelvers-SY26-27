# ForecastPH

ForecastPH is an educational forecasting platform for selected companies listed on the Philippine Stock Exchange (PSE). It validates official end-of-day OHLCV data, evaluates three forecasting model families against a Naive benchmark, refits production models, and publishes next-session forecasts to a Next.js website.

Forecasts are statistical estimates for education and research. They are not investment advice or trading signals.

## Companies and sectors

The configured universe is defined once in `backend/config/companies.py`.

| Sector | Companies |
| --- | --- |
| Financials | BPI, MBT, SECB |
| Industrial | JFC, MER, SHLPH |
| Mining and Oil | APX, NIKL, SCC |
| Property | ALI, MEG, SMPH |
| Services | GLO, ICT, PGOLD |

## Forecasting models

ForecastPH evaluates:

- **Lag-Informed Regression (LIR):** LASSO regression over causal lag, return, volume, range, and technical-indicator features.
- **ARIMA:** a univariate Close-series model selected from a bounded, configuration-driven order grid.
- **LSTM:** a univariate PyTorch sequence model over historical daily Close changes.
- **Naive benchmark:** predicts that the next Close equals the current Close.

LIR, ARIMA, and LSTM are the three deployable principal models. Naive is an evaluation benchmark only.

## Methodology

For every company, the backend constructs one-step forecast pairs:

```text
origin_date  = Date[t]
target_date  = Date[t+1]
target_delta = Close[t+1] - Close[t]
```

The latest approximately 15% of target dates are reserved for evaluation and the earlier approximately 85% are used for development. The split is generated dynamically from the available raw data; it is not tied to a fixed date or row count.

All four methods are evaluated on the same chronological target dates. Model tuning uses expanding-window validation without shuffling, and preprocessing is fitted only on the applicable training block. The backend reports RMSE, MAE, MASE, and R². MASE uses one development-series denominator per company.

The ARIMA search contains 80 valid specifications: `d=0` uses trends `n,c`, `d=1` uses `n,t`, and `d=2` uses `n`, with `p,q=0..3`. This includes no-drift `ARIMA(0,1,0)`. LIR searches the declared LASSO alpha grid through `30.0` and records whether the winner is at the lower boundary, upper boundary, or interior; an unresolved upper-bound winner blocks formal finalization.

The best principal model is the lowest-RMSE choice among LIR, ARIMA, and LSTM. The best evaluated method is reported separately and also includes Naive; an exact RMSE tie is resolved deterministically in canonical order: LIR, ARIMA, LSTM, then Naive. Evaluation remains separate from production refitting: after configurations are selected, all three principal models are freshly refitted on all currently available validated history.

Cross-company reporting does not choose a winner from pooled or averaged peso RMSE/MAE. It uses median MASE, median within-company RMSE rank, win counts, and counts beating Naive. R² is supplementary and is never used for tuning, model selection, or deployment.

Reporting-only statistical comparisons operate on the complete aligned holdout: six within-company Diebold-Mariano pairs under squared- and absolute-error loss use Newey-West variance, the Harvey-Leybourne-Newbold correction, and separate Holm families. Across-company comparison uses MASE with Friedman and conditionally Holm-corrected Wilcoxon tests. These results never tune, refit, promote, or forecast. The live site does not claim statistical significance without finalized formal-run evidence.

## Production architecture

```text
Official PSE OHLCV
        ↓
strict raw-data validation
        ↓
chronological tuning and evaluation
        ↓
full-data production refit
        ↓
persisted production-model artifacts
        ↓
daily PSE EOD ingestion and validation
        ↓
persisted-model inference without retraining
        ↓
atomic frontend JSON export
        ↓
Next.js frontend on Vercel
```

`backend/data/raw/` is the sole modeling input. Generated model, evaluation, forecast, and run artifacts live under the gitignored `backend/artifacts/` tree.

## Fresh training versus daily inference

Fresh training validates raw histories, constructs the evaluation plan, tunes and evaluates all models, saves full-precision out-of-sample evidence, refits all three principal models, creates the production artifact manifest, and exports operational frontend JSON.

Daily operation downloads available PSE EOD reports, validates and idempotently merges new rows, validates the restored artifact package, loads persisted models, performs inference, and refreshes frontend JSON when raw data changed.

After a new actual is validated, daily automation resolves matching prior forecast-ledger outcomes, performs persisted-model inference, appends the three principal forecasts plus Naive, and reports drift evidence. The append-only ledger never rewrites an issued prediction. Drift states use resolved prospective evidence only and cannot trigger training, refitting, promotion, or deployment.

The daily workflow does **not** tune or refit models. It fails closed if a complete compatible production artifact package is unavailable.

## GitHub Actions

Two workflows implement production automation:

- **PSE Fresh Model Training** (`.github/workflows/train_models.yml`) runs quarterly and supports manual `workflow_dispatch`.
- **PSE EOD Update and Persisted Model Forecast** (`.github/workflows/update_pipeline.yml`) is started by the external `update-pse-data` `repository_dispatch` event or manual `workflow_dispatch`; it has no internal cron and performs ingestion and persisted-model inference without training.

Quarterly fresh training is scheduled at 8:00 AM Philippine Time on February 28, May 28, August 28, and November 28.

GitHub Actions stores the complete production-model package as an artifact. Its manifest identifies and validates every expected model and evaluation file before daily inference begins.

## Repository layout

```text
.
├── .github/workflows/       # Quarterly training and daily persisted inference
├── backend/
│   ├── config/              # Company, model, filesystem, and PSE-calendar configuration
│   ├── data/raw/            # Canonical OHLCV histories
│   ├── scripts/             # Validation, ingestion, training, inference, and reset CLIs
│   ├── src/                 # Authoritative backend packages
│   ├── tests/               # Backend and workflow tests
│   └── artifacts/           # Generated and gitignored runtime files
├── docs/
│   ├── frontend-forecast-contract.md
│   └── research-history/    # Archival material; never a production input
└── frontend/
    ├── public/forecasts/    # Generated operational website data
    └── src/                 # Next.js App Router application
```

## Backend commands

Run from `backend/` after installing `requirements.txt`:

```bash
python scripts/validate_raw.py --all --verbose
python scripts/train_all.py --all --fresh --verbose
python scripts/forecast_all.py --all --verbose
python scripts/update_eod.py --verbose
python scripts/reset_artifacts.py --yes
python -m pytest -q
```

`train_all.py --fresh` removes only generated backend artifacts before training. It never removes raw data. A single-company diagnostic run must use `--no-export`, because the production frontend contract requires the complete configured universe.

## Frontend

The frontend is a Next.js 14 App Router application. It reads committed operational JSON from `frontend/public/forecasts/`; it does not run Python or model inference on Vercel.

Current pages and features include Home, Companies, company detail charts, My Watchlist, Models, Learn Stocks, About, the AI assistant, out-of-sample backtests, forecast-error charts, and next-session forecasts.

Run locally from `frontend/`:

```bash
npm install
npm run dev
```

Production validation:

```bash
npm run build
npx tsc --noEmit
```

## Forecast data contract

The current JSON compatibility contract is documented in `docs/frontend-forecast-contract.md`. Generated operational JSON is the website's source of truth. The exporter validates the complete payload and publishes atomically so a failure cannot leave a partially updated dataset.

Company charts show only the latest 60 evaluation sessions for readability. New exports also carry the complete evaluation count and date range; metrics and statistical tests continue to use every aligned evaluation record.

## Formal-run preparation

The opt-in formal subsystem requires a researcher-selected run ID and cutoff date. Its check-only mode performs no training and reports provenance, raw hashes, calendar completeness, Git state, ARIMA-grid validity, and unresolved LASSO boundary evidence. A completed run can move only through `IN_PROGRESS`, `FAILED`, or `FINALIZED`; finalized evidence includes an integrity manifest and cannot be overwritten. No formal experiment is implied by the presence of this infrastructure.

## Historical research

Earlier research and manuscript materials are intentionally archived under `docs/research-history/`. They are retained for academic reference only and are not imported, loaded, or generated by the active backend, frontend pages, chatbot data context, or GitHub Actions workflows.
