# PSE Pulse Backend

This directory contains the authoritative PSE Pulse data, training, evaluation, production-refit, inference, ingestion, and frontend-export implementation.

The public brand does not replace compatibility-sensitive internal identifiers. Existing `forecastph.*` schema IDs, `forecastph-v1-*` forecast IDs, artifact names, formal and supplementary run IDs, module paths, and Python packages remain unchanged.

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
│   ├── formal/         # Explicit formal-run readiness and immutable archives
│   ├── inference/      # Persisted-model next-session prediction
│   ├── ingestion/      # PSE EOD download, parsing, validation, and merge
│   ├── ledger/         # Append-only prospective forecast evidence
│   ├── models/         # LIR, ARIMA, and univariate LSTM
│   ├── monitoring/     # Reporting-only prospective drift evidence
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
python -m scripts.validate_raw --all --verbose
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

Reporting-only inference uses the complete date-aligned evaluation records. Each company receives six pairwise Diebold-Mariano comparisons under squared- and absolute-error loss with Newey-West variance, Harvey-Leybourne-Newbold correction, and separate Holm families. Across-company comparison uses MASE in a Friedman test and runs Holm-corrected pairwise Wilcoxon tests only after a significant Friedman result. These tests do not participate in tuning, production selection, refitting, or daily inference.

## Model training

### Lag-Informed Regression

LIR predicts next-day `ΔClose`. It uses causal OHLCV-derived candidates, fold-local PACF selection on training returns, a fold-local `StandardScaler`, and LASSO as the final estimator. Alpha is selected by mean expanding-window validation RMSE from the declared grid ending at `3.0`, `10.0`, and `30.0`. Metadata classifies the winner as lower boundary, upper boundary, or interior; formal readiness rejects an unresolved upper-bound winner.

### ARIMA

ARIMA models the chronological Close series. Its 80-specification grid uses `p,q=0..3`, `d=0` with `n,c`, `d=1` with `n,t`, and `d=2` with `n`; no-drift `ARIMA(0,1,0)` is eligible. Every candidate must complete all expanding-window folds and satisfy convergence requirements. Evaluation updates the fitted state with revealed actuals using `append(..., refit=False)`. Selected-fit evidence separately records AR/MA roots and moduli, stability/invertibility, fitted-residual ACF and Ljung-Box, and holdout-error Ljung-Box diagnostics.

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
python -m scripts.train_all --all --fresh --verbose
```

Useful options:

- `--symbol SYMBOL --no-export` runs one company without publishing an incomplete frontend dataset.
- `--all` processes the complete configured universe.
- `--fresh` clears generated `artifacts/` content before training and prevents fitted-state reuse.
- `--no-export` skips frontend publication.
- `--verbose` enables debug-level structured logs.

Reset generated artifacts without touching raw data:

```bash
python -m scripts.reset_artifacts --yes
```

## Persisted-model inference

Inference loads only compatible models from `artifacts/models/`, verifies their checksums and training boundaries, and creates one next-PSE-session prediction for each principal model. It does not tune or refit.

```bash
python -m scripts.forecast_all --all --verbose
```

The command requires the matching persisted evaluation evidence used by the frontend exporter. A single-symbol inference check must use `--no-export`.

## PSE EOD ingestion

The ingestion pipeline downloads official PSE EDGE quotation PDFs into gitignored `data/pdf_reports/`, parses only configured companies, cleans and validates OHLCV values, and upserts by Date into canonical raw CSVs.

Existing identical rows are idempotent no-ops. Conflicting historical rows fail rather than being overwritten silently. HTTP 404 means that a report is unpublished, a weekend, or a closure and is not itself a fatal failure.

```bash
python -m scripts.update_eod --verbose
python -m scripts.update_eod --start-date 2026-09-01 --end-date 2026-09-10 --verbose
```

Ingestion performs no training, inference, or frontend export.

## PSE calendar

`config/pse_holidays.py` contains the reviewed PSE closure baseline. `PSETradingCalendar` automatically excludes weekends and configured closures. CLI `--holiday YYYY-MM-DD` values are additive emergency overrides.

Review PSE/SCCP notices and add confirmed closures for the next year before year-end. The calendar does not infer an exchange closure merely because a PDF or raw observation is absent.

## Frontend export

The exporter builds the operational `frontend/public/forecasts/` documents from new evaluation results, production forecasts, and validated raw histories. It validates strict JSON, stages the complete payload, and atomically replaces destinations with rollback protection.

Each new company payload describes both the complete evaluation count/date range and the latest 60-session display subset. Charts use only that subset for readability; canonical metrics and statistical tests remain based on every complete aligned evaluation record.

Validate the committed frontend data without regenerating it:

```bash
python -m scripts.validate_frontend_forecasts --verbose
```

## Production artifact validation

GitHub Actions creates and restores the production-model package. Validate a restored package with:

```bash
python -m scripts.validate_production_artifacts --verbose
```

The daily workflow fails closed when a complete compatible package and manifest cannot be verified.

## Formal evaluation runs

Formal evaluation is an explicit, isolated research lifecycle. It does not replace
production training, inference, or frontend export. Every invocation requires a
human-selected run ID and cutoff date; the backend never chooses either value.

Run the read-only readiness check first:

```bash
python -m scripts.run_formal_experiment \
  --run-id research-run-001 \
  --cutoff-date YYYY-MM-DD \
  --check-only
