"""Export frozen formal selections and holdout metrics to deterministic CSV files."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import csv
from dataclasses import dataclass
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
from src.evaluation.supplementary_archive import SupplementaryEvidenceArchive
from src.formal.archive import FormalRunArchive
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
METHODS: Final[tuple[str, ...]] = ("lag_reg", "arima", "lstm", "naive")
PRINCIPAL_METHODS: Final[tuple[str, ...]] = METHODS[:3]
SELECTION_CRITERION: Final[str] = "mean_validation_rmse"

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


@dataclass(frozen=True, slots=True)
class ResearchRows:
    configurations: tuple[dict[str, object], ...]
    metrics: tuple[dict[str, object], ...]


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
    )


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

    if len(configuration_rows) != 15 or len(metric_rows) != 60:
        raise ResearchResultExportError("Research-result row counts are incomplete")
    if len({(row["symbol"], row["method"]) for row in metric_rows}) != 60:
        raise ResearchResultExportError("Research-result metrics contain duplicates")
    return ResearchRows(tuple(configuration_rows), tuple(metric_rows))


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
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    replace: Callable[[Path, Path], None] = os.replace,
) -> tuple[Path, Path]:
    """Publish both validated CSVs as one rollback-protected directory swap."""

    destination = Path(output_dir)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_dir():
            raise ResearchResultExportError("Research-result output path is not a directory")
        unexpected = {
            item.name for item in destination.iterdir()
        } - {"selected_configurations.csv", "holdout_metrics.csv"}
        if unexpected:
            raise ResearchResultExportError(
                f"Research-result directory contains unexpected files: {sorted(unexpected)}"
            )

    payloads = {
        "selected_configurations.csv": _csv_bytes(
            CONFIGURATION_COLUMNS, rows.configurations
        ),
        "holdout_metrics.csv": _csv_bytes(METRIC_COLUMNS, rows.metrics),
    }
    staging = Path(tempfile.mkdtemp(prefix=".research-result-staging-", dir=parent))
    backup: Path | None = None
    try:
        for name, payload in payloads.items():
            target = staging / name
            target.write_bytes(payload)
            with target.open("r", encoding="utf-8", newline="") as source:
                parsed = list(csv.DictReader(source))
            expected_rows = 15 if name == "selected_configurations.csv" else 60
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
    return (
        destination / "selected_configurations.csv",
        destination / "holdout_metrics.csv",
    )


def export_research_results(
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    supplementary_runs_root: Path = DEFAULT_SUPPLEMENTARY_RUNS_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Perform a read-only evidence transform followed by all-or-neither publication."""

    LOGGER.info("Loading frozen formal and linked supplementary evidence")
    evidence = load_authoritative_evidence(
        formal_runs_root=formal_runs_root,
        supplementary_runs_root=supplementary_runs_root,
    )
    LOGGER.info("Validating evidence and building both research-result datasets")
    rows = build_research_rows(evidence)
    paths = publish_research_rows(rows, output_dir=output_dir)
    LOGGER.info(
        "Published research-result CSVs configurations=%d metrics=%d output=%s",
        len(rows.configurations),
        len(rows.metrics),
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
