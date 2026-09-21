"""Read-only derivation and validation of Phase A-C supplementary evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import csv
import json
import math
from pathlib import Path

from config.companies import COMPANIES
from config.ledger_config import DEFAULT_FORECAST_LEDGER_PATH
from config.model_config import ModelId, RegressionFeatureConfig
from config.settings import manila_now
from src.evaluation.arima_diagnostic_reconstruction import (
    ARIMA_DIAGNOSTIC_STATUS_SCHEMA_ID,
    ARIMA_DIAGNOSTIC_STATUS_SCHEMA_VERSION,
    DIAGNOSTIC_ONLY_REFIT_MODE,
    FROZEN_PARAMETER_DIAGNOSTIC_MODE,
    arima_config_as_dict,
    reconstruct_arima_diagnostic_status_payload,
    reconstruct_frozen_arima_config,
)
from src.evaluation.change_diagnostics import archived_change_diagnostics
from src.evaluation.metrics import EvaluationMetrics, compute_mase_denominator
from src.evaluation.model_selection import select_company_models
from src.evaluation.reporting_semantics import (
    build_descriptive_holdout_conclusion,
    build_production_deployment_conclusion,
    build_prospective_validation_conclusion,
    build_significance_conclusion,
)
from src.evaluation.statistical_tests import (
    DMTestResult,
    LossType,
    MODEL_PAIRS,
    WithinCompanyDMTests,
    compare_methods_across_companies,
)
from src.evaluation.supplementary_archive import (
    EVIDENCE_PATHS,
    SUPPLEMENTARY_EVIDENCE_SCHEMA_ID,
    SUPPLEMENTARY_EVIDENCE_SCHEMA_VERSION,
    SupplementaryEvidenceArchive,
    VerificationResult,
)
from src.features.regression_features import regression_feature_contract
from src.formal.archive import FormalRunArchive
from src.formal.provenance import capture_environment, capture_git_state, sha256_file
from src.formal.schema import FormalRunState
from src.formal.validation import DEFAULT_FORMAL_RUNS_ROOT
from src.ledger.store import ForecastLedger
from src.monitoring.drift import monitor_company_drift
from src.models.arima import (
    ArimaSpecification,
    ConvergenceStatus,
    candidate_specifications,
)


MASE_AUDIT_TOLERANCE = 1e-12
ARIMA_UNAVAILABLE_REASON = (
    "enhanced_standardized_fitted_residuals_unavailable_from_retained_formal_evidence"
)


class SupplementaryEvidenceError(RuntimeError):
    """Raised when source evidence is incomplete, inconsistent, or unsafe."""


@dataclass(frozen=True, slots=True)
class SupplementaryEvidencePlan:
    formal_run_id: str
    formal_aggregate_sha256: str
    ledger_sha256: str | None
    payloads: Mapping[str, Mapping[str, object]]

    @property
    def planned_files(self) -> tuple[str, ...]:
        return tuple(sorted(("run.json", "state.json", *self.payloads, "integrity_manifest.json")))


def _load_json(path: Path) -> dict[str, object]:
    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant: {value}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, ValueError) as exc:
        raise SupplementaryEvidenceError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SupplementaryEvidenceError(f"Expected JSON object: {path}")
    return payload


def _metrics(company: Mapping[str, object]) -> dict[ModelId, EvaluationMetrics]:
    source = company.get("metrics")
    if not isinstance(source, dict):
        raise SupplementaryEvidenceError("Company metrics are missing")
    result: dict[ModelId, EvaluationMetrics] = {}
    for model in ModelId:
        item = source.get(model.value)
        if not isinstance(item, dict):
            raise SupplementaryEvidenceError(f"Missing metrics for {model.value}")
        try:
            result[model] = EvaluationMetrics(
                rmse=float(item["rmse"]),
                mae=float(item["mae"]),
                mase=float(item["mase"]),
                r2=float(item["r2"]),
                observations=int(item["observations"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SupplementaryEvidenceError(f"Malformed metrics for {model.value}") from exc
    return result


def _parse_dm_item(item: Mapping[str, object], expected_loss: LossType) -> DMTestResult:
    try:
        result = DMTestResult(
            model_1=ModelId(str(item["model_1"])),
            model_2=ModelId(str(item["model_2"])),
            loss_type=LossType(str(item["loss_type"])),
            sample_size=int(item["sample_size"]),
            dm_statistic=None if item["dm_statistic"] is None else float(item["dm_statistic"]),
            raw_p_value=float(item["raw_p_value"]),
            holm_adjusted_p_value=float(item["holm_adjusted_p_value"]),
            reject=bool(item["reject"]),
            hac_lag=int(item["hac_lag"]),
            forecast_horizon=int(item["forecast_horizon"]),
            hln_correction_factor=float(item["hln_correction_factor"]),
            mean_loss_differential=float(item["mean_loss_differential"]),
            long_run_variance=float(item["long_run_variance"]),
            available=bool(item["available"]),
            unavailable_reason=(
                None if item.get("unavailable_reason") is None else str(item["unavailable_reason"])
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplementaryEvidenceError("Malformed archived DM result") from exc
    if result.loss_type is not expected_loss:
        raise SupplementaryEvidenceError("Archived DM loss family is inconsistent")
    return result


def deserialize_archived_dm(company: Mapping[str, object]) -> WithinCompanyDMTests:
    try:
        source = company["statistical_tests"]["diebold_mariano"]
        families = source["holm_families"]
        alpha = float(source["alpha"])
        symbol = str(source["company"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplementaryEvidenceError("Archived DM evidence is missing") from exc
    parsed: dict[LossType, tuple[DMTestResult, ...]] = {}
    for loss in LossType:
        items = families.get(loss.value) if isinstance(families, dict) else None
        if not isinstance(items, list):
            raise SupplementaryEvidenceError(f"Archived DM family missing: {loss.value}")
        results = tuple(_parse_dm_item(item, loss) for item in items if isinstance(item, dict))
        if tuple((item.model_1, item.model_2) for item in results) != MODEL_PAIRS:
            raise SupplementaryEvidenceError(f"Archived DM pairs are incomplete: {loss.value}")
        parsed[loss] = results
    return WithinCompanyDMTests(symbol, alpha, parsed[LossType.SQUARED_ERROR], parsed[LossType.ABSOLUTE_ERROR])


def _feature_config(payload: Mapping[str, object]) -> RegressionFeatureConfig:
    try:
        return RegressionFeatureConfig(
            return_lags=tuple(int(value) for value in payload["return_lags"]),
            rolling_return_windows=tuple(int(value) for value in payload["rolling_return_windows"]),
            volume_windows=tuple(int(value) for value in payload["volume_windows"]),
            rsi_period=int(payload["rsi_period"]),
            ema_fast_period=int(payload["ema_fast_period"]),
            ema_slow_period=int(payload["ema_slow_period"]),
            macd_signal_period=int(payload["macd_signal_period"]),
            bollinger_window=int(payload["bollinger_window"]),
            bollinger_standard_deviations=float(payload["bollinger_standard_deviations"]),
            raw_price_lags=tuple(int(value) for value in payload["raw_price_lags"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplementaryEvidenceError("Frozen LIR feature configuration is malformed") from exc


def _read_development_closes(
    raw_path: Path,
    development_dates: Sequence[str],
) -> tuple[float, ...]:
    with raw_path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    by_date = {str(row["Date"]): float(row["Close"]) for row in rows}
    requested = tuple(str(value) for value in development_dates)
    if not requested:
        raise SupplementaryEvidenceError("Development target dates are empty")
    raw_dates = tuple(str(row["Date"]) for row in rows)
    try:
        end_index = raw_dates.index(requested[-1])
    except ValueError as exc:
        raise SupplementaryEvidenceError("Development boundary is absent from frozen raw") from exc
    observed_targets = raw_dates[1 : end_index + 1]
    if observed_targets != requested:
        raise SupplementaryEvidenceError(
            "Frozen development target dates do not map exactly to frozen raw history"
        )
    return tuple(float(rows[index]["Close"]) for index in range(end_index + 1))


def _ledger_payloads(ledger_path: Path, symbols: Sequence[str]) -> tuple[dict[str, object], dict[str, object], str | None]:
    ledger = ForecastLedger(ledger_path)
    snapshot = ledger.read()
    digest = sha256_file(ledger_path) if ledger_path.is_file() else None
    event_count = issuance_count = outcome_count = 0
    if ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event_count += 1
            event_type = json.loads(line).get("event_type")
            issuance_count += event_type == "forecast_issued"
            outcome_count += event_type == "forecast_outcome_observed"
    resolved_dates = [record.issuance.target_date.isoformat() for record in snapshot.resolved]
    pending_dates = [record.issuance.target_date.isoformat() for record in snapshot.pending]
    source = {
        "schema_id": "forecastph.supplementary-prospective-source",
        "schema_version": 1,
        "evidence_source": "forecast_ledger_only",
        "ledger_path": str(ledger_path),
        "ledger_sha256": digest,
        "generated_at": manila_now().isoformat(),
        "event_count": event_count,
        "issuance_count": issuance_count,
        "outcome_count": outcome_count,
        "resolved_forecast_record_count": len(snapshot.resolved),
        "pending_forecast_record_count": len(snapshot.pending),
        "latest_resolved_target_date": max(resolved_dates, default=None),
        "latest_pending_target_date": max(pending_dates, default=None),
        "excluded_sources": ["backend/data/post_formal_history", "post_formal_backfill"],
    }
    reports = []
    for symbol in symbols:
        drift = monitor_company_drift(snapshot, symbol)
        reports.append(
            {
                "symbol": symbol,
                "drift_report": drift.as_dict(),
                "reporting_conclusion": build_prospective_validation_conclusion(drift).as_dict(),
            }
        )
    prospective = {
        "schema_id": "forecastph.supplementary-prospective-validation",
        "schema_version": 1,
        "evidence_source": "resolved_prospective_forecast_ledger_only",
        "company_order": list(symbols),
        "companies": reports,
        "deployment_approved": False,
        "automatic_training": False,
        "automatic_refit": False,
        "automatic_promotion": False,
    }
    return source, prospective, digest


def build_supplementary_evidence_plan(
    formal_run_id: str,
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    ledger_path: Path = DEFAULT_FORECAST_LEDGER_PATH,
    code_provenance: Mapping[str, object] | None = None,
) -> SupplementaryEvidencePlan:
    """Build every payload in memory; never write source or destination files."""

    archive = FormalRunArchive(formal_run_id, root=formal_runs_root)
    if not archive.verify_integrity() or archive.state is not FormalRunState.FINALIZED:
        raise SupplementaryEvidenceError("Formal source must be FINALIZED and pass integrity")
    manifest_path = archive.path / "integrity_manifest.json"
    manifest = _load_json(manifest_path)
    run = _load_json(archive.path / "run.json")
    aggregate = str(manifest.get("aggregate_sha256", ""))
    symbols_value = run.get("expected_symbols")
    if not isinstance(symbols_value, list) or not symbols_value:
        raise SupplementaryEvidenceError("Formal source company manifest is missing")
    symbols = tuple(str(value) for value in symbols_value)

    companies: dict[str, dict[str, object]] = {}
    common_dates: tuple[str, ...] | None = None
    actual_rows: list[dict[str, object]] = []
    metrics_by_company: dict[str, dict[ModelId, EvaluationMetrics]] = {}
    diagnostics: list[dict[str, object]] = []
    mase_audits: list[dict[str, object]] = []
    reporting: list[dict[str, object]] = []
    lir_companies: list[dict[str, object]] = []
    feature_contract_payload: dict[str, object] | None = None
    frozen_feature_config: dict[str, object] | None = None

    prospective_source, prospective_payload, ledger_sha = _ledger_payloads(Path(ledger_path), symbols)
    prospective_by_symbol = {
        str(item["symbol"]): item["reporting_conclusion"]
        for item in prospective_payload["companies"]
    }

    for symbol in symbols:
        company = _load_json(archive.path / "companies" / symbol / "evidence.json")
        companies[symbol] = company
        holdout_dates = tuple(str(value) for value in company.get("holdout_target_dates", ()))
        records = company.get("canonical_holdout_records")
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise SupplementaryEvidenceError(f"Malformed holdout records for {symbol}")
        record_dates = tuple(str(item.get("target_date")) for item in records)
        if record_dates != holdout_dates or record_dates != tuple(sorted(set(record_dates))):
            raise SupplementaryEvidenceError(f"Unaligned holdout dates for {symbol}")
        if common_dates is None:
            common_dates = holdout_dates
        elif holdout_dates != common_dates:
            raise SupplementaryEvidenceError(f"Holdout dates differ across companies at {symbol}")
        actual_rows.append(
            {
                "symbol": symbol,
                "rows": [
                    {"target_date": item["target_date"], "actual_close": item["actual_close"]}
                    for item in records
                ],
            }
        )
        company_metrics = _metrics(company)
        metrics_by_company[symbol] = company_metrics
        diagnostics.extend(
            item.as_dict()
            for item in archived_change_diagnostics(
                symbol, records, archive.path / "frozen_raw" / f"{symbol}.csv"
            )
        )
        development_dates = tuple(str(value) for value in company["development_target_dates"])
        closes = _read_development_closes(
            archive.path / "frozen_raw" / f"{symbol}.csv", development_dates
        )
        denominator = compute_mase_denominator(closes)
        method_audits = []
        for model in ModelId:
            metric = company_metrics[model]
            reconstructed = metric.mae / denominator
            difference = abs(metric.mase - reconstructed)
            method_audits.append(
                {
                    "model": model.value,
                    "stored_mae": metric.mae,
                    "stored_mase": metric.mase,
                    "reconstructed_mase": reconstructed,
                    "absolute_difference": difference,
                    "tolerance": MASE_AUDIT_TOLERANCE,
                    "verified": difference <= MASE_AUDIT_TOLERANCE,
                }
            )
        mase_audits.append(
            {
                "symbol": symbol,
                "reconstructed_denominator": denominator,
                "denominator_source": "mean_absolute_first_difference_of_frozen_development_close_series",
                "development_start": development_dates[0],
                "development_end": development_dates[-1],
                "development_observation_count": len(closes),
                "methods": method_audits,
            }
        )

        selection = select_company_models(company_metrics, symbol=symbol)
        dm = deserialize_archived_dm(company)
        reporting.append(
            {
                "symbol": symbol,
                "metrics": {model.value: metric.as_dict() for model, metric in company_metrics.items()},
                "archived_dm_evidence": dm.as_dict(),
                "descriptive_holdout": build_descriptive_holdout_conclusion(symbol, selection).as_dict(),
                "statistical_significance": build_significance_conclusion(selection, dm).as_dict(),
                "production_deployment": build_production_deployment_conclusion().as_dict(),
                "prospective_validation": prospective_by_symbol[symbol],
            }
        )

        frozen_features = company["model_grids_and_seeds"]["lag_reg"]["features"]
        if not isinstance(frozen_features, dict):
            raise SupplementaryEvidenceError("Frozen LIR feature config is missing")
        contract = regression_feature_contract(_feature_config(frozen_features)).as_dict()
        if feature_contract_payload is None:
            feature_contract_payload = contract
            frozen_feature_config = dict(frozen_features)
        elif contract != feature_contract_payload:
            raise SupplementaryEvidenceError("Frozen LIR candidate contracts differ by company")
        fold_source = company["tuning_and_fold_scores"]["lag_reg"]["fold_scores"]
        if not isinstance(fold_source, list):
            raise SupplementaryEvidenceError("Frozen LIR fold metadata is missing")
        folds = [
            {
                "fold_index": item["fold_index"],
                "alpha": item["alpha"],
                "selected_feature_names": item["feature_names"],
                "pacf_selected_lags": item["pacf_selected_lags"],
                "scaler_mean": item["scaler_mean"],
                "scaler_scale": item["scaler_scale"],
            }
            for item in fold_source
        ]
        dev = company["selected_configurations"]["lag_reg"]["development_fit"]
        lir_companies.append(
            {
                "symbol": symbol,
                "folds": folds,
                "development_fit": {
                    "selected_feature_names": dev["feature_names"],
                    "pacf_selected_lags": dev["pacf_selected_lags"],
                    "scaler_mean": dev["scaler"]["mean"],
                    "scaler_scale": dev["scaler"]["scale"],
                },
            }
        )
    if common_dates is None or feature_contract_payload is None or frozen_feature_config is None:
        raise SupplementaryEvidenceError("Formal archive contains no company evidence")
    comparison = compare_methods_across_companies(metrics_by_company)
    paired = comparison.paired_evidence_as_dict()
    paired.update({"source_formal_run_id": formal_run_id, "source_formal_integrity_aggregate_sha256": aggregate})
    git_source = run.get("git_state") if isinstance(run.get("git_state"), dict) else {}
    formal_source = {
        "schema_id": "forecastph.supplementary-formal-source",
        "schema_version": 1,
        "source_formal_run_id": formal_run_id,
        "source_formal_schema_id": run.get("schema_id"),
        "source_formal_schema_version": run.get("schema_version"),
        "source_formal_integrity_aggregate_sha256": aggregate,
        "source_formal_integrity_manifest_sha256": sha256_file(manifest_path),
        "source_cutoff_date": run.get("cutoff_date"),
        "source_holdout_start": common_dates[0],
        "source_holdout_end": common_dates[-1],
        "source_company_count": len(symbols),
        "source_target_count_per_company": len(common_dates),
        "source_company_order": list(symbols),
        "source_git_commit": git_source.get("commit"),
        "source_git_branch": git_source.get("branch"),
        "source_formal_run_state": archive.state.value,
    }
    if code_provenance is None:
        repository_root = Path(__file__).resolve().parents[3]
        current_git = capture_git_state(repository_root).as_dict()
        environment = capture_environment()
        code_provenance = {
            "schema_id": "forecastph.supplementary-code-provenance",
            "schema_version": 1,
            "git_state": current_git,
            "environment": environment,
            "supplementary_schema_id": SUPPLEMENTARY_EVIDENCE_SCHEMA_ID,
            "supplementary_schema_version": SUPPLEMENTARY_EVIDENCE_SCHEMA_VERSION,
        }
    payloads: dict[str, Mapping[str, object]] = {
        "source/formal_source.json": formal_source,
        "source/code_provenance.json": dict(code_provenance),
        "source/prospective_source.json": prospective_source,
        "historical/formal_holdout_index.json": {
            "schema_id": "forecastph.supplementary-formal-holdout-index",
            "schema_version": 1,
            "company_order": list(symbols),
            "common_target_dates": list(common_dates),
            "companies": actual_rows,
        },
        "historical/paired_mase_evidence.json": paired,
        "historical/change_diagnostics.json": {
            "schema_id": "forecastph.supplementary-change-diagnostics",
            "schema_version": 1,
            "company_order": list(symbols),
            "model_count_per_company": len(ModelId),
            "target_count_per_company_model": len(common_dates),
            "diagnostics": diagnostics,
        },
        "historical/reporting_semantics.json": {
            "schema_id": "forecastph.supplementary-reporting-semantics",
            "schema_version": 1,
            "company_order": list(symbols),
            "companies": reporting,
            "production_deployment": build_production_deployment_conclusion().as_dict(),
        },
        "historical/mase_denominator_audit.json": {
            "schema_id": "forecastph.supplementary-mase-denominator-audit",
            "schema_version": 1,
            "tolerance": MASE_AUDIT_TOLERANCE,
            "company_order": list(symbols),
            "companies": mase_audits,
        },
        "methodology/lir_feature_contract.json": {
            "schema_id": "forecastph.supplementary-lir-methodology-evidence",
            "schema_version": 1,
            "frozen_feature_configuration": frozen_feature_config,
            "candidate_feature_contract": feature_contract_payload,
            "company_order": list(symbols),
            "companies": lir_companies,
            "retraining_performed": False,
        },
        "methodology/arima_diagnostic_status.json": (
            reconstruct_arima_diagnostic_status_payload(
                source_formal_run_id=formal_run_id,
                company_order=symbols,
                evidence_by_symbol=companies,
                frozen_raw_directory=archive.path / "frozen_raw",
            )
        ),
        "prospective/prospective_validation_snapshot.json": prospective_payload,
    }
    validate_supplementary_payloads(payloads, source_archive=archive)
    return SupplementaryEvidencePlan(formal_run_id, aggregate, ledger_sha, payloads)


def _require_company_order(payload: Mapping[str, object], expected: Sequence[str], label: str) -> None:
    if payload.get("company_order") != list(expected):
        raise SupplementaryEvidenceError(f"{label} company order is inconsistent")


def _validate_legacy_arima_status(
    payload: Mapping[str, object],
    expected_symbols: Sequence[str],
) -> None:
    companies = payload.get("companies")
    if not isinstance(companies, list) or [
        item.get("symbol") for item in companies
    ] != list(expected_symbols):
        raise SupplementaryEvidenceError(
            "Legacy ARIMA diagnostic company universe is invalid"
        )
    for item in companies:
        if (
            item.get("enhanced_standardized_residual_diagnostics_available")
            is not False
            or item.get("unavailable_reason") != ARIMA_UNAVAILABLE_REASON
            or item.get("refit_performed") is not False
        ):
            raise SupplementaryEvidenceError(
                "Legacy frozen ARIMA limitation is not reported truthfully"
            )


def _validate_v2_arima_company(item: Mapping[str, object]) -> None:
    try:
        order = tuple(int(value) for value in item["selected_order"])
        trend = str(item["selected_trend"])
        frozen_payload = item["frozen_arima_config"]
        provenance = item["fit_provenance"]
        metadata = item["fit_metadata"]
        diagnostics = item["fitted_model_diagnostics"]
        residuals = diagnostics["fitted_residuals"]
        ljung_box = residuals["ljung_box"]
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplementaryEvidenceError(
            "Schema-v2 ARIMA diagnostic evidence is malformed"
        ) from exc
    if len(order) != 3 or not isinstance(frozen_payload, dict):
        raise SupplementaryEvidenceError("Schema-v2 selected ARIMA order is invalid")
    try:
        frozen_config = reconstruct_frozen_arima_config(frozen_payload)
    except RuntimeError as exc:
        raise SupplementaryEvidenceError(str(exc)) from exc
    specification = ArimaSpecification(order=order, trend=trend)
    if specification not in candidate_specifications(frozen_config):
        raise SupplementaryEvidenceError(
            "Schema-v2 selected ARIMA specification is outside the frozen grid"
        )
    diagnostic_mode = item.get("diagnostic_mode")
    allowed_modes = {
        FROZEN_PARAMETER_DIAGNOSTIC_MODE,
        DIAGNOSTIC_ONLY_REFIT_MODE,
    }
    if (
        item.get("enhanced_standardized_residual_diagnostics_available") is not True
        or diagnostic_mode not in allowed_modes
        or not isinstance(provenance, dict)
        or not isinstance(metadata, dict)
        or not isinstance(diagnostics, dict)
        or not isinstance(residuals, dict)
        or not isinstance(ljung_box, dict)
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 fitted ARIMA diagnostics are unavailable or malformed"
        )
    required_false = (
        "grid_search_performed",
        "candidate_scoring_performed",
        "model_selection_performed",
        "holdout_used_for_fit",
        "holdout_forecasts_regenerated",
        "formal_metrics_recomputed",
        "production_artifact_created",
    )
    if (
        provenance.get("diagnostic_mode") != diagnostic_mode
        or provenance.get("selected_configuration_source")
        != "frozen_formal_evidence"
        or provenance.get("data_source") != "formal_archive_frozen_raw"
        or provenance.get("fit_scope") != "frozen_development_period_only"
        or provenance.get("selected_order") != list(order)
        or provenance.get("selected_trend") != trend
        or any(provenance.get(name) is not False for name in required_false)
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 ARIMA diagnostic-only provenance is invalid"
        )
    expected_names = provenance.get("expected_parameter_names")
    frozen_names = provenance.get("frozen_parameter_names")
    parameters = metadata.get("parameters")
    if (
        not isinstance(expected_names, list)
        or not expected_names
        or len(expected_names) != len(set(expected_names))
        or not all(isinstance(name, str) and name for name in expected_names)
        or not isinstance(frozen_names, list)
        or not isinstance(parameters, dict)
        or provenance.get("parameter_count") != len(expected_names)
        or set(parameters) != set(expected_names)
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 ARIMA parameter-name provenance is invalid"
        )
    if diagnostic_mode == FROZEN_PARAMETER_DIAGNOSTIC_MODE:
        if (
            set(frozen_names) != set(expected_names)
            or len(frozen_names) != len(expected_names)
            or provenance.get("parameter_source")
            != "frozen_formal_development_fit_metadata"
            or provenance.get("optimization_performed") is not False
            or provenance.get("refit_performed") is not False
            or metadata.get("state_space_reconstruction") is not True
            or metadata.get("optimization_performed") is not False
        ):
            raise SupplementaryEvidenceError(
                "Schema-v2 frozen-parameter reconstruction provenance is invalid"
            )
    elif (
        frozen_names
        or provenance.get("parameter_source") is not None
        or provenance.get("optimization_performed") is not True
        or provenance.get("refit_performed") is not True
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 diagnostic-only refit fallback provenance is invalid"
        )
    try:
        development_start = date.fromisoformat(str(provenance["development_start"]))
        development_end = date.fromisoformat(str(provenance["development_end"]))
        first_holdout = date.fromisoformat(
            str(provenance["first_holdout_target_date"])
        )
        observation_count = int(provenance["development_observation_count"])
        nobs = int(metadata["nobs"])
        burn_in = int(residuals["burn_in_removed"])
        residual_count = int(residuals["residual_count"])
        standardized_residuals = residuals["standardized_residuals"]
        model_df = order[0] + order[2]
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplementaryEvidenceError(
            "Schema-v2 ARIMA dates or observation counts are invalid"
        ) from exc
    if (
        development_start > development_end
        or first_holdout <= development_end
        or observation_count < 3
        or nobs != observation_count
        or metadata.get("order") != list(order)
        or metadata.get("trend") != trend
        or (
            frozen_config.require_confirmed_convergence
            and metadata.get("convergence_status")
            != ConvergenceStatus.CONFIRMED_CONVERGED.value
        )
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 ARIMA fit boundary, specification, or convergence is invalid"
        )
    if (
        diagnostics.get("available") is not True
        or diagnostics.get("order") != list(order)
        or diagnostics.get("model_df") != model_df
        or diagnostics.get("unavailable_reason") is not None
        or residuals.get("available") is not True
        or residuals.get("source")
        != "state_space_standardized_forecast_error"
        or residuals.get("model_df") != model_df
        or residuals.get("acf_available") is not True
        or residuals.get("unavailable_reason") is not None
        or not isinstance(standardized_residuals, list)
        or residual_count != len(standardized_residuals)
        or residuals.get("observations") != residual_count
        or residual_count != nobs - burn_in
        or burn_in < 0
        or ljung_box.get("available") is not True
        or ljung_box.get("model_df") != model_df
        or ljung_box.get("observations") != residual_count
        or ljung_box.get("lag") != residuals.get("diagnostic_lag")
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 standardized fitted-residual diagnostics are inconsistent"
        )
    acf_values = residuals.get("acf")
    if (
        not isinstance(acf_values, list)
        or not acf_values
        or [entry.get("lag") for entry in acf_values]
        != list(range(len(acf_values)))
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 fitted residual ACF is incomplete"
        )
    for roots_name, moduli_name, flag_name in (
        ("ar_roots", "ar_root_moduli", "stability_flag"),
        ("ma_roots", "ma_root_moduli", "invertibility_flag"),
    ):
        roots = diagnostics.get(roots_name)
        moduli = diagnostics.get(moduli_name)
        if (
            not isinstance(roots, list)
            or not isinstance(moduli, list)
            or len(roots) != len(moduli)
            or not isinstance(diagnostics.get(flag_name), bool)
        ):
            raise SupplementaryEvidenceError(
                "Schema-v2 ARIMA root diagnostics are incomplete"
            )
    holdout = item.get("original_frozen_holdout_forecast_error_diagnostics")
    if (
        not isinstance(holdout, dict)
        or holdout.get("source") != "complete_aligned_holdout_forecast_errors"
    ):
        raise SupplementaryEvidenceError(
            "Original frozen holdout-error diagnostics are not preserved separately"
        )


def _validate_arima_status_payload(
    payload: Mapping[str, object],
    expected_symbols: Sequence[str],
) -> None:
    schema_id = payload.get("schema_id", ARIMA_DIAGNOSTIC_STATUS_SCHEMA_ID)
    schema_version = payload.get("schema_version", 1)
    if schema_id != ARIMA_DIAGNOSTIC_STATUS_SCHEMA_ID:
        raise SupplementaryEvidenceError("Unknown ARIMA diagnostic-status schema")
    if schema_version == 1:
        _validate_legacy_arima_status(payload, expected_symbols)
        return
    if schema_version != ARIMA_DIAGNOSTIC_STATUS_SCHEMA_VERSION:
        raise SupplementaryEvidenceError(
            "Unsupported ARIMA diagnostic-status schema version"
        )
    companies = payload.get("companies")
    if not isinstance(companies, list) or [
        item.get("symbol") for item in companies
    ] != list(expected_symbols):
        raise SupplementaryEvidenceError(
            "Schema-v2 ARIMA diagnostic company universe is invalid"
        )
    required_false = (
        "grid_search_performed",
        "candidate_scoring_performed",
        "model_selection_performed",
        "holdout_forecasts_regenerated",
        "formal_metrics_recomputed",
        "production_artifact_created",
    )
    allowed_package_modes = {
        FROZEN_PARAMETER_DIAGNOSTIC_MODE,
        DIAGNOSTIC_ONLY_REFIT_MODE,
        "frozen_parameter_reconstruction_with_diagnostic_only_refit_fallback",
    }
    if (
        payload.get("diagnostic_mode") not in allowed_package_modes
        or any(payload.get(name) is not False for name in required_false)
    ):
        raise SupplementaryEvidenceError(
            "Schema-v2 ARIMA package-level diagnostic provenance is invalid"
        )
    for item in companies:
        _validate_v2_arima_company(item)


def validate_supplementary_payloads(
    payloads: Mapping[str, Mapping[str, object]],
    *,
    source_archive: FormalRunArchive | None = None,
) -> None:
    """Fail closed on semantic corruption before publication or after loading."""

    if set(payloads) != set(EVIDENCE_PATHS):
        raise SupplementaryEvidenceError("Supplementary payload file set is incomplete")
    formal = payloads["source/formal_source.json"]
    expected = tuple(str(value) for value in formal.get("source_company_order", ()))
    if not expected or formal.get("source_company_count") != len(expected):
        raise SupplementaryEvidenceError("Formal company universe is invalid")
    index = payloads["historical/formal_holdout_index.json"]
    dates = tuple(str(value) for value in index.get("common_target_dates", ()))
    if not dates or dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
        raise SupplementaryEvidenceError("Formal target dates must be unique and chronological")
    if formal.get("source_target_count_per_company") != len(dates):
        raise SupplementaryEvidenceError("Formal target count is inconsistent")
    for path, payload in payloads.items():
        _reject_non_finite(payload, path)
    for path in (
        "historical/formal_holdout_index.json",
        "historical/change_diagnostics.json",
        "historical/reporting_semantics.json",
        "historical/mase_denominator_audit.json",
        "methodology/lir_feature_contract.json",
        "methodology/arima_diagnostic_status.json",
        "prospective/prospective_validation_snapshot.json",
    ):
        _require_company_order(payloads[path], expected, path)

    rows = index.get("companies")
    if not isinstance(rows, list) or [item.get("symbol") for item in rows] != list(expected):
        raise SupplementaryEvidenceError("Formal holdout company records are incomplete")
    for company in rows:
        company_rows = company.get("rows")
        if not isinstance(company_rows, list):
            raise SupplementaryEvidenceError("Formal holdout rows are malformed")
        row_dates = [str(item.get("target_date")) for item in company_rows]
        if row_dates != list(dates) or len(set(row_dates)) != len(row_dates):
            raise SupplementaryEvidenceError("Company target dates are shifted, reordered, or duplicated")

    paired = payloads["historical/paired_mase_evidence.json"]
    pairs = paired.get("pairs")
    expected_pairs = [[left.value, right.value] for left, right in MODEL_PAIRS]
    if not isinstance(pairs, list) or [[item.get("model_1"), item.get("model_2")] for item in pairs] != expected_pairs:
        raise SupplementaryEvidenceError("Paired MASE evidence must contain all six method pairs")
    for item in pairs:
        n = int(item.get("observation_count", -1))
        if item.get("company_order") != list(expected) or n != len(expected):
            raise SupplementaryEvidenceError("Paired MASE company alignment is invalid")
        if int(item.get("positive_count", -1)) + int(item.get("negative_count", -1)) + int(item.get("zero_count", -1)) != n:
            raise SupplementaryEvidenceError("Paired MASE sign counts are inconsistent")
        friedman_reject = bool(paired.get("friedman", {}).get("reject"))
        if bool(item.get("wilcoxon", {}).get("performed")) != friedman_reject:
            raise SupplementaryEvidenceError("Wilcoxon conditionality disagrees with Friedman")

    change = payloads["historical/change_diagnostics.json"]
    diagnostics = change.get("diagnostics")
    expected_change = {(symbol, model.value) for symbol in expected for model in ModelId}
    if not isinstance(diagnostics, list) or {(item.get("symbol"), item.get("model")) for item in diagnostics} != expected_change:
        raise SupplementaryEvidenceError("Change diagnostics are incomplete")

    report = payloads["historical/reporting_semantics.json"]
    report_companies = report.get("companies")
    if not isinstance(report_companies, list) or [item.get("symbol") for item in report_companies] != list(expected):
        raise SupplementaryEvidenceError("Reporting semantics company universe is invalid")
    for item in report_companies:
        if set(item.get("metrics", {})) != {model.value for model in ModelId}:
            raise SupplementaryEvidenceError("Reporting metrics must contain all four methods")
        families = item.get("archived_dm_evidence", {}).get("holm_families", {})
        for loss in LossType:
            family = families.get(loss.value)
            if not isinstance(family, list) or len(family) != len(MODEL_PAIRS):
                raise SupplementaryEvidenceError("Reporting DM evidence is incomplete")
    deployment = report.get("production_deployment", {})
    if (
        deployment.get("operational_model_families") != ["lag_reg", "arima", "lstm"]
        or deployment.get("single_approved_deployment_model") is not None
        or deployment.get("automatic_promotion") is not False
    ):
        raise SupplementaryEvidenceError("Production deployment semantics changed")

    mase = payloads["historical/mase_denominator_audit.json"]
    mase_companies = mase.get("companies")
    if not isinstance(mase_companies, list) or [item.get("symbol") for item in mase_companies] != list(expected):
        raise SupplementaryEvidenceError("MASE audit company universe is invalid")
    for company in mase_companies:
        denominator = float(company.get("reconstructed_denominator"))
        methods = company.get("methods")
        if denominator <= 0 or not isinstance(methods, list) or [item.get("model") for item in methods] != [model.value for model in ModelId]:
            raise SupplementaryEvidenceError("MASE denominator audit is incomplete")
        for item in methods:
            reconstructed = float(item["stored_mae"]) / denominator
            difference = abs(float(item["stored_mase"]) - reconstructed)
            if (
                not math.isclose(float(item["reconstructed_mase"]), reconstructed, rel_tol=0.0, abs_tol=MASE_AUDIT_TOLERANCE)
                or not math.isclose(float(item["absolute_difference"]), difference, rel_tol=0.0, abs_tol=MASE_AUDIT_TOLERANCE)
                or difference > MASE_AUDIT_TOLERANCE
                or item.get("verified") is not True
            ):
                raise SupplementaryEvidenceError("MAE/MASE denominator audit failed")

    lir = payloads["methodology/lir_feature_contract.json"]
    frozen_config = lir.get("frozen_feature_configuration")
    candidate = lir.get("candidate_feature_contract")
    if not isinstance(frozen_config, dict) or candidate != regression_feature_contract(_feature_config(frozen_config)).as_dict():
        raise SupplementaryEvidenceError("LIR candidate feature contract changed")
    names = candidate["ordered_candidate_feature_names"]
    groups = candidate["groups"]
    ordered_groups = candidate["ordered_feature_groups"]
    flattened = [name for group in ordered_groups for name in groups[group]]
    expected_membership = {
        feature: group
        for group in ordered_groups
        for feature in groups[group]
    }
    membership = candidate.get("group_membership")
    if (
        set(flattened) != set(names)
        or len(flattened) != len(set(flattened))
        or not isinstance(membership, dict)
        or membership != expected_membership
        or "volume_log" not in groups["transformed_volume_level_features"]
    ):
        raise SupplementaryEvidenceError("LIR feature taxonomy is inconsistent")
    if any(name.startswith("target_") or name in {"actual_close", "target_delta"} for name in names):
        raise SupplementaryEvidenceError("LIR contract contains a target predictor")
    for company in lir.get("companies", []):
        for fold in [*company.get("folds", []), company.get("development_fit", {})]:
            selected = fold.get("selected_feature_names")
            if not isinstance(selected, list) or not set(selected) <= set(names):
                raise SupplementaryEvidenceError("Formal LIR selected feature is outside candidate contract")
            if set(fold.get("scaler_mean", {})) != set(selected) or set(fold.get("scaler_scale", {})) != set(selected):
                raise SupplementaryEvidenceError("Formal LIR scaler keys do not match selected features")

    arima = payloads["methodology/arima_diagnostic_status.json"]
    _validate_arima_status_payload(arima, expected)
    prospective = payloads["source/prospective_source.json"]
    if prospective.get("evidence_source") != "forecast_ledger_only":
        raise SupplementaryEvidenceError("Prospective evidence is not ledger-only")

    if source_archive is not None:
        if not source_archive.verify_integrity() or source_archive.state is not FormalRunState.FINALIZED:
            raise SupplementaryEvidenceError("Formal source integrity failed")
        source_manifest = _load_json(source_archive.path / "integrity_manifest.json")
        if formal.get("source_formal_run_id") != source_archive.run_id or formal.get("source_formal_integrity_aggregate_sha256") != source_manifest.get("aggregate_sha256"):
            raise SupplementaryEvidenceError("Formal source linkage is inconsistent")
        for company in rows:
            source = _load_json(source_archive.path / "companies" / str(company["symbol"]) / "evidence.json")
            expected_actual = [
                {"target_date": item["target_date"], "actual_close": item["actual_close"]}
                for item in source["canonical_holdout_records"]
            ]
            if company["rows"] != expected_actual:
                raise SupplementaryEvidenceError("Holdout actual Close disagrees with formal source")
        if arima.get("schema_version") == ARIMA_DIAGNOSTIC_STATUS_SCHEMA_VERSION:
            arima_by_symbol = {
                str(item["symbol"]): item for item in arima["companies"]
            }
            for symbol in expected:
                source = _load_json(
                    source_archive.path
                    / "companies"
                    / symbol
                    / "evidence.json"
                )
                item = arima_by_symbol[symbol]
                frozen_selected = source["selected_configurations"]["arima"]
                frozen_development_fit = frozen_selected.get("development_fit", {})
                frozen_parameters = frozen_development_fit.get("parameters")
                frozen_config = source["model_grids_and_seeds"]["arima"]
                development_dates = source["development_target_dates"]
                holdout_dates = source["holdout_target_dates"]
                if (
                    item["selected_order"] != frozen_selected["order"]
                    or item["selected_trend"] != frozen_selected["trend"]
                    or item["frozen_arima_config"] != frozen_config
                    or item["fit_provenance"]["development_end"]
                    != development_dates[-1]
                    or item["fit_provenance"]["development_observation_count"]
                    != len(development_dates) + 1
                    or item["fit_provenance"]["first_holdout_target_date"]
                    != holdout_dates[0]
                    or (
                        frozen_parameters is not None
                        and (
                            item["diagnostic_mode"]
                            != FROZEN_PARAMETER_DIAGNOSTIC_MODE
                            or item["fit_metadata"]["parameters"]
                            != frozen_parameters
                            or set(item["fit_provenance"]["expected_parameter_names"])
                            != set(frozen_parameters)
                            or set(item["fit_provenance"]["frozen_parameter_names"])
                            != set(frozen_parameters)
                        )
                    )
                    or item[
                        "original_frozen_holdout_forecast_error_diagnostics"
                    ]
                    != source["arima_diagnostics"]["holdout_forecast_errors"]
                ):
                    raise SupplementaryEvidenceError(
                        f"Schema-v2 ARIMA evidence disagrees with frozen source for {symbol}"
                    )


def _reject_non_finite(value: object, path: str) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SupplementaryEvidenceError(f"Non-finite number in {path}")
        return
    if isinstance(value, dict):
        for nested in value.values():
            _reject_non_finite(nested, path)
        return
    if isinstance(value, list):
        for nested in value:
            _reject_non_finite(nested, path)


def verify_source_linkage(
    package: SupplementaryEvidenceArchive,
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    ledger_path: Path | None = None,
) -> VerificationResult:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    try:
        formal = _load_json(package.path / "source/formal_source.json")
        archive = FormalRunArchive(str(formal["source_formal_run_id"]), root=formal_runs_root)
        checks["formal_state_finalized"] = archive.state is FormalRunState.FINALIZED
        checks["formal_integrity"] = archive.verify_integrity()
        manifest_path = archive.path / "integrity_manifest.json"
        manifest = _load_json(manifest_path)
        checks["formal_aggregate"] = manifest.get("aggregate_sha256") == formal.get("source_formal_integrity_aggregate_sha256")
        checks["formal_manifest_hash"] = sha256_file(manifest_path) == formal.get("source_formal_integrity_manifest_sha256")
        if ledger_path is not None:
            prospective = _load_json(package.path / "source/prospective_source.json")
            observed = sha256_file(ledger_path) if ledger_path.is_file() else None
            checks["ledger_hash"] = observed == prospective.get("ledger_sha256")
    except (OSError, KeyError, SupplementaryEvidenceError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    for name, passed in checks.items():
        if not passed:
            errors.append(f"failed check: {name}")
    return VerificationResult(not errors and all(checks.values()), checks, tuple(errors))


def load_and_validate_finalized_payloads(
    package: SupplementaryEvidenceArchive,
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
) -> Mapping[str, Mapping[str, object]]:
    """Load and semantically validate a byte-verified finalized package."""

    integrity = package.verify_integrity()
    if not integrity.valid:
        raise SupplementaryEvidenceError(
            f"Package integrity verification failed: {integrity.errors}"
        )
    payloads = {path: _load_json(package.path / path) for path in EVIDENCE_PATHS}
    formal_id = str(payloads["source/formal_source.json"]["source_formal_run_id"])
    source = FormalRunArchive(formal_id, root=formal_runs_root)
    validate_supplementary_payloads(payloads, source_archive=source)
    return payloads


def finalize_supplementary_plan(
    package_id: str,
    plan: SupplementaryEvidencePlan,
    *,
    root: Path,
) -> SupplementaryEvidenceArchive:
    validate_supplementary_payloads(plan.payloads)
    provenance = plan.payloads["source/code_provenance.json"]
    git_state = provenance.get("git_state")
    if not isinstance(git_state, dict) or git_state.get("dirty") is not False:
        raise SupplementaryEvidenceError("Finalization requires a clean, available Git state")
    archive = SupplementaryEvidenceArchive.create(
        package_id, source_formal_run_id=plan.formal_run_id, root=root
    )
    try:
        for path in EVIDENCE_PATHS:
            archive.write_json(path, plan.payloads[path])
        archive.finalize(
            source_formal_integrity_aggregate_sha256=plan.formal_aggregate_sha256
        )
        verification = archive.verify_integrity()
        if not verification.valid:
            raise SupplementaryEvidenceError(
                f"Finalized package failed immediate integrity verification: {verification.errors}"
            )
        return archive
    except Exception:
        archive.abort_staging()
        raise
