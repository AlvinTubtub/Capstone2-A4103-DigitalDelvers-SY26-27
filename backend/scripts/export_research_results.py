"""Export frozen formal selections and holdout metrics to deterministic CSV files."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import csv
from dataclasses import dataclass
from datetime import date, timedelta
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


def publish_research_rows(
    rows: ResearchRows,
    *,
    data_quality_rows: Sequence[Mapping[str, object]],
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
        unexpected = {item.name for item in destination.iterdir()} - {
            "selected_configurations.csv",
            "holdout_metrics.csv",
            "benchmark_vs_naive_dm.csv",
            "within_company_dm.csv",
            "across_company_tests.csv",
            "principal_winners.csv",
            "sector_peer_summary.csv",
            "data_quality.csv",
        }
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
    staging = Path(tempfile.mkdtemp(prefix=".research-result-staging-", dir=parent))
    backup: Path | None = None
    try:
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
    data_quality_rows = build_frozen_data_quality_rows(
        formal_runs_root=formal_runs_root
    )
    paths = publish_research_rows(
        rows,
        data_quality_rows=data_quality_rows,
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
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-runs-root", type=Path, default=DEFAULT_FORMAL_RUNS_ROOT)
    parser.add_argument(
        "--supplementary-runs-root",
        type=Path,
        default=DEFAULT_SUPPLEMENTARY_RUNS_ROOT,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    try:
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
