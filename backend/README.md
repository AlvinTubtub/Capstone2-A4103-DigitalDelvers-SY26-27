# ForecastPH Backend

This directory contains the authoritative ForecastPH data, training, evaluation, production-refit, inference, ingestion, and frontend-export implementation.

## Directory layout

```text
backend/
├── config/             # Companies, models, paths, timezone, and PSE closures
├── data/
│   ├── raw/            # Canonical OHLCV modeling input
│   └── pdf_reports/    # Generated PSE EOD download staging (gitignored)
├── src/
│   ├── artifacts/      # Runtime layout, checksums, and production manifest
│   ├── data/           # Loading, validation, calendar, and split planning
│   ├── evaluation/     # OOS records, metrics, alignment, and ranking
│   ├── export/         # Frontend schemas, validation, and atomic export
│   ├── features/       # Forecast targets and LIR features
│   ├── inference/      # Persisted-model next-session prediction
│   ├── ingestion/      # PSE EOD download, parsing, validation, and merge
│   ├── models/         # LIR, ARIMA, and univariate LSTM
│   └── training/       # CV, tuning, orchestration, and production refit
├── scripts/            # Supported command-line entry points
├── tests/              # Unit, integration, contract, and workflow tests
└── artifacts/          # Generated runtime files (gitignored)
```

## Canonical raw data

`data/raw/<SYMBOL>.csv` is the sole historical modeling input. Company symbols and PSE issue names come from `config/companies.py`; model code does not maintain another company list.

The loader and validator require canonical `YYYY-MM-DD` dates and finite Open, High, Low, Close, and Volume values. They reject duplicate dates, invalid price relationships, negative volume, and malformed observations. They do not forward-fill or backward-fill missing data.

Validate every configured file:

```bash
python scripts/validate_raw.py --all --verbose
```

## Evaluation design

Each adjacent pair of validated sessions produces one next-day target:

```text
origin_date  = Date[t]
target_date  = Date[t+1]
origin_close = Close[t]
actual_close = Close[t+1]
target_delta = Close[t+1] - Close[t]
```

One dynamic company plan reserves approximately 85% of target pairs for development and the newest approximately 15% for evaluation. LIR, ARIMA, LSTM, and Naive must produce forecasts on exactly the same evaluation target dates.

All model selection is chronological. The backend never uses shuffled validation or future-data backfilling.

Evaluation produces canonical out-of-sample prediction records and full-precision RMSE, MAE, MASE, and R². One development-Close MASE denominator is shared by all four methods for a company. The best principal model is the lowest-RMSE result among LIR, ARIMA, and LSTM; the best evaluated method is reported separately and also includes Naive. Exact RMSE ties use canonical order: LIR, ARIMA, LSTM, then Naive. A strict RMSE comparison determines whether the best principal model beat Naive on the held-out dates.

Cross-company summaries use median MASE, median within-company RMSE rank, win counts, and counts beating Naive. Mean raw peso RMSE/MAE never selects an overall winner. R² is retained, including negative values, as a supplementary metric only.

## Model training

### Lag-Informed Regression

LIR predicts next-day `ΔClose`. It uses causal OHLCV-derived candidates, fold-local PACF selection on training returns, a fold-local `StandardScaler`, and LASSO as the final estimator. Alpha is selected by mean expanding-window validation RMSE.

### ARIMA

ARIMA models the chronological Close series. It searches configured orders within `p=0..3`, `d=0..2`, and `q=0..3`, including `(0,d,0)`. Every eligible candidate must complete all expanding-window folds and satisfy convergence requirements. Evaluation updates the fitted state with revealed actuals using `append(..., refit=False)`.

### LSTM

The PyTorch LSTM is univariate: it consumes historical `ΔClose` sequences and predicts the next `ΔClose`. All lookbacks use common validation target dates based on the maximum configured lookback. Each fold uses three configured seeds, fold-local scaling, and an internal chronological stopping tail. Final fitting selects an epoch count, then trains a fresh model and scaler on the complete development block.

## Production refit and artifacts

After evaluation selects model configurations, production refitting creates fresh LIR, ARIMA, and LSTM models from all currently available validated raw history. Production refit never loads an earlier fitted model.

Generated files are stored only under:

```text
artifacts/
├── models/
├── evaluations/
├── forecasts/
└── logs/
```

Model metadata records the schema identity, symbol, family, training cutoff, data-row count, hyperparameters, timestamp, and model checksum. The production manifest validates the complete configured symbol/model set and rejects missing, inconsistent, corrupted, or incompatible artifacts.

Start a complete fresh run:

```bash
python scripts/train_all.py --all --fresh --verbose
```

Useful options:

- `--symbol SYMBOL --no-export` runs one company without publishing an incomplete frontend dataset.
- `--all` processes the complete configured universe.
- `--fresh` clears generated `artifacts/` content before training and prevents fitted-state reuse.
- `--no-export` skips frontend publication.
- `--verbose` enables debug-level structured logs.

Reset generated artifacts without touching raw data:

```bash
python scripts/reset_artifacts.py --yes
```

## Persisted-model inference

Inference loads only compatible models from `artifacts/models/`, verifies their checksums and training boundaries, and creates one next-PSE-session prediction for each principal model. It does not tune or refit.

```bash
python scripts/forecast_all.py --all --verbose
```

The command requires the matching persisted evaluation evidence used by the frontend exporter. A single-symbol inference check must use `--no-export`.

## PSE EOD ingestion

The ingestion pipeline downloads official PSE EDGE quotation PDFs into gitignored `data/pdf_reports/`, parses only configured companies, cleans and validates OHLCV values, and upserts by Date into canonical raw CSVs.

Existing identical rows are idempotent no-ops. Conflicting historical rows fail rather than being overwritten silently. HTTP 404 means that a report is unpublished, a weekend, or a closure and is not itself a fatal failure.

```bash
python scripts/update_eod.py --verbose
python scripts/update_eod.py --start-date 2026-09-01 --end-date 2026-09-10 --verbose
```

Ingestion performs no training, inference, or frontend export.

## PSE calendar

`config/pse_holidays.py` contains the reviewed PSE closure baseline. `PSETradingCalendar` automatically excludes weekends and configured closures. CLI `--holiday YYYY-MM-DD` values are additive emergency overrides.

Review PSE/SCCP notices and add confirmed closures for the next year before year-end. The calendar does not infer an exchange closure merely because a PDF or raw observation is absent.

## Frontend export

The exporter builds the operational `frontend/public/forecasts/` documents from new evaluation results, production forecasts, and validated raw histories. It validates strict JSON, stages the complete payload, and atomically replaces destinations with rollback protection.

Validate the committed frontend data without regenerating it:

```bash
python scripts/validate_frontend_forecasts.py --verbose
```

## Production artifact validation

GitHub Actions creates and restores the production-model package. Validate a restored package with:

```bash
python scripts/validate_production_artifacts.py --verbose
```

The daily workflow fails closed when a complete compatible package and manifest cannot be verified.

## Tests

Install dependencies and run the suite from `backend/`:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Library modules use `logging.getLogger(__name__)`. CLI entry points configure structured logging so imports do not attach global handlers or retain stale test-capture streams.
