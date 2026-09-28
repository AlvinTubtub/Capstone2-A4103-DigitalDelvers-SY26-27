# Frozen Research-Result Evidence

This directory contains deterministic, read-only submission and research evidence derived from the finalized formal evaluation.

- **Formal run:** `FORECASTPH_FORMAL_20260911_01`
- **Formal cutoff:** `2026-09-11`
- **Formal Git SHA:** `8359270bffcd43dd41830a01bb2f4e2d4c527b56`
- **Holdout target dates:** `2025-09-10` through `2026-09-11`
- **Aligned observations:** 246 per company and method

The study covers 15 companies across five sectors, with three companies per sector. It compares Lag-Informed Regression (LIR), ARIMA, and LSTM against a Naive benchmark.

## File guide

### `selected_configurations.csv`

Selected LIR, ARIMA, and LSTM configurations used in the finalized formal evaluation.

### `holdout_metrics.csv`

Common aligned holdout RMSE, MAE, MASE, and R² for LIR, ARIMA, LSTM, and Naive.

### `benchmark_vs_naive_dm.csv`

Principal-model versus Naive Diebold-Mariano benchmark evidence.

### `within_company_dm.csv`

All six model-pair DM comparisons within each company under the declared squared- and absolute-error loss families.

### `across_company_tests.csv`

Across-company MASE Friedman omnibus evidence and the conditional Wilcoxon post-hoc gate. The finalized Friedman statistic is `1.7412587412587377` with raw p-value `0.6278003229833597` at alpha `0.05`. The null was not rejected, so `posthoc_performed` remains false and the pairwise Wilcoxon result set remains empty.

### `principal_winners.csv`

Per-company principal-model winner and best evaluated method. Principal winners use within-company RMSE among LIR, ARIMA, and LSTM; the best evaluated method also includes Naive.

### `principal_win_summary.csv`

Aggregate descriptive winner counts. Principal-model wins are LIR 4, ARIMA 7, and LSTM 4. The strict-majority threshold is 8 of 15, and no principal model reached it. This threshold is descriptive and is not a statistical significance test. Best evaluated method counts including Naive are LIR 3, ARIMA 7, LSTM 4, and Naive 1.

### `sector_peer_summary.csv`

Descriptive company-level summaries within sectors. Pooled or averaged peso RMSE/MAE must not be used to declare an overall cross-company winner.

### `data_quality.csv`

Frozen formal-dataset screening results: 15 PASS and 0 FAIL. APX contains one material-discontinuity REVIEW event; the review is not itself an error, confirmed corporate action, or failed dataset.

### `data_quality_rules.csv`

Frozen `data-quality-v1` screening rules.

### `holdout_predictions.csv`

Canonical row-level frozen holdout ledger for all 15 companies. It exposes actual closes and the stored LIR, ARIMA, LSTM, and Naive one-step predictions on the common 246-session holdout. Origin dates come from the immediately preceding session in each company's frozen formal raw history.

### `formal_scope.csv`

Per-company executed formal scope: frozen raw coverage and row count, one-step forecast-pair count, development and holdout ranges, expanding-window CV split count, forecast horizon, and chronological no-shuffle policy.

These two files expose existing finalized evidence. They do not represent a new experiment, retraining run, refit, or inference run.

### `data_provenance.csv`

Reviewer-facing frozen raw-data provenance for all 15 companies: preserved source identity and reference, retrieval-date metadata, frozen raw SHA-256, formal date range and row count, correction-history count, and finalized trading-session completeness. `source_reference` is the provider-level reference preserved in the formal archive, not a unique archived URL for every report. `retrieval_date` retains the archived batch-log provenance meaning; it is not automatically the cutoff or each row's download date.

### `model_diagnostics.csv`

Stored ARIMA diagnostic evidence: selected fitted-model stability and invertibility, fitted-residual Ljung-Box, and separate complete aligned out-of-sample holdout-error Ljung-Box. The file does not recompute diagnostics or create model-selection evidence. Fitted residuals and holdout forecast errors have different scopes; LIR/LSTM analogues are not fabricated for symmetry.

Phase 6A.2 exposes existing finalized evidence, not a new experiment.

### `results_manifest.csv`

Deterministic file hashes, row counts, provenance fields, and package-integrity metadata.

## Corporate-Action and Material Price-Discontinuity Screening

The supporting package at `corporate_action_screening/` screens the immutable frozen OHLCV files from `FORECASTPH_FORMAL_20260911_01` (cutoff `2026-09-11`), covering `2020-01-02` through `2026-09-11`: 15 companies, 1,635 observations each, and 24,525 observations total. Its threshold is an absolute close-to-close change or opening gap of at least 30%. The independently recomputed result is one statistical flag (APX, `2020-10-16`), six predetermined official-event dates, seven unique documented stock-dates, zero duplicate symbol-dates, and zero records removed or adjusted. No new statistical flag occurred from `2026-07-01` through `2026-09-11`.

This is documentation and data-quality screening, not an OHLCV correction. A material-discontinuity `REVIEW` does not itself mean dataset failure, extraction error, stock split, corporate action, or record removal. The screening does not alter frozen raw OHLCV, finalized forecasts, or model results. The frozen formal CSVs do not contain issue names or traded value; the package explicitly marks source-name continuity and Value_PHP as unavailable rather than inferring them from configured display names or another dataset.

The subpackage has its own `manifest.csv` because it includes Python, JSON, and log evidence in addition to CSVs. The manifest lists each required file and SHA-256 with the formal run/cutoff, without changing the root `results_manifest.csv` CSV-dataset semantics. The research-result validator verifies exact membership, hashes, script-copy identity, and screening totals.

## Safe validation and export

Run the focused validation tests from `backend/` without changing this package:

```bash
python -m pytest -q tests/test_research_result_export.py
```

The exporter supports a deterministic rebuild from finalized formal and linked supplementary evidence. When an independent staging export is required, use a separate output directory:

```bash
python -m scripts.export_research_results \
  --output-dir /tmp/pse-pulse-research-result-check \
  --verbose
```

Do not run the exporter with its default output directory merely to validate committed evidence: the default is this protected directory. The export path validates provenance and cross-file consistency, generates deterministic tables, and maintains `results_manifest.csv`; it does not train, tune, refit, run inference, or generate operational next-session forecasts.

Do not manually edit or reformat generated research-result CSV files.