```

Check-only mode does not create an archive or call model training. It reports raw
hashes, calendar-session gaps, missing provenance, Git state, ARIMA-grid validity,
LASSO upper-bound concerns, and run-ID availability. The intentionally empty
`config/formal_provenance.json` and `config/corporate_actions.json` registries must
only be populated from externally verified sources. Unknown source fields remain
null and prevent formal readiness; they are never inferred from filenames or data.

An approved non-check invocation writes only beneath
`artifacts/evaluations/formal-runs/<RUN_ID>/`. Runs move from `IN_PROGRESS` to either
`FAILED` or `FINALIZED`. Finalization requires every configured company, frozen raw
CSV snapshots, complete model/evaluation evidence, cross-company statistics, and
logs. A finalized run cannot be reused or changed through the archive API, and its
integrity manifest detects modified, deleted, or added files.

## Prospective forecast ledger and drift monitoring

`data/forecast_ledger/events.jsonl` is the append-only production evidence stream.
It contains `forecast_issued` and `forecast_outcome_observed` events. A forecast ID
is the SHA-256 identity of its schema version, symbol, origin date, target date, and
method. This creates one immutable issuance slot per method and session; model
version changes cannot bypass an already-issued slot. Exact semantic retries are
idempotent, while changed predictions, model metadata, or outcomes fail.

After a new EOD row is validated, the daily workflow first resolves pending events
on that exact target date. It then runs persisted-model inference and appends the
three principal forecasts plus a prospective Naive forecast equal to the latest
known Close. Production artifact run ID, source commit, and model version/checksum
are preserved with each issuance. Outcomes are separate events and never rewrite
issued predictions.

The drift monitor reads resolved prospective events only. For each principal model,
it reports rolling MAE, signed error (bias), Naive MAE, the MAE ratio to Naive, and
the count/proportion of sessions with lower absolute error than Naive. Operational
defaults in `config/ledger_config.py` use 20-session review and 60-session
consideration windows. `INSUFFICIENT_DATA`, `OK`, `WATCH`, and `DRIFT_SIGNAL` are
reporting states, not automatic training, refitting, promotion, or deployment
decisions. Candidate deployment remains unapproved without a separate manual
decision; insufficient evidence returns `INSUFFICIENT_PROSPECTIVE_EVIDENCE`.

The two workflow operations can also be run explicitly after their corresponding
EOD stages:

```bash
python -m scripts.update_forecast_ledger --resolve-outcomes --all --verbose
python -m scripts.update_forecast_ledger --issue-forecasts --all --verbose
python -m scripts.update_forecast_ledger --report-drift --all --verbose
```

GitHub Actions receives the external `update-pse-data` `repository_dispatch` event
or a manual `workflow_dispatch`. The EOD workflow contains no internal schedule and
performs no training, tuning, refitting, or formal statistical experiment.

## Tests

Install dependencies and run the suite from `backend/`:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Library modules use `logging.getLogger(__name__)`. CLI entry points configure structured logging so imports do not attach global handlers or retain stale test-capture streams.
