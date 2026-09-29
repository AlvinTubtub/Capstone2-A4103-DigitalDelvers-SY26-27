#!/usr/bin/env bash
set -euo pipefail

# Run from the repository's backend/ directory.
# This script intentionally runs the Chapter-IV-focused targeted validation groups,
# not the full pytest suite.

python -m pytest --collect-only -q

python -m pytest -q \
  tests/test_data_foundation.py \
  tests/test_data_quality_screening.py \
  tests/test_targets_and_split.py \
  tests/test_formal.py

python -m pytest -q \
  tests/test_lag_regression.py \
  tests/test_arima.py \
  tests/test_arima_diagnostics.py \
  tests/test_lstm.py \
  tests/test_model_selection.py \
  tests/test_evaluation.py \
  tests/test_statistical_tests.py

python -m pytest -q \
  tests/test_frontend_exporter.py \
  tests/test_frontend_validation.py \
  tests/test_reporting_semantics.py

python -m pytest -q \
  tests/test_production_inference.py \
  tests/test_forecast_ledger.py \
  tests/test_drift_monitoring.py \
  tests/test_production_manifest.py \
  tests/test_workflows.py

python -m pytest -q \
  tests/test_calendar.py \
  tests/test_ingestion.py \
  tests/test_artifacts.py \
  tests/test_formal_display_export.py \
  tests/test_production_history_export.py \
  tests/test_change_diagnostics.py \
  tests/test_arima_diagnostic_reconstruction.py \
  tests/test_lstm_training_history.py \
  tests/test_clean_imports.py

# Corporate-action tests require the frozen formal-run archive expected by the test.
python -m pytest -q tests/test_corporate_action_screening.py
