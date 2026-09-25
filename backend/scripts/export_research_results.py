"""Export frozen formal selections and holdout metrics to deterministic CSV files."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import csv
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Final

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.companies import COMPANIES, Company
from config.settings import BACKEND_ROOT, SETTINGS
from src.data.calendar import PSETradingCalendar
from src.data.quality_screening import (
    DataQualityScreeningError,
    RULE_VERSION,
    screen_ohlcv_rows,
)
from src.evaluation.supplementary_archive import SupplementaryEvidenceArchive
from src.formal.archive import FormalRunArchive
from src.formal.provenance import load_corporate_action_registry, sha256_file
from src.logging_config import configure_structured_logging


LOGGER = logging.getLogger(__name__)

FORMAL_RUN_ID: Final[str] = "FORECASTPH_FORMAL_20260911_01"
FORMAL_CUTOFF: Final[str] = "2026-09-11"
FORMAL_GIT_SHA: Final[str] = "8359270bffcd43dd41830a01bb2f4e2d4c527b56"
FORMAL_AGGREGATE_SHA256: Final[str] = (
    "c6991b3b9fa79f0eccb1761f8c40f87a79996646e2ec0eafe5a769c538be05f9"
)
SUPPLEMENTARY_PACKAGE_ID: Final[str] = "FORECASTPH_SUPPLEMENTARY_20260921_03"
HOLDOUT_START: Final[str] = "2025-09-10"
HOLDOUT_END: Final[str] = "2026-09-11"
HOLDOUT_OBSERVATIONS: Final[int] = 246
FORMAL_START: Final[str] = "2020-01-02"
FORMAL_ROWS_PER_COMPANY: Final[int] = 1_635
FORMAL_TOTAL_ROWS: Final[int] = 24_525
METHODS: Final[tuple[str, ...]] = ("lag_reg", "arima", "lstm", "naive")
PRINCIPAL_METHODS: Final[tuple[str, ...]] = METHODS[:3]
LOSS_TYPES: Final[tuple[str, ...]] = ("squared_error", "absolute_error")
METHOD_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("lag_reg", "arima"),
    ("lag_reg", "lstm"),
    ("lag_reg", "naive"),
    ("arima", "lstm"),
    ("arima", "naive"),
    ("lstm", "naive"),
)
SELECTION_CRITERION: Final[str] = "mean_validation_rmse"
TIE_POLICY_PREFIX: Final[str] = (
    "Exact RMSE ties are ordered deterministically as lag_reg, arima, lstm, naive."
)

DEFAULT_FORMAL_RUNS_ROOT = SETTINGS.artifacts_dir / "evaluations" / "formal-runs"
DEFAULT_SUPPLEMENTARY_RUNS_ROOT = (
    SETTINGS.artifacts_dir / "evaluations" / "supplementary-runs"
)
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "research-result"

CONFIGURATION_COLUMNS: Final[tuple[str, ...]] = (
    "symbol",
    "company_name",
    "sector",
    "lir_selected_alpha",
    "lir_selected_features",
    "lir_selected_feature_count",
    "lir_selection_mean_validation_rmse",
    "lir_alpha_grid_boundary_status",
    "arima_p",
    "arima_d",
    "arima_q",
    "arima_trend",
    "arima_drift_enabled",
    "arima_selection_mean_validation_rmse",
    "arima_convergence_status",
    "lstm_lookback",
    "lstm_hidden_size",
    "lstm_learning_rate",
    "lstm_batch_size",
    "lstm_selection_mean_validation_rmse",
    "lstm_validation_rmse_std",
    "lstm_selected_epoch_count",
    "lstm_tuning_seeds",
    "lstm_final_seed",
    "selection_criterion",
    "cv_splits",
    "formal_run_id",
    "formal_cutoff",
    "formal_git_sha",
)

METRIC_COLUMNS: Final[tuple[str, ...]] = (
    "symbol",
    "company_name",
    "sector",
    "method",
    "holdout_start",
    "holdout_end",
    "observation_count",
    "rmse",
    "mae",
    "mase",
    "r2",
    "mase_denominator",
    "best_principal_model",
    "best_evaluated_method",
    "best_principal_beats_naive",
    "all_principals_worse_than_naive",
    "formal_run_id",
    "formal_cutoff",
    "formal_git_sha",
)

BENCHMARK_DM_COLUMNS: Final[tuple[str, ...]] = (
    "symbol", "company_name", "sector", "model", "benchmark", "loss_type",
    "sample_size", "mean_loss_differential", "loss_difference_direction",
    "dm_statistic", "raw_p_value", "holm_adjusted_p_value", "reject",
    "available", "unavailable_reason", "hac_lag", "forecast_horizon",
    "hln_correction_factor", "formal_run_id", "formal_cutoff", "formal_git_sha",
    "evidence_source",
)

WITHIN_COMPANY_DM_COLUMNS: Final[tuple[str, ...]] = (
    "symbol", "company_name", "sector", "model_1", "model_2", "loss_type",
    "sample_size", "mean_loss_differential", "dm_statistic", "raw_p_value",
    "holm_adjusted_p_value", "reject", "available", "unavailable_reason",
    "hac_lag", "forecast_horizon", "hln_correction_factor", "holm_family_size",
    "formal_run_id", "formal_cutoff", "formal_git_sha",
    "supplementary_package_id", "evidence_source",
)

ACROSS_COMPANY_COLUMNS: Final[tuple[str, ...]] = (
    "test_level", "test_name", "metric", "model_1", "model_2", "company_count",
    "statistic", "raw_p_value", "holm_adjusted_p_value", "alpha", "reject",
    "performed", "difference_direction", "median_difference", "mean_difference",
    "std_difference", "skewness", "positive_count", "negative_count", "zero_count",
    "sign_test_p_value", "formal_run_id", "formal_cutoff", "formal_git_sha",
    "supplementary_package_id", "evidence_source",
)

PRINCIPAL_WINNER_COLUMNS: Final[tuple[str, ...]] = (
    "symbol", "company_name", "sector", "lag_reg_rmse", "arima_rmse", "lstm_rmse",
    "naive_rmse", "lag_reg_rank", "arima_rank", "lstm_rank",
    "best_principal_model", "best_principal_rmse", "best_evaluated_method",
    "best_evaluated_rmse", "best_principal_beats_naive",
    "all_principals_worse_than_naive", "winner_selection_metric", "tie_policy",
    "formal_run_id", "formal_cutoff", "formal_git_sha",
)

SECTOR_PEER_COLUMNS: Final[tuple[str, ...]] = (
    "sector", "symbol", "company_name", "best_principal_model",
    "best_evaluated_method", "best_principal_beats_naive", "lag_reg_rmse",
    "arima_rmse", "lstm_rmse", "naive_rmse", "lag_reg_mase", "arima_mase",
    "lstm_mase", "naive_mase", "lag_reg_rmse_rank", "arima_rmse_rank",
    "lstm_rmse_rank", "lag_reg_vs_naive_squared_status",
    "arima_vs_naive_squared_status", "lstm_vs_naive_squared_status",
    "lag_reg_vs_naive_absolute_status", "arima_vs_naive_absolute_status",
    "lstm_vs_naive_absolute_status", "formal_run_id", "formal_cutoff",
    "formal_git_sha",
)

DATA_QUALITY_COLUMNS: Final[tuple[str, ...]] = (
    "symbol", "company_name", "sector", "start_date", "end_date", "row_count",
    "required_columns_status", "numeric_validity_status", "positive_price_status",
    "ohlc_relationship_status", "negative_volume_count", "duplicate_date_count",
    "basic_validity_status", "expected_session_count", "observed_session_count",
    "missing_session_count", "unexpected_session_count", "continuity_status",
    "zero_volume_count", "zero_volume_rate", "zero_volume_status",
    "unchanged_close_count", "identical_ohlc_transition_count",
    "max_identical_ohlc_run", "max_identical_ohlc_run_start",
    "max_identical_ohlc_run_end", "stale_price_status", "active_session_count",
    "active_session_rate", "median_volume", "median_close_value_proxy",
    "liquidity_status", "material_discontinuity_count", "max_absolute_return",
    "max_absolute_return_date", "material_discontinuity_dates",
    "material_discontinuity_status", "dataset_quality_status",
    "screening_review_required", "formal_run_id", "formal_cutoff",
    "formal_git_sha", "rule_version",
)

DATA_QUALITY_RULE_COLUMNS: Final[tuple[str, ...]] = (
    "rule_name",
    "rule_category",
    "measurement",
    "pass_condition",
    "review_condition",
    "fail_condition",
    "threshold_value",
    "threshold_unit",
    "effect_on_dataset_quality",
    "rule_version",
    "notes",
    "formal_run_id",
    "formal_cutoff",
    "formal_git_sha",
)

PRINCIPAL_WIN_SUMMARY_COLUMNS: Final[tuple[str, ...]] = (
    "model",
    "win_count",
    "total_companies",
    "win_share",
    "strict_majority_threshold",
    "strict_majority_achieved",
    "overall_majority_model",
    "selection_metric",
    "interpretation",
    "formal_run_id",
    "formal_cutoff",
    "formal_git_sha",
)

MANIFEST_COLUMNS: Final[tuple[str, ...]] = (
    "filename",
    "purpose",
    "row_count",
    "column_count",
    "sha256",
    "formal_run_id",
    "formal_cutoff",
    "formal_git_sha",
    "formal_archive_sha256",
    "supplementary_package_id",
    "rule_version",
    "source_scope",
    "validation_status",
    "package_content_sha256",
)

HOLDOUT_PREDICTION_COLUMNS: Final[tuple[str, ...]] = (
    "symbol", "company_name", "sector", "origin_date", "target_date",
    "actual_close", "lag_reg_prediction", "arima_prediction",
    "lstm_prediction", "naive_prediction", "formal_run_id", "formal_cutoff",
    "formal_git_sha",
)

FORMAL_SCOPE_COLUMNS: Final[tuple[str, ...]] = (
    "symbol", "company_name", "sector", "raw_start", "raw_end",
    "raw_row_count", "forecast_pair_count", "development_start",
    "development_end", "development_pair_count", "holdout_start",
    "holdout_end", "holdout_pair_count", "cv_split_count",
    "forecast_horizon", "shuffle_used", "formal_run_id", "formal_cutoff",
    "formal_git_sha",
)

SUBSTANTIVE_FILE_ORDER: Final[tuple[str, ...]] = (
    "selected_configurations.csv",
    "holdout_metrics.csv",
    "benchmark_vs_naive_dm.csv",
    "within_company_dm.csv",
    "across_company_tests.csv",
    "principal_winners.csv",
    "principal_win_summary.csv",
    "sector_peer_summary.csv",
    "data_quality.csv",
    "data_quality_rules.csv",
    "holdout_predictions.csv",
    "formal_scope.csv",
)

SUBSTANTIVE_FILE_SCHEMAS: Final[Mapping[str, tuple[str, ...]]] = {
    "selected_configurations.csv": CONFIGURATION_COLUMNS,
    "holdout_metrics.csv": METRIC_COLUMNS,
    "benchmark_vs_naive_dm.csv": BENCHMARK_DM_COLUMNS,
    "within_company_dm.csv": WITHIN_COMPANY_DM_COLUMNS,
    "across_company_tests.csv": ACROSS_COMPANY_COLUMNS,
    "principal_winners.csv": PRINCIPAL_WINNER_COLUMNS,
    "principal_win_summary.csv": PRINCIPAL_WIN_SUMMARY_COLUMNS,
    "sector_peer_summary.csv": SECTOR_PEER_COLUMNS,
    "data_quality.csv": DATA_QUALITY_COLUMNS,
    "data_quality_rules.csv": DATA_QUALITY_RULE_COLUMNS,
    "holdout_predictions.csv": HOLDOUT_PREDICTION_COLUMNS,
    "formal_scope.csv": FORMAL_SCOPE_COLUMNS,
}

SUBSTANTIVE_FILE_ROW_COUNTS: Final[Mapping[str, int]] = {
    "selected_configurations.csv": 15,
    "holdout_metrics.csv": 60,
    "benchmark_vs_naive_dm.csv": 90,
    "within_company_dm.csv": 180,
    "across_company_tests.csv": 7,
    "principal_winners.csv": 15,
    "principal_win_summary.csv": 3,
    "sector_peer_summary.csv": 15,
    "data_quality.csv": 15,
    "data_quality_rules.csv": 6,
    "holdout_predictions.csv": 15 * HOLDOUT_OBSERVATIONS,
    "formal_scope.csv": 15,
}

SUBSTANTIVE_FILE_PURPOSES: Final[Mapping[str, str]] = {
    "selected_configurations.csv": "development-selected model configurations",
    "holdout_metrics.csv": "frozen common-holdout evaluation metrics",
    "benchmark_vs_naive_dm.csv": "principal-model versus naive paired DM evidence",
    "within_company_dm.csv": "all-pairs within-company paired DM evidence",
    "across_company_tests.csv": "across-company MASE statistical evidence",
    "principal_winners.csv": "descriptive per-company principal-model winners",
    "principal_win_summary.csv": "descriptive aggregate principal-model win counts",
    "sector_peer_summary.csv": "descriptive within-sector company-peer summaries",
    "data_quality.csv": "frozen formal-dataset quality screening evidence",
    "data_quality_rules.csv": "predeclared frozen data-quality screening rules",
    "holdout_predictions.csv": "canonical frozen common-holdout actual and forecast ledger",
    "formal_scope.csv": "per-company executed formal data split and validation scope",
}

SUBSTANTIVE_FILE_SOURCE_SCOPES: Final[Mapping[str, str]] = {
    "selected_configurations.csv": "formal",
    "holdout_metrics.csv": "formal+supplementary",
    "benchmark_vs_naive_dm.csv": "formal",
    "within_company_dm.csv": "formal+supplementary",
    "across_company_tests.csv": "formal+supplementary",
    "principal_winners.csv": "formal+supplementary",
    "principal_win_summary.csv": "formal-derived-summary",
    "sector_peer_summary.csv": "formal",
    "data_quality.csv": "formal+data-quality-screening",
    "data_quality_rules.csv": "predeclared-data-quality-rules",
    "holdout_predictions.csv": "formal",
    "formal_scope.csv": "formal",
}

SUPPLEMENTARY_DEPENDENT_FILES: Final[frozenset[str]] = frozenset(
    {
        "holdout_metrics.csv",
        "within_company_dm.csv",
        "across_company_tests.csv",
        "principal_winners.csv",
    }
)


class ResearchResultExportError(RuntimeError):
    """Raised before publication when frozen evidence is missing or inconsistent."""


@dataclass(frozen=True, slots=True)
class ResearchEvidence:
    formal_run: Mapping[str, Any]
    formal_model_config: Mapping[str, Any]
    company_evidence: Mapping[str, Mapping[str, Any]]
    supplementary_source: Mapping[str, Any]
    mase_audit: Mapping[str, Any]
    reporting_semantics: Mapping[str, Any]
    holdout_index: Mapping[str, Any]
    formal_across_company: Mapping[str, Any]
    supplementary_run: Mapping[str, Any]
    paired_mase_evidence: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ResearchRows:
    configurations: tuple[dict[str, object], ...]
    metrics: tuple[dict[str, object], ...]
    benchmark_dm: tuple[dict[str, object], ...]
    within_company_dm: tuple[dict[str, object], ...]
    across_company: tuple[dict[str, object], ...]
    principal_winners: tuple[dict[str, object], ...]
    sector_peers: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class FrozenFormalScope:
    """Verified archive inputs for the two reviewer-facing formal CSVs."""

    run: Mapping[str, Any]
    model_config: Mapping[str, Any]
    raw_provenance: Mapping[str, Any]
    session_completeness: Mapping[str, Any]
    company_evidence: Mapping[str, Mapping[str, Any]]
    raw_dates: Mapping[str, tuple[str, ...]]


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchResultExportError(f"Cannot read authoritative JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ResearchResultExportError(f"Authoritative JSON must be an object: {path}")
    return payload


def load_authoritative_evidence(
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    supplementary_runs_root: Path = DEFAULT_SUPPLEMENTARY_RUNS_ROOT,
) -> ResearchEvidence:
    """Load only integrity-verified evidence linked to the frozen formal run."""

    formal = FormalRunArchive(FORMAL_RUN_ID, root=formal_runs_root)
    if not formal.verify_integrity():
        raise ResearchResultExportError("Formal-run integrity validation failed")
    formal_manifest = _load_json(formal.path / "integrity_manifest.json")
    if formal_manifest.get("aggregate_sha256") != FORMAL_AGGREGATE_SHA256:
        raise ResearchResultExportError("Formal-run aggregate SHA-256 conflicts")

    supplementary = SupplementaryEvidenceArchive(
        SUPPLEMENTARY_PACKAGE_ID,
        root=supplementary_runs_root,
    )
    supplementary_integrity = supplementary.verify_integrity()
    if not supplementary_integrity.valid:
        raise ResearchResultExportError(
            "Supplementary integrity validation failed: "
            + "; ".join(supplementary_integrity.errors)
        )

    company_evidence = {
        company.symbol: _load_json(
            formal.path / "companies" / company.symbol / "evidence.json"
        )
        for company in COMPANIES
    }
    return ResearchEvidence(
        formal_run=_load_json(formal.path / "run.json"),
        formal_model_config=_load_json(
            formal.path / "configuration" / "model_config.json"
        ),
        company_evidence=company_evidence,
        supplementary_source=_load_json(
            supplementary.path / "source" / "formal_source.json"
        ),
        mase_audit=_load_json(
            supplementary.path / "historical" / "mase_denominator_audit.json"
        ),
        reporting_semantics=_load_json(
            supplementary.path / "historical" / "reporting_semantics.json"
        ),
        holdout_index=_load_json(
            supplementary.path / "historical" / "formal_holdout_index.json"
        ),
        formal_across_company=_load_json(
            formal.path / "statistics" / "across_company.json"
        ),
        supplementary_run=_load_json(supplementary.path / "run.json"),
        paired_mase_evidence=_load_json(
            supplementary.path / "historical" / "paired_mase_evidence.json"
        ),
    )


def load_frozen_formal_scope(
    *, formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
) -> FrozenFormalScope:
    """Read chronology and scope exclusively from the verified formal archive."""

    formal = FormalRunArchive(FORMAL_RUN_ID, root=formal_runs_root)
    if not formal.verify_integrity():
        raise ResearchResultExportError("Formal-run integrity validation failed for scope")
    manifest = _load_json(formal.path / "integrity_manifest.json")
    if manifest.get("aggregate_sha256") != FORMAL_AGGREGATE_SHA256:
        raise ResearchResultExportError("Formal-run aggregate SHA-256 conflicts for scope")
    raw_dates: dict[str, tuple[str, ...]] = {}
    company_evidence: dict[str, Mapping[str, Any]] = {}
    for company in COMPANIES:
        symbol = company.symbol
        raw_path = formal.path / "frozen_raw" / f"{symbol}.csv"
        try:
            with raw_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None or "Date" not in reader.fieldnames:
                    raise ResearchResultExportError(f"Frozen raw Date column missing for {symbol}")
                dates = tuple(row["Date"] for row in reader)
        except (OSError, csv.Error, KeyError) as exc:
            raise ResearchResultExportError(f"Cannot read frozen raw dates for {symbol}") from exc
        raw_dates[symbol] = dates
        company_evidence[symbol] = _load_json(
            formal.path / "companies" / symbol / "evidence.json"
        )
    LOGGER.info("Loaded verified formal scope companies=%d", len(company_evidence))
    return FrozenFormalScope(
        run=_load_json(formal.path / "run.json"),
        model_config=_load_json(formal.path / "configuration" / "model_config.json"),
        raw_provenance=_load_json(formal.path / "provenance" / "raw_files.json"),
        session_completeness=_load_json(
            formal.path / "provenance" / "session_completeness.json"
        ),
        company_evidence=company_evidence,
        raw_dates=raw_dates,
    )


def _strict_iso_date(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ResearchResultExportError(f"{label} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ResearchResultExportError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ResearchResultExportError(f"{label} must be a canonical ISO date")
    return value


def build_frozen_formal_rows(
    source: FrozenFormalScope,
    *, companies: Sequence[Company] = COMPANIES,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    """Expose stored predictions and executed scope without statistical computation."""

    canonical = tuple(companies)
    symbols = tuple(company.symbol for company in canonical)
    if len(symbols) != 15 or len(set(symbols)) != 15:
        raise ResearchResultExportError("Formal scope requires 15 unique configured companies")
    run = source.run
    git_state = _mapping(run.get("git_state"), "formal Git state")
    if (
        run.get("run_id") != FORMAL_RUN_ID
        or run.get("cutoff_date") != FORMAL_CUTOFF
        or git_state.get("commit") != FORMAL_GIT_SHA
        or git_state.get("dirty") is not False
        or set(run.get("expected_symbols", ())) != set(symbols)
    ):
        raise ResearchResultExportError("Frozen formal run identity conflicts")
    if set(source.company_evidence) != set(symbols) or set(source.raw_dates) != set(symbols):
        raise ResearchResultExportError("Frozen formal company universe is incomplete")
    provenance = _list(source.raw_provenance.get("raw_files"), "frozen raw provenance")
    sessions = _list(source.session_completeness.get("companies"), "frozen sessions")
    if len(provenance) != 15 or len(sessions) != 15:
        raise ResearchResultExportError("Frozen raw provenance/session count conflicts")
    provenance_by_symbol = {
        _mapping(item, "frozen raw provenance row").get("symbol"): item
        for item in provenance
    }
    sessions_by_symbol = {
        _mapping(item, "frozen session row").get("symbol"): item
        for item in sessions
    }
    if set(provenance_by_symbol) != set(symbols) or set(sessions_by_symbol) != set(symbols):
        raise ResearchResultExportError("Frozen provenance/session symbols conflict")
    config = _mapping(source.model_config.get("model_config"), "formal model config")
    split_counts = {
        _positive_integer(_mapping(config.get(key), key).get("cv_splits"), f"{key} CV splits")
        for key in ("lag_regression", "arima", "lstm")
    }
    if split_counts != {5}:
        raise ResearchResultExportError("Executed formal CV split counts conflict")
    cv_count = split_counts.pop()
    seeds = tuple(_list(_mapping(config.get("lstm"), "LSTM config").get("tuning_seeds"), "LSTM seeds"))
    if not seeds or len(set(seeds)) != len(seeds):
        raise ResearchResultExportError("Executed LSTM tuning seeds are invalid")

    predictions: list[dict[str, object]] = []
    scopes: list[dict[str, object]] = []
    common_holdout: tuple[str, ...] | None = None
    common_development: tuple[str, ...] | None = None
    for company in canonical:
        symbol = company.symbol
        raw_dates = tuple(
            _strict_iso_date(value, f"{symbol} frozen raw Date")
            for value in source.raw_dates[symbol]
        )
        if (
            len(raw_dates) != FORMAL_ROWS_PER_COMPANY
            or not raw_dates
            or raw_dates[0] != FORMAL_START
            or raw_dates[-1] != FORMAL_CUTOFF
            or raw_dates != tuple(sorted(set(raw_dates)))
        ):
            raise ResearchResultExportError(f"Frozen raw chronology conflicts for {symbol}")
        provenance_row = _mapping(provenance_by_symbol[symbol], f"{symbol} provenance")
        session_row = _mapping(sessions_by_symbol[symbol], f"{symbol} sessions")
        if (
            provenance_row.get("first_date") != raw_dates[0]
            or provenance_row.get("last_date") != raw_dates[-1]
            or provenance_row.get("row_count") != len(raw_dates)
            or session_row.get("start_date") != raw_dates[0]
            or session_row.get("cutoff_date") != raw_dates[-1]
            or session_row.get("expected_session_count") != len(raw_dates)
            or session_row.get("actual_session_count") != len(raw_dates)
            or session_row.get("complete") is not True
            or any(session_row.get(key) != [] for key in ("missing_dates", "duplicate_dates", "unexpected_dates"))
        ):
            raise ResearchResultExportError(f"Frozen raw provenance conflicts for {symbol}")

        evidence = _mapping(source.company_evidence[symbol], f"{symbol} evidence")
        if evidence.get("symbol") != symbol:
            raise ResearchResultExportError(f"Frozen company identity conflicts for {symbol}")
        development = tuple(
            _strict_iso_date(value, f"{symbol} development target")
            for value in _list(evidence.get("development_target_dates"), "development dates")
        )
        holdout = tuple(
            _strict_iso_date(value, f"{symbol} holdout target")
            for value in _list(evidence.get("holdout_target_dates"), "holdout dates")
        )
        if (
            not development
            or len(holdout) != HOLDOUT_OBSERVATIONS
            or holdout[0] != HOLDOUT_START
            or holdout[-1] != HOLDOUT_END
            or development[-1] >= holdout[0]
            or development + holdout != raw_dates[1:]
        ):
            raise ResearchResultExportError(f"Formal target-date scope conflicts for {symbol}")
        if common_holdout is None:
            common_holdout, common_development = holdout, development
        elif holdout != common_holdout or development != common_development:
            raise ResearchResultExportError(f"Formal target dates differ for {symbol}")

        manifests = _mapping(evidence.get("cv_fold_target_date_manifests"), f"{symbol} CV")
        if set(manifests) != set(PRINCIPAL_METHODS):
            raise ResearchResultExportError(f"Formal CV families conflict for {symbol}")
        for method in PRINCIPAL_METHODS:
            folds = _list(manifests[method], f"{symbol}/{method} CV folds")
            expected = cv_count * (len(seeds) if method == "lstm" else 1)
            if len(folds) != expected:
                raise ResearchResultExportError(f"Formal CV fold count conflicts for {symbol}/{method}")
            fold_ids: list[int] = []
            for fold in folds:
                entry = _mapping(fold, f"{symbol}/{method} CV fold")
                fold_id = entry.get("fold_index")
                if type(fold_id) is not int:
                    raise ResearchResultExportError(f"Formal CV fold index invalid for {symbol}/{method}")
                fold_ids.append(fold_id)
                train_key = "outer_training_target_dates" if method == "lstm" else "training_target_dates"
                train = tuple(_list(entry.get(train_key), f"{symbol}/{method} CV train"))
                validation = tuple(_list(entry.get("validation_target_dates"), f"{symbol}/{method} CV validation"))
                if (
                    not train or not validation
                    or train != tuple(sorted(set(train)))
                    or validation != tuple(sorted(set(validation)))
                    or train[-1] >= validation[0]
                    or not set(validation).issubset(development)
                ):
                    raise ResearchResultExportError(f"Nonchronological formal CV for {symbol}/{method}")
                if method == "lstm":
                    stopping = tuple(_list(entry.get("stopping_target_dates"), "LSTM stopping dates"))
                    if not stopping or not set(stopping).issubset(train):
                        raise ResearchResultExportError(f"Formal LSTM stopping dates conflict for {symbol}")
                    if entry.get("seed") not in seeds:
                        raise ResearchResultExportError(f"Formal LSTM CV seed conflicts for {symbol}")
            if set(fold_ids) != set(range(cv_count)):
                raise ResearchResultExportError(f"Formal CV fold indices conflict for {symbol}/{method}")
            if method == "lstm" and {
                (fold["fold_index"], fold["seed"]) for fold in folds
            } != {(index, seed) for index in range(cv_count) for seed in seeds}:
                raise ResearchResultExportError(f"Formal LSTM fold/seed coverage conflicts for {symbol}")

        dm = _mapping(_mapping(evidence.get("statistical_tests"), "formal tests").get("diebold_mariano"), "formal DM")
        families = _mapping(dm.get("holm_families"), "formal DM families")
        horizons = {
            _positive_integer(_mapping(item, "formal DM pair").get("forecast_horizon"), "forecast horizon")
            for loss in LOSS_TYPES
            for item in _list(families.get(loss), f"{loss} DM family")
        }
        if horizons != {1}:
            raise ResearchResultExportError(f"Formal forecast horizon conflicts for {symbol}")

        records = _list(evidence.get("canonical_holdout_records"), f"{symbol} records")
        if len(records) != len(holdout):
            raise ResearchResultExportError(f"Canonical holdout row count conflicts for {symbol}")
        position = {value: index for index, value in enumerate(raw_dates)}
        for target, item in zip(holdout, records, strict=True):
            record = _mapping(item, f"{symbol} canonical record")
            if record.get("company") != symbol or record.get("target_date") != target:
                raise ResearchResultExportError(f"Canonical holdout alignment conflicts for {symbol}")
            index = position.get(target)
            if index is None or index == 0:
                raise ResearchResultExportError(f"Target has no frozen origin for {symbol}")
            origin = raw_dates[index - 1]
            if record.get("origin_date", origin) != origin:
                raise ResearchResultExportError(f"Stored origin conflicts with frozen session for {symbol}")
            predictions.append({
                "symbol": symbol,
                "company_name": company.name,
                "sector": company.sector,
                "origin_date": origin,
                "target_date": target,
                "actual_close": _finite_number(record.get("actual_close"), f"{symbol} actual Close"),
                "lag_reg_prediction": _finite_number(record.get("lir_prediction"), f"{symbol} LIR prediction"),
                "arima_prediction": _finite_number(record.get("arima_prediction"), f"{symbol} ARIMA prediction"),
                "lstm_prediction": _finite_number(record.get("lstm_prediction"), f"{symbol} LSTM prediction"),
                "naive_prediction": _finite_number(record.get("naive_prediction"), f"{symbol} Naive prediction"),
                "formal_run_id": FORMAL_RUN_ID,
                "formal_cutoff": FORMAL_CUTOFF,
                "formal_git_sha": FORMAL_GIT_SHA,
            })
        scopes.append({
            "symbol": symbol,
            "company_name": company.name,
            "sector": company.sector,
            "raw_start": raw_dates[0],
            "raw_end": raw_dates[-1],
            "raw_row_count": len(raw_dates),
            "forecast_pair_count": len(development) + len(holdout),
            "development_start": development[0],
            "development_end": development[-1],
            "development_pair_count": len(development),
            "holdout_start": holdout[0],
            "holdout_end": holdout[-1],
            "holdout_pair_count": len(holdout),
            "cv_split_count": cv_count,
            "forecast_horizon": 1,
            "shuffle_used": _bool_text(False),
            "formal_run_id": FORMAL_RUN_ID,
            "formal_cutoff": FORMAL_CUTOFF,
            "formal_git_sha": FORMAL_GIT_SHA,
        })
    if len(predictions) != 15 * HOLDOUT_OBSERVATIONS or len(scopes) != 15:
        raise ResearchResultExportError("Frozen formal row counts are incomplete")
    LOGGER.info("Built frozen formal rows holdout=%d scope=%d", len(predictions), len(scopes))
    return tuple(predictions), tuple(scopes)


def build_holdout_prediction_rows(source: FrozenFormalScope) -> tuple[dict[str, object], ...]:
    return build_frozen_formal_rows(source)[0]


def build_formal_scope_rows(source: FrozenFormalScope) -> tuple[dict[str, object], ...]:
    return build_frozen_formal_rows(source)[1]


def _expected_formal_sessions(calendar: PSETradingCalendar) -> tuple[date, ...]:
    start = date.fromisoformat(FORMAL_START)
    cutoff = date.fromisoformat(FORMAL_CUTOFF)
    sessions: list[date] = []
    candidate = start
    while candidate <= cutoff:
        if calendar.is_trading_day(candidate):
            sessions.append(candidate)
        candidate += timedelta(days=1)
    return tuple(sessions)


def build_frozen_data_quality_rows(
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    companies: Sequence[Company] = COMPANIES,
    calendar: PSETradingCalendar | None = None,
) -> tuple[dict[str, object], ...]:
    """Screen only integrity-verified frozen raw files from the formal archive."""

    canonical_companies = tuple(companies)
    symbols = tuple(company.symbol for company in canonical_companies)
    if len(canonical_companies) != 15 or len(set(symbols)) != 15:
        raise ResearchResultExportError(
            "Data-quality export requires exactly 15 configured companies"
        )

    formal = FormalRunArchive(
        FORMAL_RUN_ID,
        root=formal_runs_root,
        expected_symbols=symbols,
    )
    if not formal.verify_integrity():
        raise ResearchResultExportError(
            "Formal-run integrity validation failed for data-quality export"
        )
    manifest = _load_json(formal.path / "integrity_manifest.json")
    if manifest.get("aggregate_sha256") != FORMAL_AGGREGATE_SHA256:
        raise ResearchResultExportError("Formal aggregate SHA-256 conflicts")
    run = _load_json(formal.path / "run.json")
    git_state = _mapping(run.get("git_state"), "formal Git state")
    if (
        run.get("run_id") != FORMAL_RUN_ID
        or run.get("cutoff_date") != FORMAL_CUTOFF
        or tuple(run.get("expected_symbols", ())) != symbols
        or git_state.get("commit") != FORMAL_GIT_SHA
        or git_state.get("dirty") is not False
    ):
        raise ResearchResultExportError("Formal data-quality identity conflicts")

    provenance = _load_json(formal.path / "provenance" / "raw_files.json")
    provenance_rows = _list(provenance.get("raw_files"), "formal raw provenance")
    provenance_by_symbol: dict[str, Mapping[str, Any]] = {}
    for item in provenance_rows:
        record = _mapping(item, "formal raw provenance record")
        symbol = record.get("symbol")
        if not isinstance(symbol, str) or symbol in provenance_by_symbol:
            raise ResearchResultExportError("Formal raw provenance symbols conflict")
        provenance_by_symbol[symbol] = record
    if tuple(provenance_by_symbol) != symbols:
        raise ResearchResultExportError("Formal raw provenance company order conflicts")

    completeness = _load_json(
        formal.path / "provenance" / "session_completeness.json"
    )
    completeness_rows = _list(
        completeness.get("companies"), "formal session completeness"
    )
    completeness_by_symbol = {
        item.get("symbol"): _mapping(item, "formal session record")
        for item in completeness_rows
        if isinstance(item, Mapping)
    }
    if set(completeness_by_symbol) != set(symbols) or len(completeness_rows) != 15:
        raise ResearchResultExportError("Formal session evidence is incomplete")

    try:
        load_corporate_action_registry(
            formal.path / "provenance" / "corporate_actions.json"
        )
    except Exception as exc:
        raise ResearchResultExportError(
            "Formal corporate-action registry is invalid"
        ) from exc

    expected_sessions = _expected_formal_sessions(calendar or PSETradingCalendar())
    if len(expected_sessions) != FORMAL_ROWS_PER_COMPANY:
        raise ResearchResultExportError(
            "Configured PSE calendar conflicts with the frozen formal session count"
        )

    output: list[dict[str, object]] = []
    total_rows = 0
    for company in canonical_companies:
        symbol = company.symbol
        snapshot = formal.path / "frozen_raw" / company.raw_filename
        source = provenance_by_symbol[symbol]
        if (
            source.get("sha256") != sha256_file(snapshot)
            or source.get("first_date") != FORMAL_START
            or source.get("last_date") != FORMAL_CUTOFF
            or source.get("row_count") != FORMAL_ROWS_PER_COMPANY
        ):
            raise ResearchResultExportError(
                f"Frozen raw provenance conflicts for {symbol}"
            )
        with snapshot.open("r", encoding="utf-8", newline="") as csv_source:
            reader = csv.DictReader(csv_source)
            fieldnames = tuple(reader.fieldnames or ())
            raw_rows = list(reader)
        try:
            screened = screen_ohlcv_rows(
                fieldnames=fieldnames,
                rows=raw_rows,
                expected_sessions=expected_sessions,
            )
        except DataQualityScreeningError as exc:
            raise ResearchResultExportError(
                f"Frozen data-quality screening failed for {symbol}: {exc}"
            ) from exc
        if (
            screened["start_date"] != FORMAL_START
            or screened["end_date"] != FORMAL_CUTOFF
            or screened["row_count"] != FORMAL_ROWS_PER_COMPANY
        ):
            raise ResearchResultExportError(
                f"Frozen formal date range or row count conflicts for {symbol}"
            )

        archived = completeness_by_symbol[symbol]
        expected_completeness = {
            "start_date": screened["start_date"],
            "cutoff_date": screened["end_date"],
            "expected_session_count": screened["expected_session_count"],
            "actual_session_count": screened["observed_session_count"],
            "missing_dates": [],
            "unexpected_dates": [],
            "duplicate_dates": [],
            "complete": screened["continuity_status"] == "PASS",
        }
        for key, expected in expected_completeness.items():
            if archived.get(key) != expected:
                raise ResearchResultExportError(
                    f"Formal session evidence conflicts for {symbol}/{key}"
                )

        total_rows += int(screened["row_count"])
        output.append(
            {
                "symbol": symbol,
                "company_name": company.name,
                "sector": company.sector,
                **{
                    key: (
                        _bool_text(bool(value))
                        if key == "screening_review_required"
                        else value
                    )
                    for key, value in screened.items()
                },
                "formal_run_id": FORMAL_RUN_ID,
                "formal_cutoff": FORMAL_CUTOFF,
                "formal_git_sha": FORMAL_GIT_SHA,
                "rule_version": RULE_VERSION,
            }
        )

    if len(output) != 15 or total_rows != FORMAL_TOTAL_ROWS:
        raise ResearchResultExportError(
            "Frozen formal company or total row count conflicts"
        )
    return tuple(output)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResearchResultExportError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ResearchResultExportError(f"{label} must be a list")
    return value


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResearchResultExportError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ResearchResultExportError(f"{label} must be finite")
    return result


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ResearchResultExportError(f"{label} must be a positive integer")
    return value


def _exact_number(value: object, expected: object, label: str) -> None:
    if _finite_number(value, label) != _finite_number(expected, label):
        raise ResearchResultExportError(f"{label} conflicts across evidence")


def _company_index(payload: Mapping[str, Any], label: str) -> dict[str, Mapping[str, Any]]:
    companies = _list(payload.get("companies"), f"{label}.companies")
    indexed: dict[str, Mapping[str, Any]] = {}
    for item in companies:
        company = _mapping(item, f"{label} company")
        symbol = company.get("symbol")
        if not isinstance(symbol, str) or symbol in indexed:
            raise ResearchResultExportError(f"{label} has invalid or duplicate symbols")
        indexed[symbol] = company
    return indexed


def _validate_provenance(evidence: ResearchEvidence, symbols: tuple[str, ...]) -> None:
    run = evidence.formal_run
    git_state = _mapping(run.get("git_state"), "formal git_state")
    expected_run = {
        "run_id": FORMAL_RUN_ID,
        "cutoff_date": FORMAL_CUTOFF,
    }
    for key, expected in expected_run.items():
        if run.get(key) != expected:
            raise ResearchResultExportError(f"Formal {key} conflicts with expected identity")
    if git_state.get("commit") != FORMAL_GIT_SHA or git_state.get("dirty") is not False:
        raise ResearchResultExportError("Formal Git provenance conflicts")
    if tuple(run.get("expected_symbols", ())) != symbols:
        raise ResearchResultExportError("Formal company universe or order conflicts")

    source = evidence.supplementary_source
    expected_source = {
        "source_formal_run_id": FORMAL_RUN_ID,
        "source_cutoff_date": FORMAL_CUTOFF,
        "source_git_commit": FORMAL_GIT_SHA,
        "source_formal_integrity_aggregate_sha256": FORMAL_AGGREGATE_SHA256,
        "source_formal_run_state": "FINALIZED",
        "source_holdout_start": HOLDOUT_START,
        "source_holdout_end": HOLDOUT_END,
        "source_target_count_per_company": HOLDOUT_OBSERVATIONS,
        "source_company_count": len(symbols),
    }
    for key, expected in expected_source.items():
        if source.get(key) != expected:
            raise ResearchResultExportError(
                f"Supplementary formal linkage conflicts for {key}"
            )
    if tuple(source.get("source_company_order", ())) != symbols:
        raise ResearchResultExportError("Supplementary company order conflicts")
    if (
        evidence.supplementary_run.get("package_id") != SUPPLEMENTARY_PACKAGE_ID
        or evidence.supplementary_run.get("source_formal_run_id") != FORMAL_RUN_ID
    ):
        raise ResearchResultExportError("Supplementary package identity conflicts")


def _selected_lir_mean(tuning: Mapping[str, Any], alpha: float) -> float:
    values = _mapping(tuning.get("mean_validation_rmse"), "LIR validation RMSE grid")
    matches = [value for key, value in values.items() if float(key) == alpha]
    if len(matches) != 1:
        raise ResearchResultExportError("Selected LIR alpha has no unique tuning score")
    selected = _finite_number(matches[0], "selected LIR validation RMSE")
    all_scores = tuple(_finite_number(value, "LIR validation RMSE") for value in values.values())
    if selected != min(all_scores):
        raise ResearchResultExportError("Selected LIR alpha is not a minimum-RMSE candidate")
    return selected


def _validate_selected_candidate(
    tuning: Mapping[str, Any],
    selected_specification: Mapping[str, Any],
    label: str,
    completion_key: str = "completed",
) -> tuple[float, float | None]:
    stored_specification = _mapping(
        tuning.get("selected_specification"), f"{label} selected specification"
    )
    if dict(stored_specification) != dict(selected_specification):
        raise ResearchResultExportError(f"{label} selected specification conflicts")
    selected_mean = _finite_number(
        tuning.get("selected_mean_validation_rmse"),
        f"{label} selected mean validation RMSE",
    )
    candidates = _list(tuning.get("candidates"), f"{label} candidates")
    eligible_scores = [
        _finite_number(candidate["mean_validation_rmse"], f"{label} candidate RMSE")
        for candidate in candidates
        if isinstance(candidate, Mapping)
        and candidate.get(completion_key) is True
        and candidate.get("mean_validation_rmse") is not None
    ]
    if not eligible_scores or selected_mean != min(eligible_scores):
        raise ResearchResultExportError(f"{label} selection is not minimum mean RMSE")
    variability = tuning.get("selected_validation_rmse_standard_deviation")
    return selected_mean, (
        None
        if variability is None
        else _finite_number(variability, f"{label} validation RMSE variability")
    )


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _selection_summary(metrics: Mapping[str, Mapping[str, Any]]) -> dict[str, object]:
    rmse = {
        method: _finite_number(metrics[method].get("rmse"), f"{method} RMSE")
        for method in METHODS
    }
    order = {method: index for index, method in enumerate(METHODS)}
    best_principal = min(PRINCIPAL_METHODS, key=lambda item: (rmse[item], order[item]))
    best_evaluated = min(METHODS, key=lambda item: (rmse[item], order[item]))
    return {
        "best_principal_model": best_principal,
        "best_evaluated_method": best_evaluated,
        "best_principal_beats_naive": rmse[best_principal] < rmse["naive"],
        "all_principals_worse_than_naive": all(
            rmse[method] > rmse["naive"] for method in PRINCIPAL_METHODS
        ),
    }


def _principal_ranks(rmse: Mapping[str, float]) -> dict[str, int]:
    ordered = sorted(
        PRINCIPAL_METHODS,
        key=lambda method: (rmse[method], PRINCIPAL_METHODS.index(method)),
    )
    return {method: rank for rank, method in enumerate(ordered, start=1)}


def _dm_export_values(
    result: Mapping[str, Any], label: str
) -> tuple[dict[str, object], float]:
    available = result.get("available")
    reject = result.get("reject")
    if not isinstance(available, bool) or not isinstance(reject, bool):
        raise ResearchResultExportError(f"{label} availability/rejection is invalid")
    sample_size = _positive_integer(result.get("sample_size"), f"{label} sample size")
    if sample_size != HOLDOUT_OBSERVATIONS:
        raise ResearchResultExportError(f"{label} sample size conflicts")
    mean_difference = _finite_number(
        result.get("mean_loss_differential"), f"{label} mean loss differential"
    )
    hac_lag = _positive_integer(result.get("hac_lag"), f"{label} HAC lag")
    horizon = _positive_integer(
        result.get("forecast_horizon"), f"{label} forecast horizon"
    )
    if horizon != 1:
        raise ResearchResultExportError(f"{label} forecast horizon conflicts")
    hln = _finite_number(
        result.get("hln_correction_factor"), f"{label} HLN correction"
    )
    reason = result.get("unavailable_reason")
    if available:
        if reason is not None:
            raise ResearchResultExportError(f"{label} has an unexpected unavailable reason")
        statistic = _finite_number(result.get("dm_statistic"), f"{label} statistic")
        raw_p = _finite_number(result.get("raw_p_value"), f"{label} raw p-value")
        adjusted_p = _finite_number(
            result.get("holm_adjusted_p_value"), f"{label} adjusted p-value"
        )
        if not (0.0 <= raw_p <= 1.0 and 0.0 <= adjusted_p <= 1.0):
            raise ResearchResultExportError(f"{label} p-value is outside [0, 1]")
    else:
        if result.get("dm_statistic") is not None or reject:
            raise ResearchResultExportError(f"{label} unavailable result is inconsistent")
        if not isinstance(reason, str) or not reason:
            raise ResearchResultExportError(f"{label} unavailable reason is missing")
        statistic = raw_p = adjusted_p = ""
    return (
        {
            "sample_size": sample_size,
            "mean_loss_differential": mean_difference,
            "dm_statistic": statistic,
            "raw_p_value": raw_p,
            "holm_adjusted_p_value": adjusted_p,
            "reject": _bool_text(reject),
            "available": _bool_text(available),
            "unavailable_reason": "" if reason is None else reason,
            "hac_lag": hac_lag,
            "forecast_horizon": horizon,
            "hln_correction_factor": hln,
        },
        mean_difference,
    )


def _company_dm_rows(
    *,
    company: Company,
    formal: Mapping[str, Any],
    semantics: Mapping[str, Any],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[tuple[str, str], str]]:
    statistical_tests = _mapping(formal.get("statistical_tests"), "statistical tests")
    formal_dm = _mapping(
        statistical_tests.get("diebold_mariano"), "formal DM evidence"
    )
    supplementary_dm = _mapping(
        semantics.get("archived_dm_evidence"), "supplementary DM evidence"
    )
    if formal_dm != supplementary_dm:
        raise ResearchResultExportError(
            f"Formal and supplementary DM evidence conflict for {company.symbol}"
        )
    if (
        formal_dm.get("company") != company.symbol
        or formal_dm.get("scope") != "complete_aligned_evaluation"
        or formal_dm.get("p_value_sidedness") != "two_sided"
        or formal_dm.get("hln_small_sample_correction") is not True
    ):
        raise ResearchResultExportError(f"DM provenance conflicts for {company.symbol}")
    families = _mapping(formal_dm.get("holm_families"), "DM Holm families")
    if set(families) != set(LOSS_TYPES):
        raise ResearchResultExportError(f"DM loss families conflict for {company.symbol}")

    within_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []
    statuses: dict[tuple[str, str], str] = {}
    expected_pairs = set(METHOD_PAIRS)
    for loss_type in LOSS_TYPES:
        results = _list(families.get(loss_type), f"{company.symbol}/{loss_type} DM family")
        indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
        for item in results:
            result = _mapping(item, "DM result")
            pair = (result.get("model_1"), result.get("model_2"))
            if pair in indexed or pair not in expected_pairs:
                raise ResearchResultExportError(
                    f"DM method pairs conflict for {company.symbol}/{loss_type}"
                )
            if tuple(result.get("model_pair", ())) != pair:
                raise ResearchResultExportError(
                    f"DM pair direction conflicts for {company.symbol}/{loss_type}"
                )
            if result.get("loss_type") != loss_type:
                raise ResearchResultExportError(
                    f"DM loss label conflicts for {company.symbol}/{pair}"
                )
            indexed[pair] = result
        if set(indexed) != expected_pairs:
            raise ResearchResultExportError(
                f"DM family is incomplete for {company.symbol}/{loss_type}"
            )

        for model_1, model_2 in METHOD_PAIRS:
            result = indexed[(model_1, model_2)]
            values, mean_difference = _dm_export_values(
                result, f"{company.symbol}/{loss_type}/{model_1}/{model_2}"
            )
            within_rows.append(
                {
                    "symbol": company.symbol,
                    "company_name": company.name,
                    "sector": company.sector,
                    "model_1": model_1,
                    "model_2": model_2,
                    "loss_type": loss_type,
                    **values,
                    "holm_family_size": 6,
                    "formal_run_id": FORMAL_RUN_ID,
                    "formal_cutoff": FORMAL_CUTOFF,
                    "formal_git_sha": FORMAL_GIT_SHA,
                    "supplementary_package_id": SUPPLEMENTARY_PACKAGE_ID,
                    "evidence_source": (
                        "formal_company_evidence_verified_against_linked_supplementary"
                    ),
                }
            )
            if model_2 == "naive":
                benchmark_rows.append(
                    {
                        "symbol": company.symbol,
                        "company_name": company.name,
                        "sector": company.sector,
                        "model": model_1,
                        "benchmark": model_2,
                        "loss_type": loss_type,
                        "sample_size": values["sample_size"],
                        "mean_loss_differential": mean_difference,
                        "loss_difference_direction": (
                            "model_minus_benchmark_negative_means_model_lower_loss"
                        ),
                        **{
                            key: values[key]
                            for key in (
                                "dm_statistic", "raw_p_value", "holm_adjusted_p_value",
                                "reject", "available", "unavailable_reason", "hac_lag",
                                "forecast_horizon", "hln_correction_factor",
                            )
                        },
                        "formal_run_id": FORMAL_RUN_ID,
                        "formal_cutoff": FORMAL_CUTOFF,
                        "formal_git_sha": FORMAL_GIT_SHA,
                        "evidence_source": "finalized_formal_company_dm_evidence",
                    }
                )
                if values["available"] == "false":
                    status = "unavailable"
                elif values["reject"] == "false":
                    status = "not_significant"
                elif mean_difference < 0:
                    status = "significantly_better"
                elif mean_difference > 0:
                    status = "significantly_worse"
                else:
                    raise ResearchResultExportError(
                        f"Rejected zero-difference DM result for {company.symbol}/{model_1}"
                    )
                statuses[(model_1, loss_type)] = status
    return within_rows, benchmark_rows, statuses


def _build_across_company_rows(
    evidence: ResearchEvidence, symbols: tuple[str, ...]
) -> list[dict[str, object]]:
    formal = evidence.formal_across_company
    supplementary = evidence.paired_mase_evidence
    if (
        supplementary.get("source_formal_run_id") != FORMAL_RUN_ID
        or supplementary.get("source_formal_integrity_aggregate_sha256")
        != FORMAL_AGGREGATE_SHA256
        or supplementary.get("company_count") != len(symbols)
        or supplementary.get("metric") != "mase"
        or supplementary.get("wilcoxon_gate")
        != "performed_only_when_friedman_rejects"
        or supplementary.get("wilcoxon_holm_family_size") != 6
    ):
        raise ResearchResultExportError("Across-company supplementary provenance conflicts")
    for key in ("alpha", "company_count", "metric", "friedman"):
        if formal.get(key) != supplementary.get(key):
            raise ResearchResultExportError(
                f"Formal and supplementary across-company evidence conflict for {key}"
            )
    if tuple(formal.get("models", ())) != METHODS:
        raise ResearchResultExportError("Across-company method order conflicts")

    alpha = _finite_number(formal.get("alpha"), "across-company alpha")
    friedman = _mapping(formal.get("friedman"), "Friedman evidence")
    reject = friedman.get("reject")
    if not isinstance(reject, bool):
        raise ResearchResultExportError("Friedman reject flag is invalid")
    rows: list[dict[str, object]] = [
        {
            "test_level": "across_company",
            "test_name": "friedman",
            "metric": "mase",
            "model_1": "",
            "model_2": "",
            "company_count": len(symbols),
            "statistic": _finite_number(friedman.get("statistic"), "Friedman statistic"),
            "raw_p_value": _finite_number(
                friedman.get("raw_p_value"), "Friedman p-value"
            ),
            "holm_adjusted_p_value": "",
            "alpha": alpha,
            "reject": _bool_text(reject),
            "performed": "true",
            "difference_direction": "",
            "median_difference": "",
            "mean_difference": "",
            "std_difference": "",
            "skewness": "",
            "positive_count": "",
            "negative_count": "",
            "zero_count": "",
            "sign_test_p_value": "",
            "formal_run_id": FORMAL_RUN_ID,
            "formal_cutoff": FORMAL_CUTOFF,
            "formal_git_sha": FORMAL_GIT_SHA,
            "supplementary_package_id": SUPPLEMENTARY_PACKAGE_ID,
            "evidence_source": "finalized_formal_across_company_evidence",
        }
    ]

    pairs = _list(supplementary.get("pairs"), "paired MASE evidence")
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in pairs:
        pair = _mapping(item, "paired MASE result")
        key = (pair.get("model_1"), pair.get("model_2"))
        if key in indexed or key not in set(METHOD_PAIRS):
            raise ResearchResultExportError("Paired MASE method pairs conflict")
        indexed[key] = pair
    if set(indexed) != set(METHOD_PAIRS):
        raise ResearchResultExportError("Paired MASE evidence is incomplete")

    formal_posthoc = _list(formal.get("pairwise_wilcoxon"), "formal Wilcoxon evidence")
    if formal.get("posthoc_performed") is not reject:
        raise ResearchResultExportError("Friedman/Wilcoxon gate conflicts")
    if (not reject and formal_posthoc) or (reject and len(formal_posthoc) != 6):
        raise ResearchResultExportError("Formal Wilcoxon results conflict with the gate")

    for model_1, model_2 in METHOD_PAIRS:
        pair = indexed[(model_1, model_2)]
        if (
            tuple(pair.get("company_order", ())) != symbols
            or pair.get("observation_count") != len(symbols)
            or pair.get("difference_direction") != "model_1_mase_minus_model_2_mase"
        ):
            raise ResearchResultExportError(
                f"Paired MASE alignment conflicts for {model_1}/{model_2}"
            )
        wilcoxon = _mapping(pair.get("wilcoxon"), "Wilcoxon status")
        performed = wilcoxon.get("performed")
        if performed is not reject:
            raise ResearchResultExportError("Stored Wilcoxon gate conflicts")
        if not performed and any(
            wilcoxon.get(key) is not None
            for key in ("statistic", "raw_p_value", "holm_adjusted_p_value", "reject")
        ):
            raise ResearchResultExportError("Unperformed Wilcoxon has invented results")
        if performed:
            statistic: object = _finite_number(
                wilcoxon.get("statistic"), "Wilcoxon statistic"
            )
            raw_p: object = _finite_number(wilcoxon.get("raw_p_value"), "Wilcoxon p-value")
            adjusted_p: object = _finite_number(
                wilcoxon.get("holm_adjusted_p_value"), "Wilcoxon adjusted p-value"
            )
            wilcoxon_reject = wilcoxon.get("reject")
            if not isinstance(wilcoxon_reject, bool):
                raise ResearchResultExportError("Wilcoxon reject flag is invalid")
            reject_text: object = _bool_text(wilcoxon_reject)
        else:
            statistic = raw_p = adjusted_p = reject_text = ""
        sign_test = _mapping(pair.get("sign_test"), "sign test evidence")
        rows.append(
            {
                "test_level": "across_company",
                "test_name": "wilcoxon",
                "metric": "mase",
                "model_1": model_1,
                "model_2": model_2,
                "company_count": len(symbols),
                "statistic": statistic,
                "raw_p_value": raw_p,
                "holm_adjusted_p_value": adjusted_p,
                "alpha": alpha,
                "reject": reject_text,
                "performed": _bool_text(performed),
                "difference_direction": pair.get("difference_direction"),
                "median_difference": _finite_number(
                    pair.get("median_difference"), "median paired difference"
                ),
                "mean_difference": _finite_number(
                    pair.get("mean_difference"), "mean paired difference"
                ),
                "std_difference": _finite_number(
                    pair.get("standard_deviation"), "paired difference standard deviation"
                ),
                "skewness": _finite_number(pair.get("skewness"), "paired difference skewness"),
                "positive_count": pair.get("positive_count"),
                "negative_count": pair.get("negative_count"),
                "zero_count": pair.get("zero_count"),
                "sign_test_p_value": _finite_number(
                    sign_test.get("raw_p_value"), "sign-test p-value"
                ),
                "formal_run_id": FORMAL_RUN_ID,
                "formal_cutoff": FORMAL_CUTOFF,
                "formal_git_sha": FORMAL_GIT_SHA,
                "supplementary_package_id": SUPPLEMENTARY_PACKAGE_ID,
                "evidence_source": "verified_supplementary_paired_mase_evidence",
            }
        )
    return rows


def build_research_rows(
    evidence: ResearchEvidence,
    *,
    companies: Sequence[Company] = COMPANIES,
) -> ResearchRows:
    """Validate all evidence first and construct both CSV datasets in memory."""

    canonical_companies = tuple(companies)
    symbols = tuple(company.symbol for company in canonical_companies)
    if len(canonical_companies) != 15 or len(set(symbols)) != 15:
        raise ResearchResultExportError("Exactly 15 unique configured companies are required")
    if set(evidence.company_evidence) != set(symbols):
        raise ResearchResultExportError("Formal company evidence is incomplete or unexpected")
    _validate_provenance(evidence, symbols)

    config_root = _mapping(evidence.formal_model_config.get("model_config"), "model config")
    lir_config = _mapping(config_root.get("lag_regression"), "LIR config")
    arima_config = _mapping(config_root.get("arima"), "ARIMA config")
    lstm_config = _mapping(config_root.get("lstm"), "LSTM config")
    cv_splits = {
        _positive_integer(lir_config.get("cv_splits"), "LIR cv_splits"),
        _positive_integer(arima_config.get("cv_splits"), "ARIMA cv_splits"),
        _positive_integer(lstm_config.get("cv_splits"), "LSTM cv_splits"),
    }
    if cv_splits != {5}:
        raise ResearchResultExportError("Formal model CV split counts conflict")
    tuning_seeds = tuple(_list(lstm_config.get("tuning_seeds"), "LSTM tuning seeds"))
    if tuning_seeds != (11, 29, 47) or lstm_config.get("final_seed") != 42:
        raise ResearchResultExportError("Formal LSTM seeds conflict")
    trends_by_d = {
        int(item[0]): tuple(item[1])
        for item in _list(arima_config.get("trend_options_by_d"), "ARIMA trends")
    }

    audit_by_symbol = _company_index(evidence.mase_audit, "MASE audit")
    semantics_by_symbol = _company_index(
        evidence.reporting_semantics, "reporting semantics"
    )
    index_by_symbol = _company_index(evidence.holdout_index, "holdout index")
    for label, payload in (
        ("MASE audit", evidence.mase_audit),
        ("reporting semantics", evidence.reporting_semantics),
        ("holdout index", evidence.holdout_index),
    ):
        if tuple(payload.get("company_order", ())) != symbols:
            raise ResearchResultExportError(f"{label} company order conflicts")
    common_dates = tuple(
        _list(evidence.holdout_index.get("common_target_dates"), "common dates")
    )
    if (
        len(common_dates) != HOLDOUT_OBSERVATIONS
        or common_dates[0] != HOLDOUT_START
        or common_dates[-1] != HOLDOUT_END
        or tuple(sorted(set(common_dates))) != common_dates
    ):
        raise ResearchResultExportError("Frozen common holdout dates conflict")

    configuration_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []
    within_rows: list[dict[str, object]] = []
    winner_rows: list[dict[str, object]] = []
    sector_rows: list[dict[str, object]] = []
    for company in canonical_companies:
        symbol = company.symbol
        formal = evidence.company_evidence[symbol]
        if formal.get("symbol") != symbol:
            raise ResearchResultExportError(f"Formal company identity conflicts for {symbol}")
        holdout_dates = tuple(_list(formal.get("holdout_target_dates"), "holdout dates"))
        records = _list(formal.get("canonical_holdout_records"), "holdout records")
        if holdout_dates != common_dates or len(records) != HOLDOUT_OBSERVATIONS:
            raise ResearchResultExportError(f"Holdout alignment conflicts for {symbol}")
        if tuple(record.get("target_date") for record in records) != common_dates:
            raise ResearchResultExportError(f"Holdout record dates conflict for {symbol}")
        if any(record.get("company") != symbol for record in records):
            raise ResearchResultExportError(f"Holdout record company conflicts for {symbol}")
        indexed_rows = _list(index_by_symbol[symbol].get("rows"), "indexed holdout rows")
        if tuple(row.get("target_date") for row in indexed_rows) != common_dates:
            raise ResearchResultExportError(f"Supplementary holdout dates conflict for {symbol}")
        for formal_record, indexed_record in zip(records, indexed_rows):
            _exact_number(
                formal_record.get("actual_close"),
                indexed_record.get("actual_close"),
                f"{symbol} actual Close",
            )

        selected = _mapping(formal.get("selected_configurations"), "selected configs")
        tuning = _mapping(formal.get("tuning_and_fold_scores"), "tuning evidence")
        lir_selected = _mapping(selected.get("lag_reg"), "selected LIR")
        lir_fit = _mapping(lir_selected.get("development_fit"), "LIR development fit")
        alpha = _finite_number(lir_selected.get("alpha"), "selected LIR alpha")
        if _finite_number(lir_fit.get("alpha"), "LIR fit alpha") != alpha:
            raise ResearchResultExportError(f"LIR alpha conflicts for {symbol}")
        features = tuple(_list(lir_fit.get("selected_features"), "LIR selected features"))
        if any(not isinstance(value, str) or "|" in value or "\n" in value for value in features):
            raise ResearchResultExportError(f"Invalid LIR selected feature for {symbol}")
        lir_tuning = _mapping(tuning.get("lag_reg"), "LIR tuning")
        lir_mean = _selected_lir_mean(lir_tuning, alpha)
        boundary = _mapping(formal.get("lasso_boundary_metadata"), "LASSO boundary")
        if _finite_number(boundary.get("chosen_alpha"), "boundary alpha") != alpha:
            raise ResearchResultExportError(f"LASSO boundary alpha conflicts for {symbol}")
        boundary_status = boundary.get("classification")
        if boundary_status not in {"lower", "upper", "interior"}:
            raise ResearchResultExportError(f"Invalid LASSO boundary status for {symbol}")

        arima_selected = _mapping(selected.get("arima"), "selected ARIMA")
        order = tuple(_list(arima_selected.get("order"), "ARIMA order"))
        if (
            len(order) != 3
            or any(isinstance(value, bool) or not isinstance(value, int) for value in order)
            or not (0 <= order[0] <= 3 and 0 <= order[1] <= 2 and 0 <= order[2] <= 3)
        ):
            raise ResearchResultExportError(f"Invalid ARIMA order for {symbol}")
        trend = arima_selected.get("trend")
        if trend not in trends_by_d.get(order[1], ()):
            raise ResearchResultExportError(f"Invalid ARIMA trend for {symbol}")
        drift_enabled = arima_selected.get("drift_enabled")
        if not isinstance(drift_enabled, bool):
            raise ResearchResultExportError(f"Invalid ARIMA drift flag for {symbol}")
        arima_fit = _mapping(arima_selected.get("development_fit"), "ARIMA fit")
        if (
            tuple(arima_fit.get("order", ())) != order
            or arima_fit.get("trend") != trend
            or arima_fit.get("drift_enabled") is not drift_enabled
        ):
            raise ResearchResultExportError(f"ARIMA fit configuration conflicts for {symbol}")
        convergence = arima_fit.get("convergence_status")
        if convergence != "confirmed_converged":
            raise ResearchResultExportError(f"ARIMA development fit did not converge for {symbol}")
        arima_mean, _ = _validate_selected_candidate(
            _mapping(tuning.get("arima"), "ARIMA tuning"),
            {"order": list(order), "trend": trend, "drift_enabled": drift_enabled},
            "ARIMA",
            completion_key="completed_all_folds",
        )

        lstm_selected = _mapping(selected.get("lstm"), "selected LSTM")
        lstm_mean, lstm_std = _validate_selected_candidate(
            _mapping(tuning.get("lstm"), "LSTM tuning"), lstm_selected, "LSTM"
        )
        if lstm_std is None:
            raise ResearchResultExportError(f"LSTM validation variability is missing for {symbol}")
        epoch_metadata = _mapping(
            formal.get("lstm_seed_epoch_metadata"), "LSTM epoch metadata"
        )
        selected_epochs = _positive_integer(
            epoch_metadata.get("selected_epoch_count"), "LSTM selected epoch count"
        )
        if (
            tuple(epoch_metadata.get("tuning_seeds", ())) != tuning_seeds
            or epoch_metadata.get("final_seed") != 42
        ):
            raise ResearchResultExportError(f"LSTM seed metadata conflicts for {symbol}")
        stage_b = _mapping(epoch_metadata.get("stage_b"), "LSTM Stage B")
        for key in ("lookback", "hidden_size", "learning_rate", "batch_size"):
            if stage_b.get(key) != lstm_selected.get(key):
                raise ResearchResultExportError(f"LSTM Stage B {key} conflicts for {symbol}")
        if stage_b.get("selected_epoch_count") != selected_epochs or stage_b.get("seed") != 42:
            raise ResearchResultExportError(f"LSTM Stage B epoch/seed conflicts for {symbol}")

        configuration_rows.append(
            {
                "symbol": symbol,
                "company_name": company.name,
                "sector": company.sector,
                "lir_selected_alpha": alpha,
                "lir_selected_features": "|".join(features),
                "lir_selected_feature_count": len(features),
                "lir_selection_mean_validation_rmse": lir_mean,
                "lir_alpha_grid_boundary_status": boundary_status,
                "arima_p": order[0],
                "arima_d": order[1],
                "arima_q": order[2],
                "arima_trend": trend,
                "arima_drift_enabled": _bool_text(drift_enabled),
                "arima_selection_mean_validation_rmse": arima_mean,
                "arima_convergence_status": convergence,
                "lstm_lookback": _positive_integer(lstm_selected.get("lookback"), "lookback"),
                "lstm_hidden_size": _positive_integer(lstm_selected.get("hidden_size"), "hidden size"),
                "lstm_learning_rate": _finite_number(lstm_selected.get("learning_rate"), "learning rate"),
                "lstm_batch_size": _positive_integer(lstm_selected.get("batch_size"), "batch size"),
                "lstm_selection_mean_validation_rmse": lstm_mean,
                "lstm_validation_rmse_std": lstm_std,
                "lstm_selected_epoch_count": selected_epochs,
                "lstm_tuning_seeds": "|".join(str(value) for value in tuning_seeds),
                "lstm_final_seed": 42,
                "selection_criterion": SELECTION_CRITERION,
                "cv_splits": 5,
                "formal_run_id": FORMAL_RUN_ID,
                "formal_cutoff": FORMAL_CUTOFF,
                "formal_git_sha": FORMAL_GIT_SHA,
            }
        )

        formal_metrics = _mapping(formal.get("metrics"), "formal metrics")
        if set(formal_metrics) != set(METHODS):
            raise ResearchResultExportError(f"Formal metrics are incomplete for {symbol}")
        typed_metrics = {
            method: _mapping(formal_metrics[method], f"{symbol}/{method} metrics")
            for method in METHODS
        }
        selection = _selection_summary(typed_metrics)
        semantics = _mapping(
            semantics_by_symbol[symbol].get("descriptive_holdout"),
            "descriptive holdout semantics",
        )
        for key, expected in selection.items():
            if semantics.get(key) != expected:
                raise ResearchResultExportError(f"Holdout selection conflicts for {symbol}/{key}")
        semantics_metrics = _mapping(
            semantics_by_symbol[symbol].get("metrics"), "supplementary metrics"
        )

        audit = audit_by_symbol[symbol]
        denominator = _finite_number(
            audit.get("reconstructed_denominator"), f"{symbol} MASE denominator"
        )
        if denominator <= 0:
            raise ResearchResultExportError(f"Invalid MASE denominator for {symbol}")
        audit_methods = {
            item.get("model"): _mapping(item, "MASE method audit")
            for item in _list(audit.get("methods"), "MASE methods")
            if isinstance(item, Mapping)
        }
        if set(audit_methods) != set(METHODS):
            raise ResearchResultExportError(f"MASE audit methods conflict for {symbol}")

        company_within, company_benchmark, dm_statuses = _company_dm_rows(
            company=company,
            formal=formal,
            semantics=semantics_by_symbol[symbol],
        )
        within_rows.extend(company_within)
        benchmark_rows.extend(company_benchmark)

        rmse = {
            method: _finite_number(typed_metrics[method].get("rmse"), f"{symbol}/{method} RMSE")
            for method in METHODS
        }
        mase = {
            method: _finite_number(typed_metrics[method].get("mase"), f"{symbol}/{method} MASE")
            for method in METHODS
        }
        ranks = _principal_ranks(rmse)
        best_principal = str(selection["best_principal_model"])
        best_evaluated = str(selection["best_evaluated_method"])
        tie_policy = semantics.get("tie_policy")
        if not isinstance(tie_policy, str) or not tie_policy.startswith(TIE_POLICY_PREFIX):
            raise ResearchResultExportError(f"Tie policy conflicts for {symbol}")
        expected_semantics = {
            "symbol": symbol,
            "selection_metric": "rmse",
            "best_principal_rmse": rmse[best_principal],
            "best_evaluated_rmse": rmse[best_evaluated],
            "naive_rmse": rmse["naive"],
        }
        for key, expected in expected_semantics.items():
            if semantics.get(key) != expected:
                raise ResearchResultExportError(
                    f"Holdout reporting semantics conflict for {symbol}/{key}"
                )

        winner_rows.append(
            {
                "symbol": symbol,
                "company_name": company.name,
                "sector": company.sector,
                **{f"{method}_rmse": rmse[method] for method in METHODS},
                **{f"{method}_rank": ranks[method] for method in PRINCIPAL_METHODS},
                "best_principal_model": best_principal,
                "best_principal_rmse": rmse[best_principal],
                "best_evaluated_method": best_evaluated,
                "best_evaluated_rmse": rmse[best_evaluated],
                "best_principal_beats_naive": _bool_text(
                    bool(selection["best_principal_beats_naive"])
                ),
                "all_principals_worse_than_naive": _bool_text(
                    bool(selection["all_principals_worse_than_naive"])
                ),
                "winner_selection_metric": "rmse",
                "tie_policy": tie_policy,
                "formal_run_id": FORMAL_RUN_ID,
                "formal_cutoff": FORMAL_CUTOFF,
                "formal_git_sha": FORMAL_GIT_SHA,
            }
        )
        sector_rows.append(
            {
                "sector": company.sector,
                "symbol": symbol,
                "company_name": company.name,
                "best_principal_model": best_principal,
                "best_evaluated_method": best_evaluated,
                "best_principal_beats_naive": _bool_text(
                    bool(selection["best_principal_beats_naive"])
                ),
                **{f"{method}_rmse": rmse[method] for method in METHODS},
                **{f"{method}_mase": mase[method] for method in METHODS},
                **{f"{method}_rmse_rank": ranks[method] for method in PRINCIPAL_METHODS},
                **{
                    f"{method}_vs_naive_squared_status": dm_statuses[
                        (method, "squared_error")
                    ]
                    for method in PRINCIPAL_METHODS
                },
                **{
                    f"{method}_vs_naive_absolute_status": dm_statuses[
                        (method, "absolute_error")
                    ]
                    for method in PRINCIPAL_METHODS
                },
                "formal_run_id": FORMAL_RUN_ID,
                "formal_cutoff": FORMAL_CUTOFF,
                "formal_git_sha": FORMAL_GIT_SHA,
            }
        )

        for method in METHODS:
            metrics = typed_metrics[method]
            observations = _positive_integer(
                metrics.get("observations"), f"{symbol}/{method} observations"
            )
            if observations != HOLDOUT_OBSERVATIONS:
                raise ResearchResultExportError(f"Observation count conflicts for {symbol}/{method}")
            values = {
                key: _finite_number(metrics.get(key), f"{symbol}/{method} {key}")
                for key in ("rmse", "mae", "mase", "r2")
            }
            supplementary_metrics = _mapping(
                semantics_metrics.get(method), f"supplementary {method} metrics"
            )
            for key, value in (*values.items(), ("observations", observations)):
                _exact_number(supplementary_metrics.get(key), value, f"{symbol}/{method} {key}")
            method_audit = audit_methods[method]
            if method_audit.get("verified") is not True:
                raise ResearchResultExportError(f"Unverified MASE evidence for {symbol}/{method}")
            _exact_number(method_audit.get("stored_mae"), values["mae"], "stored MAE")
            _exact_number(method_audit.get("stored_mase"), values["mase"], "stored MASE")
            method_denominator = values["mae"] / values["mase"]
            tolerance = _finite_number(method_audit.get("tolerance"), "MASE tolerance")
            if not math.isclose(
                method_denominator,
                denominator,
                rel_tol=0.0,
                abs_tol=tolerance,
            ):
                raise ResearchResultExportError(
                    f"MASE denominator conflicts for {symbol}/{method}"
                )
            metric_rows.append(
                {
                    "symbol": symbol,
                    "company_name": company.name,
                    "sector": company.sector,
                    "method": method,
                    "holdout_start": HOLDOUT_START,
                    "holdout_end": HOLDOUT_END,
                    "observation_count": observations,
                    **values,
                    "mase_denominator": denominator,
                    "best_principal_model": selection["best_principal_model"],
                    "best_evaluated_method": selection["best_evaluated_method"],
                    "best_principal_beats_naive": _bool_text(
                        bool(selection["best_principal_beats_naive"])
                    ),
                    "all_principals_worse_than_naive": _bool_text(
                        bool(selection["all_principals_worse_than_naive"])
                    ),
                    "formal_run_id": FORMAL_RUN_ID,
                    "formal_cutoff": FORMAL_CUTOFF,
                    "formal_git_sha": FORMAL_GIT_SHA,
                }
            )

    across_rows = _build_across_company_rows(evidence, symbols)
    if (
        len(configuration_rows) != 15
        or len(metric_rows) != 60
        or len(benchmark_rows) != 90
        or len(within_rows) != 180
        or len(winner_rows) != 15
        or len(sector_rows) != 15
    ):
        raise ResearchResultExportError("Research-result row counts are incomplete")
    if len({(row["symbol"], row["method"]) for row in metric_rows}) != 60:
        raise ResearchResultExportError("Research-result metrics contain duplicates")
    if len({company.sector for company in canonical_companies}) != 5:
        raise ResearchResultExportError("Exactly five configured sectors are required")
    sector_counts = {
        sector: sum(company.sector == sector for company in canonical_companies)
        for sector in {company.sector for company in canonical_companies}
    }
    if set(sector_counts.values()) != {3}:
        raise ResearchResultExportError("Each configured sector must contain three companies")
    return ResearchRows(
        tuple(configuration_rows),
        tuple(metric_rows),
        tuple(benchmark_rows),
        tuple(within_rows),
        tuple(across_rows),
        tuple(winner_rows),
        tuple(sector_rows),
    )


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(columns),
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        if set(row) != set(columns):
            raise ResearchResultExportError("CSV row does not match the required schema")
        if any("\n" in str(value) or "\r" in str(value) for value in row.values()):
            raise ResearchResultExportError("CSV values cannot contain newlines")
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


@dataclass(frozen=True, slots=True)
class ParsedSubstantiveCsv:
    filename: str
    payload: bytes
    columns: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class PackageValidation:
    files: tuple[ParsedSubstantiveCsv, ...]
    manifest_rows: tuple[dict[str, object], ...]
    package_content_sha256: str
    principal_winner_counts: Mapping[str, int]
    best_evaluated_method_counts: Mapping[str, int]


def _csv_integer(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ResearchResultExportError(f"{label} must be an integer") from exc
    return parsed


def _csv_number(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ResearchResultExportError(f"{label} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ResearchResultExportError(f"{label} must be finite")
    return parsed


def _csv_boolean(value: str, label: str) -> bool:
    if value not in {"true", "false"}:
        raise ResearchResultExportError(f"{label} must be true or false")
    return value == "true"


def build_data_quality_rule_rows() -> tuple[dict[str, object], ...]:
    """Return the six predeclared rules without inspecting company outcomes."""

    common = {
        "rule_version": RULE_VERSION,
        "formal_run_id": FORMAL_RUN_ID,
        "formal_cutoff": FORMAL_CUTOFF,
        "formal_git_sha": FORMAL_GIT_SHA,
    }
    return (
        {
            "rule_name": "basic_ohlcv_validity",
            "rule_category": "hard",
            "measurement": (
                "required columns, canonical dates, finite numeric OHLCV, positive "
                "prices, non-negative volume, valid OHLC relationships, unique "
                "chronological dates"
            ),
            "pass_condition": "all structural checks pass",
            "review_condition": "",
            "fail_condition": "any structural validity check fails",
            "threshold_value": "",
            "threshold_unit": "",
            "effect_on_dataset_quality": "FAIL if rule fails",
            "notes": "dataset_quality_status depends on this hard rule",
            **common,
        },
        {
            "rule_name": "trading_session_continuity",
            "rule_category": "hard",
            "measurement": "observed dates compared with configured PSE trading calendar",
            "pass_condition": (
                "missing sessions = 0; unexpected sessions = 0; duplicate sessions = 0"
            ),
            "review_condition": "",
            "fail_condition": (
                "any missing, unexpected, or duplicate trading session exists"
            ),
            "threshold_value": "0",
            "threshold_unit": "session violations",
            "effect_on_dataset_quality": "FAIL if rule fails",
            "notes": "dataset_quality_status depends on this hard rule",
            **common,
        },
        {
            "rule_name": "zero_volume",
            "rule_category": "screening",
            "measurement": "count of formal sessions where Volume == 0",
            "pass_condition": "zero-volume count = 0",
            "review_condition": "zero-volume count > 0",
            "fail_condition": "",
            "threshold_value": "0",
            "threshold_unit": "sessions",
            "effect_on_dataset_quality": (
                "review only; does not cause dataset-quality FAIL"
            ),
            "notes": "",
            **common,
        },
        {
            "rule_name": "stale_price",
            "rule_category": "screening",
            "measurement": (
                "maximum consecutive sessions with identical full Open, High, Low, "
                "and Close"
            ),
            "pass_condition": "maximum identical-OHLC run < 5 sessions",
            "review_condition": "maximum identical-OHLC run >= 5 sessions",
            "fail_condition": "",
            "threshold_value": "5",
            "threshold_unit": "consecutive sessions",
            "effect_on_dataset_quality": (
                "review only; does not cause dataset-quality FAIL"
            ),
            "notes": (
                "threshold counts sessions, not transitions; Volume is excluded from "
                "equality; unchanged Close alone is insufficient"
            ),
            **common,
        },
        {
            "rule_name": "ohlcv_activity_proxy",
            "rule_category": "screening",
            "measurement": "active-session rate where active session means Volume > 0",
            "pass_condition": "active-session rate >= 0.95",
            "review_condition": "active-session rate < 0.95",
            "fail_condition": "",
            "threshold_value": "0.95",
            "threshold_unit": "proportion of sessions",
            "effect_on_dataset_quality": (
                "review only; does not cause dataset-quality FAIL"
            ),
            "notes": (
                "OHLCV-based activity/liquidity proxy; not a comprehensive "
                "market-liquidity measure"
            ),
            **common,
        },
        {
            "rule_name": "material_discontinuity",
            "rule_category": "screening",
            "measurement": "absolute simple close-to-close return",
            "pass_condition": "all absolute returns < 0.30",
            "review_condition": "any absolute return >= 0.30",
            "fail_condition": "",
            "threshold_value": "0.30",
            "threshold_unit": "absolute simple return",
            "effect_on_dataset_quality": (
                "review only; does not cause dataset-quality FAIL"
            ),
            "notes": (
                "A review flag is not an assertion of bad data or a corporate action."
            ),
            **common,
        },
    )


def build_principal_win_summary_rows(
    principal_winner_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, object], ...]:
    """Aggregate stored company winners without reading predictions or RMSE."""

    if len(principal_winner_rows) != len(COMPANIES):
        raise ResearchResultExportError(
            "Principal win summary requires exactly 15 company winner rows"
        )
    symbols = [row.get("symbol") for row in principal_winner_rows]
    if len(set(symbols)) != len(COMPANIES):
        raise ResearchResultExportError(
            "Principal win summary source contains duplicate companies"
        )
    counts = {method: 0 for method in PRINCIPAL_METHODS}
    for row in principal_winner_rows:
        method = row.get("best_principal_model")
        if method not in counts:
            raise ResearchResultExportError(
                f"Principal win summary source has invalid winner: {method!r}"
            )
        counts[method] += 1
    if sum(counts.values()) != len(COMPANIES):
        raise ResearchResultExportError("Principal win counts do not sum to 15")

    threshold = len(COMPANIES) // 2 + 1
    majority_models = [
        method for method in PRINCIPAL_METHODS if counts[method] >= threshold
    ]
    if len(majority_models) > 1:
        raise ResearchResultExportError(
            "More than one principal model reaches the strict-majority threshold"
        )
    majority_model = majority_models[0] if majority_models else ""
    interpretation = (
        "descriptive company-level win count; not a statistical significance test"
    )
    return tuple(
        {
            "model": method,
            "win_count": counts[method],
            "total_companies": len(COMPANIES),
            "win_share": counts[method] / len(COMPANIES),
            "strict_majority_threshold": threshold,
            "strict_majority_achieved": _bool_text(counts[method] >= threshold),
            "overall_majority_model": majority_model,
            "selection_metric": "rmse",
            "interpretation": interpretation,
            "formal_run_id": FORMAL_RUN_ID,
            "formal_cutoff": FORMAL_CUTOFF,
            "formal_git_sha": FORMAL_GIT_SHA,
        }
        for method in PRINCIPAL_METHODS
    )


def _parse_substantive_csv(filename: str, payload: bytes) -> ParsedSubstantiveCsv:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResearchResultExportError(f"{filename} is not valid UTF-8") from exc
    if "\x00" in text:
        raise ResearchResultExportError(f"{filename} contains a NUL byte")
    try:
        records = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        raise ResearchResultExportError(f"{filename} is malformed CSV: {exc}") from exc
    if not records:
        raise ResearchResultExportError(f"{filename} is empty")
    columns = tuple(records[0])
    expected_columns = SUBSTANTIVE_FILE_SCHEMAS[filename]
    if columns != expected_columns:
        raise ResearchResultExportError(f"{filename} header does not match its schema")
    if len(columns) != len(set(columns)):
        raise ResearchResultExportError(f"{filename} contains duplicate columns")
    if any(len(record) != len(columns) for record in records[1:]):
        raise ResearchResultExportError(f"{filename} contains a malformed row width")
    rows = tuple(dict(zip(columns, record)) for record in records[1:])
    expected_rows = SUBSTANTIVE_FILE_ROW_COUNTS[filename]
    if len(rows) != expected_rows:
        raise ResearchResultExportError(
            f"{filename} has {len(rows)} rows; expected {expected_rows}"
        )
    return ParsedSubstantiveCsv(
        filename=filename,
        payload=payload,
        columns=columns,
        rows=rows,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _load_substantive_csvs(
    output_dir: Path,
    *,
    staged_payloads: Mapping[str, bytes] | None = None,
) -> tuple[ParsedSubstantiveCsv, ...]:
    directory = Path(output_dir)
    if not directory.is_dir():
        raise ResearchResultExportError(
            f"Research-result directory is missing: {directory}"
        )
    allowed = set(SUBSTANTIVE_FILE_ORDER) | {"results_manifest.csv", "README.md"}
    unexpected = {item.name for item in directory.iterdir()} - allowed
    if unexpected:
        raise ResearchResultExportError(
            f"Research-result directory contains unexpected files: {sorted(unexpected)}"
        )
    staged = dict(staged_payloads or {})
    unexpected_staged = set(staged) - set(SUBSTANTIVE_FILE_ORDER)
    if unexpected_staged:
        raise ResearchResultExportError(
            f"Unexpected staged substantive CSVs: {sorted(unexpected_staged)}"
        )
    parsed: list[ParsedSubstantiveCsv] = []
    for filename in SUBSTANTIVE_FILE_ORDER:
        if filename in staged:
            payload = staged[filename]
        else:
            path = directory / filename
            if not path.is_file():
                raise ResearchResultExportError(
                    f"Required substantive CSV is missing: {filename}"
                )
            try:
                payload = path.read_bytes()
            except OSError as exc:
                raise ResearchResultExportError(
                    f"Cannot read substantive CSV: {filename}"
                ) from exc
        parsed.append(_parse_substantive_csv(filename, payload))
    return tuple(parsed)


def _validate_company_rows(
    files: Mapping[str, ParsedSubstantiveCsv],
) -> dict[str, Company]:
    if len(COMPANIES) != 15:
        raise ResearchResultExportError("Exactly 15 configured companies are required")
    companies = {company.symbol: company for company in COMPANIES}
    if len(companies) != 15:
        raise ResearchResultExportError("Configured company symbols are not unique")
    expected_symbols = set(companies)
    for filename, parsed in files.items():
        if "symbol" not in parsed.columns:
            continue
        symbols = {row["symbol"] for row in parsed.rows}
        if symbols != expected_symbols:
            raise ResearchResultExportError(
                f"{filename} has missing or unexpected company symbols"
            )
        for row in parsed.rows:
            company = companies[row["symbol"]]
            if row.get("company_name") != company.name:
                raise ResearchResultExportError(
                    f"{filename} company name conflicts for {company.symbol}"
                )
            if row.get("sector") != company.sector:
                raise ResearchResultExportError(
                    f"{filename} sector conflicts for {company.symbol}"
                )
    return companies


def _validate_formal_identity(files: Mapping[str, ParsedSubstantiveCsv]) -> None:
    expected = {
        "formal_run_id": FORMAL_RUN_ID,
        "formal_cutoff": FORMAL_CUTOFF,
        "formal_git_sha": FORMAL_GIT_SHA,
    }
    for filename, parsed in files.items():
        for row_number, row in enumerate(parsed.rows, start=2):
            for field, value in expected.items():
                if row.get(field) != value:
                    raise ResearchResultExportError(
                        f"{filename} row {row_number} has conflicting {field}"
                    )


def _validate_selected_configurations(parsed: ParsedSubstantiveCsv) -> None:
    if len({row["symbol"] for row in parsed.rows}) != 15:
        raise ResearchResultExportError(
            "selected_configurations.csv must contain one row per company"
        )
    for row in parsed.rows:
        symbol = row["symbol"]
        _csv_number(row["lir_selected_alpha"], f"{symbol} selected LIR alpha")
        feature_count = _csv_integer(
            row["lir_selected_feature_count"], f"{symbol} selected feature count"
        )
        features = [] if not row["lir_selected_features"] else row[
            "lir_selected_features"
        ].split("|")
        if feature_count != len(features):
            raise ResearchResultExportError(
                f"selected_configurations.csv LIR feature count conflicts for {symbol}"
            )
        if row["lir_alpha_grid_boundary_status"] not in {
            "lower",
            "upper",
            "interior",
        }:
            raise ResearchResultExportError(
                f"selected_configurations.csv LIR boundary status conflicts for {symbol}"
            )
        for field in ("arima_p", "arima_d", "arima_q"):
            _csv_integer(row[field], f"{symbol} {field}")
        if row["arima_trend"] not in {"n", "c", "t"}:
            raise ResearchResultExportError(
                f"selected_configurations.csv ARIMA trend conflicts for {symbol}"
            )
        if row["arima_convergence_status"] != "confirmed_converged":
            raise ResearchResultExportError(
                f"selected_configurations.csv ARIMA convergence conflicts for {symbol}"
            )
        for field in (
            "lstm_lookback",
            "lstm_hidden_size",
            "lstm_batch_size",
            "lstm_selected_epoch_count",
        ):
            if _csv_integer(row[field], f"{symbol} {field}") <= 0:
                raise ResearchResultExportError(f"{symbol} {field} must be positive")
        _csv_number(row["lstm_learning_rate"], f"{symbol} LSTM learning rate")
        if row["lstm_tuning_seeds"] != "11|29|47" or row["lstm_final_seed"] != "42":
            raise ResearchResultExportError(
                f"selected_configurations.csv LSTM seeds conflict for {symbol}"
            )


def _validate_holdout_metrics(
    parsed: ParsedSubstantiveCsv,
) -> dict[tuple[str, str], dict[str, str]]:
    indexed: dict[tuple[str, str], dict[str, str]] = {}
    for row in parsed.rows:
        key = (row["symbol"], row["method"])
        if key in indexed:
            raise ResearchResultExportError(
                f"holdout_metrics.csv contains duplicate row {key}"
            )
        indexed[key] = row
        for field in ("rmse", "mae", "mase", "r2", "mase_denominator"):
            _csv_number(row[field], f"{row['symbol']}/{row['method']} {field}")
    for company in COMPANIES:
        company_rows = {
            method: indexed.get((company.symbol, method)) for method in METHODS
        }
        if any(row is None for row in company_rows.values()):
            raise ResearchResultExportError(
                f"holdout_metrics.csv methods are incomplete for {company.symbol}"
            )
        typed_rows = tuple(row for row in company_rows.values() if row is not None)
        if {row["holdout_start"] for row in typed_rows} != {HOLDOUT_START}:
            raise ResearchResultExportError(
                f"holdout_metrics.csv start date conflicts for {company.symbol}"
            )
        if {row["holdout_end"] for row in typed_rows} != {HOLDOUT_END}:
            raise ResearchResultExportError(
                f"holdout_metrics.csv end date conflicts for {company.symbol}"
            )
        if {
            _csv_integer(
                row["observation_count"],
                f"{company.symbol}/{row['method']} observation count",
            )
            for row in typed_rows
        } != {HOLDOUT_OBSERVATIONS}:
            raise ResearchResultExportError(
                f"holdout_metrics.csv observation count conflicts for {company.symbol}"
            )
        if len({row["mase_denominator"] for row in typed_rows}) != 1:
            raise ResearchResultExportError(
                f"holdout_metrics.csv MASE denominator conflicts for {company.symbol}"
            )
    return indexed


def _validate_frozen_formal_csvs(
    predictions: ParsedSubstantiveCsv,
    scope: ParsedSubstantiveCsv,
) -> None:
    """Check frozen ledger/scope structure without recalculating research results."""

    symbols = tuple(company.symbol for company in COMPANIES)
    if tuple(row["symbol"] for row in scope.rows) != symbols:
        raise ResearchResultExportError("formal_scope.csv company order conflicts")
    if tuple(row["symbol"] for row in predictions.rows) != tuple(
        symbol for symbol in symbols for _ in range(HOLDOUT_OBSERVATIONS)
    ):
        raise ResearchResultExportError("holdout_predictions.csv company order conflicts")
    common_dates: tuple[str, ...] | None = None
    seen: set[tuple[str, str]] = set()
    for index, company in enumerate(COMPANIES):
        symbol = company.symbol
        row = scope.rows[index]
        if (
            row["raw_start"] != FORMAL_START
            or row["raw_end"] != FORMAL_CUTOFF
            or _csv_integer(row["raw_row_count"], "frozen raw row count") != FORMAL_ROWS_PER_COMPANY
            or row["holdout_start"] != HOLDOUT_START
            or row["holdout_end"] != HOLDOUT_END
            or _csv_integer(row["holdout_pair_count"], "holdout pair count") != HOLDOUT_OBSERVATIONS
            or _csv_integer(row["cv_split_count"], "CV split count") != 5
            or _csv_integer(row["forecast_horizon"], "forecast horizon") != 1
            or _csv_boolean(row["shuffle_used"], "shuffle policy")
        ):
            raise ResearchResultExportError(f"formal_scope.csv conflicts for {symbol}")
        development_count = _csv_integer(row["development_pair_count"], "development pair count")
        forecast_count = _csv_integer(row["forecast_pair_count"], "forecast pair count")
        if (
            development_count <= 0
            or forecast_count != development_count + HOLDOUT_OBSERVATIONS
            or forecast_count != FORMAL_ROWS_PER_COMPANY - 1
            or not (FORMAL_START < _strict_iso_date(row["development_start"], "development start")
                    <= _strict_iso_date(row["development_end"], "development end")
                    < HOLDOUT_START)
        ):
            raise ResearchResultExportError(f"formal_scope.csv pair scope conflicts for {symbol}")
        company_rows = predictions.rows[
            index * HOLDOUT_OBSERVATIONS : (index + 1) * HOLDOUT_OBSERVATIONS
        ]
        target_dates = tuple(item["target_date"] for item in company_rows)
        if (
            target_dates != tuple(sorted(set(target_dates)))
            or target_dates[0] != row["holdout_start"]
            or target_dates[-1] != row["holdout_end"]
            or (common_dates is not None and target_dates != common_dates)
        ):
            raise ResearchResultExportError(f"holdout_predictions.csv dates conflict for {symbol}")
        common_dates = target_dates
        for item in company_rows:
            key = (symbol, item["target_date"])
            if key in seen:
                raise ResearchResultExportError(f"Duplicate holdout prediction row: {key}")
            seen.add(key)
            origin = _strict_iso_date(item["origin_date"], "holdout origin")
            target = _strict_iso_date(item["target_date"], "holdout target")
            if origin >= target:
                raise ResearchResultExportError(f"Holdout origin is not earlier for {key}")
            for field in (
                "actual_close", "lag_reg_prediction", "arima_prediction",
                "lstm_prediction", "naive_prediction",
            ):
                _csv_number(item[field], f"{symbol}/{target} {field}")


def _validate_dm_files(
    benchmark: ParsedSubstantiveCsv,
    within: ParsedSubstantiveCsv,
) -> dict[tuple[str, str, str], dict[str, str]]:
    within_index: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in within.rows:
        key = (row["symbol"], row["model_1"], row["model_2"], row["loss_type"])
        if key in within_index:
            raise ResearchResultExportError(
                f"within_company_dm.csv contains duplicate row {key}"
            )
        within_index[key] = row
        if row["loss_type"] not in LOSS_TYPES:
            raise ResearchResultExportError(
                f"within_company_dm.csv has unexpected loss type for {row['symbol']}"
            )
        if _csv_integer(row["holm_family_size"], "DM Holm family size") != 6:
            raise ResearchResultExportError("DM Holm family size must equal 6")
    expected_within = {
        (company.symbol, model_1, model_2, loss_type)
        for company in COMPANIES
        for loss_type in LOSS_TYPES
        for model_1, model_2 in METHOD_PAIRS
    }
    if set(within_index) != expected_within:
        raise ResearchResultExportError(
            "within_company_dm.csv method pairs or loss families are incomplete"
        )

    benchmark_index: dict[tuple[str, str, str], dict[str, str]] = {}
    comparable_fields = (
        "sample_size",
        "mean_loss_differential",
        "dm_statistic",
        "raw_p_value",
        "holm_adjusted_p_value",
        "reject",
        "available",
        "unavailable_reason",
        "hac_lag",
        "forecast_horizon",
        "hln_correction_factor",
    )
    for row in benchmark.rows:
        key = (row["symbol"], row["model"], row["loss_type"])
        if key in benchmark_index or row["benchmark"] != "naive":
            raise ResearchResultExportError(
                f"benchmark_vs_naive_dm.csv contains duplicate or invalid row {key}"
            )
        benchmark_index[key] = row
        within_row = within_index.get(
            (row["symbol"], row["model"], "naive", row["loss_type"])
        )
        if within_row is None or any(
            row[field] != within_row[field] for field in comparable_fields
        ):
            raise ResearchResultExportError(
                "benchmark_vs_naive_dm.csv does not match within_company_dm.csv "
                f"for {key}"
            )
    expected_benchmark = {
        (company.symbol, method, loss_type)
        for company in COMPANIES
        for loss_type in LOSS_TYPES
        for method in PRINCIPAL_METHODS
    }
    if set(benchmark_index) != expected_benchmark:
        raise ResearchResultExportError(
            "benchmark_vs_naive_dm.csv is not the complete principal-versus-naive subset"
        )
    return benchmark_index


def _validate_across_company(parsed: ParsedSubstantiveCsv) -> None:
    friedman = [row for row in parsed.rows if row["test_name"] == "friedman"]
    wilcoxon = [row for row in parsed.rows if row["test_name"] == "wilcoxon"]
    if len(friedman) != 1 or len(wilcoxon) != 6:
        raise ResearchResultExportError(
            "across_company_tests.csv must contain one Friedman and six Wilcoxon rows"
        )
    omnibus = friedman[0]
    if (
        omnibus["metric"] != "mase"
        or _csv_integer(omnibus["company_count"], "Friedman company count") != 15
        or omnibus["performed"] != "true"
        or omnibus["reject"] != "false"
    ):
        raise ResearchResultExportError(
            "across_company_tests.csv Friedman evidence conflicts"
        )
    pairs = {(row["model_1"], row["model_2"]) for row in wilcoxon}
    if pairs != set(METHOD_PAIRS):
        raise ResearchResultExportError(
            "across_company_tests.csv Wilcoxon pairs conflict"
        )
    for row in wilcoxon:
        if (
            row["metric"] != "mase"
            or _csv_integer(row["company_count"], "Wilcoxon company count") != 15
            or row["performed"] != "false"
            or any(
                row[field]
                for field in (
                    "statistic",
                    "raw_p_value",
                    "holm_adjusted_p_value",
                    "reject",
                )
            )
        ):
            raise ResearchResultExportError(
                "across_company_tests.csv Wilcoxon gate conflicts"
            )


def _validate_winners(
    parsed: ParsedSubstantiveCsv,
    metrics: Mapping[tuple[str, str], Mapping[str, str]],
) -> tuple[dict[str, dict[str, str]], dict[str, int], dict[str, int]]:
    winners: dict[str, dict[str, str]] = {}
    principal_counts = {method: 0 for method in PRINCIPAL_METHODS}
    evaluated_counts = {method: 0 for method in METHODS}
    for row in parsed.rows:
        symbol = row["symbol"]
        if symbol in winners:
            raise ResearchResultExportError(
                f"principal_winners.csv contains duplicate company {symbol}"
            )
        rmse = {
            method: _csv_number(
                metrics[(symbol, method)]["rmse"], f"{symbol}/{method} RMSE"
            )
            for method in METHODS
        }
        for method in METHODS:
            if row[f"{method}_rmse"] != metrics[(symbol, method)]["rmse"]:
                raise ResearchResultExportError(
                    f"principal_winners.csv RMSE conflicts for {symbol}/{method}"
                )
        principal = min(
            PRINCIPAL_METHODS,
            key=lambda method: (rmse[method], PRINCIPAL_METHODS.index(method)),
        )
        evaluated = min(
            METHODS, key=lambda method: (rmse[method], METHODS.index(method))
        )
        if (
            row["best_principal_model"] != principal
            or row["best_evaluated_method"] != evaluated
            or row["best_principal_rmse"] != metrics[(symbol, principal)]["rmse"]
            or row["best_evaluated_rmse"] != metrics[(symbol, evaluated)]["rmse"]
            or row["winner_selection_metric"] != "rmse"
            or not row["tie_policy"].startswith(TIE_POLICY_PREFIX)
        ):
            raise ResearchResultExportError(
                f"principal_winners.csv winner conflicts for {symbol}"
            )
        expected_beats = rmse[principal] < rmse["naive"]
        expected_all_worse = all(
            rmse[method] > rmse["naive"] for method in PRINCIPAL_METHODS
        )
        if (
            _csv_boolean(
                row["best_principal_beats_naive"],
                f"{symbol} principal-beats-naive",
            )
            is not expected_beats
            or _csv_boolean(
                row["all_principals_worse_than_naive"],
                f"{symbol} all-principals-worse",
            )
            is not expected_all_worse
        ):
            raise ResearchResultExportError(
                f"principal_winners.csv benchmark flags conflict for {symbol}"
            )
        expected_ranks = _principal_ranks(
            {method: rmse[method] for method in PRINCIPAL_METHODS}
        )
        if any(
            _csv_integer(row[f"{method}_rank"], f"{symbol}/{method} rank")
            != expected_ranks[method]
            for method in PRINCIPAL_METHODS
        ):
            raise ResearchResultExportError(
                f"principal_winners.csv ranks conflict for {symbol}"
            )
        winners[symbol] = row
        principal_counts[principal] += 1
        evaluated_counts[evaluated] += 1
    return winners, principal_counts, evaluated_counts


def _benchmark_status(row: Mapping[str, str]) -> str:
    available = _csv_boolean(row["available"], "DM availability")
    reject = _csv_boolean(row["reject"], "DM rejection")
    if not available:
        return "unavailable"
    if not reject:
        return "not_significant"
    difference = _csv_number(row["mean_loss_differential"], "DM mean loss difference")
    if difference < 0:
        return "significantly_better"
    if difference > 0:
        return "significantly_worse"
    raise ResearchResultExportError("Rejected DM result has zero mean loss difference")


def _validate_sector_peers(
    parsed: ParsedSubstantiveCsv,
    metrics: Mapping[tuple[str, str], Mapping[str, str]],
    winners: Mapping[str, Mapping[str, str]],
    benchmark: Mapping[tuple[str, str, str], Mapping[str, str]],
) -> None:
    if len({row["symbol"] for row in parsed.rows}) != 15:
        raise ResearchResultExportError(
            "sector_peer_summary.csv must contain one row per company"
        )
    sector_counts: dict[str, int] = {}
    for row in parsed.rows:
        symbol = row["symbol"]
        sector_counts[row["sector"]] = sector_counts.get(row["sector"], 0) + 1
        winner = winners[symbol]
        for field in (
            "best_principal_model",
            "best_evaluated_method",
            "best_principal_beats_naive",
        ):
            if row[field] != winner[field]:
                raise ResearchResultExportError(
                    f"sector_peer_summary.csv winner conflicts for {symbol}/{field}"
                )
        for method in METHODS:
            if (
                row[f"{method}_rmse"] != metrics[(symbol, method)]["rmse"]
                or row[f"{method}_mase"] != metrics[(symbol, method)]["mase"]
            ):
                raise ResearchResultExportError(
                    f"sector_peer_summary.csv metrics conflict for {symbol}/{method}"
                )
        for method in PRINCIPAL_METHODS:
            if row[f"{method}_rmse_rank"] != winner[f"{method}_rank"]:
                raise ResearchResultExportError(
                    f"sector_peer_summary.csv rank conflicts for {symbol}/{method}"
                )
            for loss_type, suffix in (
                ("squared_error", "squared"),
                ("absolute_error", "absolute"),
            ):
                expected_status = _benchmark_status(
                    benchmark[(symbol, method, loss_type)]
                )
                if row[f"{method}_vs_naive_{suffix}_status"] != expected_status:
                    raise ResearchResultExportError(
                        "sector_peer_summary.csv benchmark status conflicts for "
                        f"{symbol}/{method}/{loss_type}"
                    )
    if len(sector_counts) != 5 or set(sector_counts.values()) != {3}:
        raise ResearchResultExportError(
            "sector_peer_summary.csv must contain five sectors with three companies each"
        )


def _validate_data_quality(parsed: ParsedSubstantiveCsv) -> None:
    if len({row["symbol"] for row in parsed.rows}) != 15:
        raise ResearchResultExportError(
            "data_quality.csv must contain one row per company"
        )
    screening_fields = (
        "zero_volume_status",
        "stale_price_status",
        "liquidity_status",
        "material_discontinuity_status",
    )
    for row in parsed.rows:
        symbol = row["symbol"]
        if (
            row["start_date"] != FORMAL_START
            or row["end_date"] != FORMAL_CUTOFF
            or _csv_integer(row["row_count"], f"{symbol} data-quality row count")
            != FORMAL_ROWS_PER_COMPANY
            or row["rule_version"] != RULE_VERSION
        ):
            raise ResearchResultExportError(
                f"data_quality.csv frozen contract conflicts for {symbol}"
            )
        hard_pass = (
            all(
                row[field] == "PASS"
                for field in (
                    "required_columns_status",
                    "numeric_validity_status",
                    "positive_price_status",
                    "ohlc_relationship_status",
                    "basic_validity_status",
                    "continuity_status",
                )
            )
            and _csv_integer(row["negative_volume_count"], "negative volume count")
            == 0
            and _csv_integer(row["duplicate_date_count"], "duplicate date count")
            == 0
            and _csv_integer(row["expected_session_count"], "expected session count")
            == FORMAL_ROWS_PER_COMPANY
            and _csv_integer(row["observed_session_count"], "observed session count")
            == FORMAL_ROWS_PER_COMPANY
            and _csv_integer(row["missing_session_count"], "missing session count")
            == 0
            and _csv_integer(row["unexpected_session_count"], "unexpected session count")
            == 0
        )
        if row["dataset_quality_status"] != ("PASS" if hard_pass else "FAIL"):
            raise ResearchResultExportError(
                f"data_quality.csv hard-check status conflicts for {symbol}"
            )
        review_required = any(row[field] == "REVIEW" for field in screening_fields)
        if (
            _csv_boolean(
                row["screening_review_required"],
                f"{symbol} screening review flag",
            )
            is not review_required
        ):
            raise ResearchResultExportError(
                f"data_quality.csv screening review flag conflicts for {symbol}"
            )


def _validate_data_quality_rules(parsed: ParsedSubstantiveCsv) -> None:
    expected_payload = _csv_bytes(
        DATA_QUALITY_RULE_COLUMNS,
        build_data_quality_rule_rows(),
    )
    expected = _parse_substantive_csv("data_quality_rules.csv", expected_payload)
    if parsed.rows != expected.rows:
        raise ResearchResultExportError(
            "data_quality_rules.csv conflicts with the locked data-quality-v1 rules"
        )
    categories = [row["rule_category"] for row in parsed.rows]
    if categories.count("hard") != 2 or categories.count("screening") != 4:
        raise ResearchResultExportError(
            "data_quality_rules.csv must contain two hard and four screening rules"
        )
    for row in parsed.rows:
        if row["rule_category"] == "hard":
            if row["fail_condition"] == "" or "FAIL" not in row[
                "effect_on_dataset_quality"
            ]:
                raise ResearchResultExportError(
                    f"Hard data-quality rule cannot fail: {row['rule_name']}"
                )
        elif (
            row["fail_condition"] != ""
            or row["effect_on_dataset_quality"]
            != "review only; does not cause dataset-quality FAIL"
        ):
            raise ResearchResultExportError(
                f"Screening rule incorrectly changes dataset quality: {row['rule_name']}"
            )


def _validate_principal_win_summary(
    parsed: ParsedSubstantiveCsv,
    winners: Mapping[str, Mapping[str, str]],
) -> None:
    expected_rows = build_principal_win_summary_rows(tuple(winners.values()))
    expected = _parse_substantive_csv(
        "principal_win_summary.csv",
        _csv_bytes(PRINCIPAL_WIN_SUMMARY_COLUMNS, expected_rows),
    )
    if parsed.rows != expected.rows:
        raise ResearchResultExportError(
            "principal_win_summary.csv conflicts with principal_winners.csv"
        )
    if tuple(row["model"] for row in parsed.rows) != PRINCIPAL_METHODS:
        raise ResearchResultExportError(
            "principal_win_summary.csv model order conflicts"
        )
    counts = [_csv_integer(row["win_count"], "principal win count") for row in parsed.rows]
    if sum(counts) != len(COMPANIES):
        raise ResearchResultExportError("Principal win summary counts do not sum to 15")
    majority_values = {row["overall_majority_model"] for row in parsed.rows}
    if len(majority_values) != 1:
        raise ResearchResultExportError(
            "Principal win summary majority model is inconsistent"
        )
    if any(
        phrase in row["interpretation"].lower()
        for row in parsed.rows
        for phrase in ("dominant", "statistically superior", "significantly better")
    ):
        raise ResearchResultExportError(
            "Principal win summary interpretation makes an inferential claim"
        )


def _build_research_closure_payloads(output_dir: Path) -> dict[str, bytes]:
    winner_path = Path(output_dir) / "principal_winners.csv"
    if not winner_path.is_file():
        raise ResearchResultExportError(
            "Required substantive CSV is missing: principal_winners.csv"
        )
    winner_file = _parse_substantive_csv(
        "principal_winners.csv",
        winner_path.read_bytes(),
    )
    return {
        "principal_win_summary.csv": _csv_bytes(
            PRINCIPAL_WIN_SUMMARY_COLUMNS,
            build_principal_win_summary_rows(winner_file.rows),
        ),
        "data_quality_rules.csv": _csv_bytes(
            DATA_QUALITY_RULE_COLUMNS,
            build_data_quality_rule_rows(),
        ),
    }


def validate_research_result_package(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    staged_payloads: Mapping[str, bytes] | None = None,
) -> PackageValidation:
    """Validate the frozen CSV package without recomputing research results."""

    parsed_files = _load_substantive_csvs(
        output_dir,
        staged_payloads=staged_payloads,
    )
    files = {parsed.filename: parsed for parsed in parsed_files}
    _validate_company_rows(files)
    _validate_formal_identity(files)
    _validate_selected_configurations(files["selected_configurations.csv"])
    metrics = _validate_holdout_metrics(files["holdout_metrics.csv"])
    benchmark = _validate_dm_files(
        files["benchmark_vs_naive_dm.csv"],
        files["within_company_dm.csv"],
    )
    _validate_across_company(files["across_company_tests.csv"])
    winners, principal_counts, evaluated_counts = _validate_winners(
        files["principal_winners.csv"], metrics
    )
    _validate_principal_win_summary(
        files["principal_win_summary.csv"],
        winners,
    )
    _validate_sector_peers(
        files["sector_peer_summary.csv"],
        metrics,
        winners,
        benchmark,
    )
    _validate_data_quality(files["data_quality.csv"])
    _validate_data_quality_rules(files["data_quality_rules.csv"])
    _validate_frozen_formal_csvs(
        files["holdout_predictions.csv"], files["formal_scope.csv"]
    )

    # The aggregate deliberately excludes results_manifest.csv to avoid
    # recursive self-reference. Each line is UTF-8 filename<TAB>sha256<LF>.
    package_source = "".join(
        f"{parsed.filename}\t{parsed.sha256}\n" for parsed in parsed_files
    ).encode("utf-8")
    package_hash = hashlib.sha256(package_source).hexdigest()
    manifest_rows = tuple(
        {
            "filename": parsed.filename,
            "purpose": SUBSTANTIVE_FILE_PURPOSES[parsed.filename],
            "row_count": len(parsed.rows),
            "column_count": len(parsed.columns),
            "sha256": parsed.sha256,
            "formal_run_id": FORMAL_RUN_ID,
            "formal_cutoff": FORMAL_CUTOFF,
            "formal_git_sha": FORMAL_GIT_SHA,
            "formal_archive_sha256": FORMAL_AGGREGATE_SHA256,
            "supplementary_package_id": (
                SUPPLEMENTARY_PACKAGE_ID
                if parsed.filename in SUPPLEMENTARY_DEPENDENT_FILES
                else ""
            ),
            "rule_version": (
                RULE_VERSION
                if parsed.filename in {"data_quality.csv", "data_quality_rules.csv"}
                else ""
            ),
            "source_scope": SUBSTANTIVE_FILE_SOURCE_SCOPES[parsed.filename],
            "validation_status": "PASS",
            "package_content_sha256": package_hash,
        }
        for parsed in parsed_files
    )
    return PackageValidation(
        files=parsed_files,
        manifest_rows=manifest_rows,
        package_content_sha256=package_hash,
        principal_winner_counts=principal_counts,
        best_evaluated_method_counts=evaluated_counts,
    )


def publish_research_closure(
    validation: PackageValidation,
    *,
    closure_payloads: Mapping[str, bytes],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    replace: Callable[[Path, Path], None] = os.replace,
) -> tuple[Path, ...]:
    """Publish both closure CSVs and the manifest with rollback protection."""

    destination = Path(output_dir)
    required_closure = {
        "data_quality_rules.csv",
        "principal_win_summary.csv",
    }
    if set(closure_payloads) != required_closure:
        raise ResearchResultExportError("Research closure payload set is incomplete")
    manifest_payload = _csv_bytes(MANIFEST_COLUMNS, validation.manifest_rows)
    parsed = list(
        csv.reader(io.StringIO(manifest_payload.decode("utf-8")), strict=True)
    )
    if (
        tuple(parsed[0]) != MANIFEST_COLUMNS
        or len(parsed[1:]) != len(SUBSTANTIVE_FILE_ORDER)
        or tuple(row[0] for row in parsed[1:]) != SUBSTANTIVE_FILE_ORDER
    ):
        raise ResearchResultExportError("Constructed results manifest is invalid")

    files_by_name = {item.filename: item for item in validation.files}
    for filename, payload in closure_payloads.items():
        if (
            filename not in files_by_name
            or files_by_name[filename].sha256
            != hashlib.sha256(payload).hexdigest()
        ):
            raise ResearchResultExportError(
                f"Validated closure payload conflicts for {filename}"
            )

    publication_order = (
        "data_quality_rules.csv",
        "principal_win_summary.csv",
        "results_manifest.csv",
    )
    payloads = {
        **closure_payloads,
        "results_manifest.csv": manifest_payload,
    }
    staging = Path(
        tempfile.mkdtemp(prefix=".research-closure-staging-", dir=destination)
    )
    backup = Path(
        tempfile.mkdtemp(prefix=".research-closure-backup-", dir=destination)
    )
    backed_up: list[str] = []
    published: list[str] = []
    try:
        for filename in publication_order:
            target = staging / filename
            target.write_bytes(payloads[filename])
        for filename in publication_order:
            target = destination / filename
            if target.exists():
                replace(target, backup / filename)
                backed_up.append(filename)
        for filename in publication_order:
            replace(staging / filename, destination / filename)
            published.append(filename)
    except Exception as exc:
        for filename in published:
            (destination / filename).unlink(missing_ok=True)
        for filename in reversed(backed_up):
            archived = backup / filename
            if archived.exists():
                os.replace(archived, destination / filename)
        if isinstance(exc, ResearchResultExportError):
            raise
        raise ResearchResultExportError(
            "Atomic research-closure publication failed"
        ) from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
    return tuple(destination / filename for filename in publication_order)


def export_results_manifest(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, PackageValidation]:
    """Build, validate, and publish the deterministic evidence closure."""

    LOGGER.info("Building two deterministic research-evidence closure CSVs")
    closure_payloads = _build_research_closure_payloads(output_dir)
    LOGGER.info("Validating substantive research-result CSVs")
    validation = validate_research_result_package(
        output_dir,
        staged_payloads=closure_payloads,
    )
    paths = publish_research_closure(
        validation,
        closure_payloads=closure_payloads,
        output_dir=output_dir,
    )
    manifest_path = paths[-1]
    LOGGER.info(
        "Published research closure files=%d manifest_rows=%d package_sha256=%s "
        "principal_winners=%s evaluated_winners=%s output=%s",
        len(paths),
        len(validation.manifest_rows),
        validation.package_content_sha256,
        dict(validation.principal_winner_counts),
        dict(validation.best_evaluated_method_counts),
        output_dir,
    )
    return manifest_path, validation


def publish_research_rows(
    rows: ResearchRows,
    *,
    data_quality_rows: Sequence[Mapping[str, object]],
    holdout_prediction_rows: Sequence[Mapping[str, object]],
    formal_scope_rows: Sequence[Mapping[str, object]],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    replace: Callable[[Path, Path], None] = os.replace,
) -> tuple[Path, ...]:
    """Publish all validated CSVs as one rollback-protected directory swap."""

    destination = Path(output_dir)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_dir():
            raise ResearchResultExportError("Research-result output path is not a directory")
        unexpected = {item.name for item in destination.iterdir()} - (
            set(SUBSTANTIVE_FILE_ORDER) | {"results_manifest.csv", "README.md"}
        )
        if unexpected:
            raise ResearchResultExportError(
                f"Research-result directory contains unexpected files: {sorted(unexpected)}"
            )

    payloads = {
        "selected_configurations.csv": _csv_bytes(
            CONFIGURATION_COLUMNS, rows.configurations
        ),
        "holdout_metrics.csv": _csv_bytes(METRIC_COLUMNS, rows.metrics),
        "benchmark_vs_naive_dm.csv": _csv_bytes(
            BENCHMARK_DM_COLUMNS, rows.benchmark_dm
        ),
        "within_company_dm.csv": _csv_bytes(
            WITHIN_COMPANY_DM_COLUMNS, rows.within_company_dm
        ),
        "across_company_tests.csv": _csv_bytes(
            ACROSS_COMPANY_COLUMNS, rows.across_company
        ),
        "principal_winners.csv": _csv_bytes(
            PRINCIPAL_WINNER_COLUMNS, rows.principal_winners
        ),
        "sector_peer_summary.csv": _csv_bytes(
            SECTOR_PEER_COLUMNS, rows.sector_peers
        ),
        "data_quality.csv": _csv_bytes(
            DATA_QUALITY_COLUMNS, data_quality_rows
        ),
    }
    payloads["holdout_predictions.csv"] = _csv_bytes(
        HOLDOUT_PREDICTION_COLUMNS, holdout_prediction_rows
    )
    payloads["formal_scope.csv"] = _csv_bytes(
        FORMAL_SCOPE_COLUMNS, formal_scope_rows
    )
    expected_counts = {
        "selected_configurations.csv": 15,
        "holdout_metrics.csv": 60,
        "benchmark_vs_naive_dm.csv": 90,
        "within_company_dm.csv": 180,
        "across_company_tests.csv": len(rows.across_company),
        "principal_winners.csv": 15,
        "sector_peer_summary.csv": 15,
        "data_quality.csv": 15,
    }
    expected_counts["holdout_predictions.csv"] = 15 * HOLDOUT_OBSERVATIONS
    expected_counts["formal_scope.csv"] = 15
    new_files = {
        name: _parse_substantive_csv(name, payloads[name])
        for name in ("holdout_predictions.csv", "formal_scope.csv")
    }
    _validate_company_rows(new_files)
    _validate_formal_identity(new_files)
    _validate_frozen_formal_csvs(
        new_files["holdout_predictions.csv"], new_files["formal_scope.csv"]
    )
    staging = Path(tempfile.mkdtemp(prefix=".research-result-staging-", dir=parent))
    backup: Path | None = None
    try:
        readme_path = destination / "README.md"
        if readme_path.is_file():
            shutil.copyfile(readme_path, staging / "README.md")
        for name, payload in payloads.items():
            target = staging / name
            target.write_bytes(payload)
            with target.open("r", encoding="utf-8", newline="") as source:
                parsed = list(csv.DictReader(source))
            expected_rows = expected_counts[name]
            if len(parsed) != expected_rows:
                raise ResearchResultExportError(f"Staged {name} failed row validation")
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix=".research-result-backup-", dir=parent))
            backup.rmdir()
            replace(destination, backup)
        try:
            replace(staging, destination)
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                replace(backup, destination)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
    except Exception as exc:
        if staging.exists():
            shutil.rmtree(staging)
        if isinstance(exc, ResearchResultExportError):
            raise
        raise ResearchResultExportError("Atomic research-result publication failed") from exc
    return tuple(destination / name for name in payloads)


def export_research_results(
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    supplementary_runs_root: Path = DEFAULT_SUPPLEMENTARY_RUNS_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, ...]:
    """Perform a read-only evidence transform followed by all-or-neither publication."""

    LOGGER.info("Loading frozen formal and linked supplementary evidence")
    evidence = load_authoritative_evidence(
        formal_runs_root=formal_runs_root,
        supplementary_runs_root=supplementary_runs_root,
    )
    LOGGER.info("Validating evidence and building all research-result datasets")
    rows = build_research_rows(evidence)
    frozen_scope = load_frozen_formal_scope(formal_runs_root=formal_runs_root)
    holdout_prediction_rows, formal_scope_rows = build_frozen_formal_rows(frozen_scope)
    data_quality_rows = build_frozen_data_quality_rows(
        formal_runs_root=formal_runs_root
    )
    paths = publish_research_rows(
        rows,
        data_quality_rows=data_quality_rows,
        holdout_prediction_rows=holdout_prediction_rows,
        formal_scope_rows=formal_scope_rows,
        output_dir=output_dir,
    )
    LOGGER.info(
        "Published research-result CSVs configurations=%d metrics=%d dm=%d/%d "
        "across=%d winners=%d sectors=%d data_quality=%d output=%s",
        len(rows.configurations),
        len(rows.metrics),
        len(rows.benchmark_dm),
        len(rows.within_company_dm),
        len(rows.across_company),
        len(rows.principal_winners),
        len(rows.sector_peers),
        len(data_quality_rows),
        output_dir,
    )
    manifest_path, _ = export_results_manifest(output_dir=output_dir)
    return (*paths, manifest_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-runs-root", type=Path, default=DEFAULT_FORMAL_RUNS_ROOT)
    parser.add_argument(
        "--supplementary-runs-root",
        type=Path,
        default=DEFAULT_SUPPLEMENTARY_RUNS_ROOT,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Validate existing substantive CSVs and publish only results_manifest.csv",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    try:
        if arguments.manifest_only:
            export_results_manifest(output_dir=arguments.output_dir)
        else:
            export_research_results(
                formal_runs_root=arguments.formal_runs_root,
                supplementary_runs_root=arguments.supplementary_runs_root,
                output_dir=arguments.output_dir,
            )
    except ResearchResultExportError:
        LOGGER.exception("Research-result export failed closed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
