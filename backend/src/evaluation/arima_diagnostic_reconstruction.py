"""Reconstruct selected formal ARIMA fitted evidence without retraining."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import csv
import math
from pathlib import Path

import numpy as np
from statsmodels.tsa.arima.model import ARIMA

from config.model_config import ArimaConfig
from src.evaluation.arima_diagnostics import compute_fitted_arima_diagnostics
from src.models.arima import (
    ArimaSpecification,
    ConvergenceStatus,
    FittedArimaModel,
    candidate_specifications,
    fit_arima,
)


ARIMA_DIAGNOSTIC_STATUS_SCHEMA_ID = (
    "forecastph.supplementary-arima-diagnostic-status"
)
ARIMA_DIAGNOSTIC_STATUS_SCHEMA_VERSION = 2
FROZEN_PARAMETER_DIAGNOSTIC_MODE = (
    "frozen_parameter_state_space_reconstruction"
)
DIAGNOSTIC_ONLY_REFIT_MODE = "diagnostic_only_refit"


class ArimaDiagnosticReconstructionError(RuntimeError):
    """Raised when frozen evidence cannot prove a safe diagnostic result."""


@dataclass(frozen=True, slots=True)
class FrozenDevelopmentSeries:
    dates: tuple[date, ...]
    closes: tuple[float, ...]
    development_target_dates: tuple[date, ...]
    first_holdout_target_date: date

    @property
    def start(self) -> date:
        return self.dates[0]

    @property
    def end(self) -> date:
        return self.dates[-1]


def arima_config_as_dict(config: ArimaConfig) -> dict[str, object]:
    """Return the exact JSON representation retained by formal evidence."""

    return {
        "p_values": list(config.p_values),
        "d_values": list(config.d_values),
        "q_values": list(config.q_values),
        "trend_options_by_d": [
            [differencing, list(trends)]
            for differencing, trends in config.trend_options_by_d
        ],
        "cv_splits": config.cv_splits,
        "retry_max_iterations": list(config.retry_max_iterations),
        "enforce_stationarity": config.enforce_stationarity,
        "enforce_invertibility": config.enforce_invertibility,
        "require_confirmed_convergence": config.require_confirmed_convergence,
    }


def reconstruct_frozen_arima_config(payload: Mapping[str, object]) -> ArimaConfig:
    """Rebuild and exact-round-trip the frozen formal ARIMA configuration."""

    expected_keys = {
        "p_values",
        "d_values",
        "q_values",
        "trend_options_by_d",
        "cv_splits",
        "retry_max_iterations",
        "enforce_stationarity",
        "enforce_invertibility",
        "require_confirmed_convergence",
    }
    if set(payload) != expected_keys:
        raise ArimaDiagnosticReconstructionError(
            "Frozen ARIMA configuration fields are incomplete or unexpected"
        )
    boolean_fields = (
        "enforce_stationarity",
        "enforce_invertibility",
        "require_confirmed_convergence",
    )
    if any(not isinstance(payload[name], bool) for name in boolean_fields):
        raise ArimaDiagnosticReconstructionError(
            "Frozen ARIMA configuration boolean fields must be actual booleans"
        )
    try:
        config = ArimaConfig(
            p_values=tuple(int(value) for value in payload["p_values"]),
            d_values=tuple(int(value) for value in payload["d_values"]),
            q_values=tuple(int(value) for value in payload["q_values"]),
            trend_options_by_d=tuple(
                (int(item[0]), tuple(str(value) for value in item[1]))
                for item in payload["trend_options_by_d"]
            ),
            cv_splits=int(payload["cv_splits"]),
            retry_max_iterations=tuple(
                int(value) for value in payload["retry_max_iterations"]
            ),
            enforce_stationarity=payload["enforce_stationarity"],
            enforce_invertibility=payload["enforce_invertibility"],
            require_confirmed_convergence=payload[
                "require_confirmed_convergence"
            ],
        )
    except (TypeError, ValueError, IndexError) as exc:
        raise ArimaDiagnosticReconstructionError(
            "Frozen ARIMA configuration is malformed"
        ) from exc
    if arima_config_as_dict(config) != dict(payload):
        raise ArimaDiagnosticReconstructionError(
            "Frozen ARIMA configuration cannot be reconstructed exactly"
        )
    return config


def reconstruct_frozen_development_series(
    evidence: Mapping[str, object],
    frozen_raw_path: Path,
) -> FrozenDevelopmentSeries:
    """Prove and return the formal development-fit Close sequence."""

    development_values = evidence.get("development_target_dates")
    holdout_values = evidence.get("holdout_target_dates")
    if not isinstance(development_values, list) or not development_values:
        raise ArimaDiagnosticReconstructionError(
            "Frozen development_target_dates are missing"
        )
    if not isinstance(holdout_values, list) or not holdout_values:
        raise ArimaDiagnosticReconstructionError("Frozen holdout_target_dates are missing")
    try:
        development_dates = tuple(
            date.fromisoformat(str(value)) for value in development_values
        )
        holdout_dates = tuple(date.fromisoformat(str(value)) for value in holdout_values)
    except ValueError as exc:
        raise ArimaDiagnosticReconstructionError(
            "Frozen formal dates are malformed"
        ) from exc
    if (
        development_dates != tuple(sorted(development_dates))
        or len(set(development_dates)) != len(development_dates)
    ):
        raise ArimaDiagnosticReconstructionError(
            "Frozen development dates must be unique and chronological"
        )
    if (
        holdout_dates != tuple(sorted(holdout_dates))
        or len(set(holdout_dates)) != len(holdout_dates)
        or holdout_dates[0] <= development_dates[-1]
    ):
        raise ArimaDiagnosticReconstructionError(
            "Frozen holdout dates must be unique, chronological, and after development"
        )

    try:
        with Path(frozen_raw_path).open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or not {"Date", "Close"} <= set(
                reader.fieldnames
            ):
                raise ArimaDiagnosticReconstructionError(
                    "Frozen raw CSV lacks Date or Close"
                )
            raw_rows = tuple(reader)
        raw_dates = tuple(date.fromisoformat(str(row["Date"])) for row in raw_rows)
        raw_closes = tuple(float(row["Close"]) for row in raw_rows)
    except (OSError, ValueError, TypeError) as exc:
        raise ArimaDiagnosticReconstructionError(
            "Frozen raw Date/Close data are unreadable"
        ) from exc
    if not raw_dates:
        raise ArimaDiagnosticReconstructionError("Frozen raw CSV is empty")
    if raw_dates != tuple(sorted(raw_dates)) or len(set(raw_dates)) != len(raw_dates):
        raise ArimaDiagnosticReconstructionError(
            "Frozen raw dates must be unique and chronological"
        )
    if any(not math.isfinite(value) or value <= 0.0 for value in raw_closes):
        raise ArimaDiagnosticReconstructionError(
            "Frozen raw Close values must be finite and positive"
        )
    try:
        development_end_index = raw_dates.index(development_dates[-1])
    except ValueError as exc:
        raise ArimaDiagnosticReconstructionError(
            "Final development date is absent from frozen raw data"
        ) from exc
    fit_dates = raw_dates[: development_end_index + 1]
    fit_closes = raw_closes[: development_end_index + 1]
    if fit_dates[1:] != development_dates:
        raise ArimaDiagnosticReconstructionError(
            "Frozen development target dates do not map exactly to raw dates"
        )
    if holdout_dates[0] in fit_dates:
        raise ArimaDiagnosticReconstructionError(
            "A holdout target observation was included in development fit data"
        )
    return FrozenDevelopmentSeries(
        dates=fit_dates,
        closes=fit_closes,
        development_target_dates=development_dates,
        first_holdout_target_date=holdout_dates[0],
    )


def selected_frozen_specification(
    evidence: Mapping[str, object],
    config: ArimaConfig,
) -> ArimaSpecification:
    """Read the selected formal specification and prove grid membership."""

    try:
        selected = evidence["selected_configurations"]["arima"]
        order_values = selected["order"]
        specification = ArimaSpecification(
            order=tuple(int(value) for value in order_values),
            trend=str(selected["trend"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ArimaDiagnosticReconstructionError(
            "Frozen selected ARIMA specification is malformed"
        ) from exc
    if len(specification.order) != 3:
        raise ArimaDiagnosticReconstructionError(
            "Frozen selected ARIMA order must contain p, d, and q"
        )
    if specification not in candidate_specifications(config):
        raise ArimaDiagnosticReconstructionError(
            "Frozen selected ARIMA specification is not legal under frozen config"
        )
    return specification


def reconstruct_company_arima_diagnostics(
    symbol: str,
    evidence: Mapping[str, object],
    frozen_raw_path: Path,
    *,
    source_formal_run_id: str,
    fit_function: Callable[..., FittedArimaModel] = fit_arima,
    diagnostics_function: Callable[..., object] = compute_fitted_arima_diagnostics,
    model_factory: Callable[..., object] = ARIMA,
) -> dict[str, object]:
    """Reconstruct the frozen state; optimize only when parameters are absent."""

    try:
        frozen_config_payload = evidence["model_grids_and_seeds"]["arima"]
    except (KeyError, TypeError) as exc:
        raise ArimaDiagnosticReconstructionError(
            f"Frozen ARIMA configuration is missing for {symbol}"
        ) from exc
    if not isinstance(frozen_config_payload, dict):
        raise ArimaDiagnosticReconstructionError(
            f"Frozen ARIMA configuration is malformed for {symbol}"
        )
    config = reconstruct_frozen_arima_config(frozen_config_payload)
    specification = selected_frozen_specification(evidence, config)
    development = reconstruct_frozen_development_series(evidence, frozen_raw_path)
    try:
        frozen_selected = evidence["selected_configurations"]["arima"]
    except (KeyError, TypeError) as exc:
        raise ArimaDiagnosticReconstructionError(
            f"Frozen selected ARIMA metadata is missing for {symbol}"
        ) from exc
    if not isinstance(frozen_selected, dict):
        raise ArimaDiagnosticReconstructionError(
            f"Frozen selected ARIMA metadata is malformed for {symbol}"
        )
    frozen_fit = frozen_selected.get("development_fit", {})
    if not isinstance(frozen_fit, dict):
        raise ArimaDiagnosticReconstructionError(
            f"Frozen ARIMA development-fit metadata is malformed for {symbol}"
        )
    frozen_parameters = frozen_fit.get("parameters")
    if frozen_parameters is not None:
        if not isinstance(frozen_parameters, dict) or not frozen_parameters:
            raise ArimaDiagnosticReconstructionError(
                f"Frozen ARIMA parameters are malformed for {symbol}"
            )
        if (
            frozen_fit.get("order") != list(specification.order)
            or frozen_fit.get("trend") != specification.trend
            or frozen_fit.get("nobs") != len(development.closes)
        ):
            raise ArimaDiagnosticReconstructionError(
                f"Frozen ARIMA development-fit metadata disagrees with the "
                f"selected specification or development boundary for {symbol}"
            )
        model = model_factory(
            development.closes,
            order=specification.order,
            trend=specification.trend,
            enforce_stationarity=config.enforce_stationarity,
            enforce_invertibility=config.enforce_invertibility,
        )
        expected_parameter_names = tuple(str(name) for name in model.param_names)
        frozen_parameter_names = tuple(str(name) for name in frozen_parameters)
        if set(frozen_parameter_names) != set(expected_parameter_names):
            missing = sorted(set(expected_parameter_names) - set(frozen_parameter_names))
            extra = sorted(set(frozen_parameter_names) - set(expected_parameter_names))
            raise ArimaDiagnosticReconstructionError(
                f"Frozen ARIMA parameter names disagree for {symbol}; "
                f"missing={missing} extra={extra}"
            )
        parameter_values: list[float] = []
        for name in expected_parameter_names:
            raw_value = frozen_parameters[name]
            if isinstance(raw_value, bool):
                raise ArimaDiagnosticReconstructionError(
                    f"Frozen ARIMA parameter {name} is boolean for {symbol}"
                )
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise ArimaDiagnosticReconstructionError(
                    f"Frozen ARIMA parameter {name} is not numeric for {symbol}"
                ) from exc
            if not math.isfinite(value):
                raise ArimaDiagnosticReconstructionError(
                    f"Frozen ARIMA parameter {name} is non-finite for {symbol}"
                )
            parameter_values.append(value)
        parameter_vector = np.asarray(parameter_values, dtype=np.float64)
        try:
            result = model.filter(parameter_vector)
        except Exception as exc:
            raise ArimaDiagnosticReconstructionError(
                f"Frozen-parameter state-space reconstruction failed for {symbol}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        observed_parameters = np.asarray(result.params, dtype=np.float64).reshape(-1)
        if (
            observed_parameters.shape != parameter_vector.shape
            or not np.array_equal(observed_parameters, parameter_vector)
        ):
            raise ArimaDiagnosticReconstructionError(
                f"Reconstructed ARIMA parameter values changed for {symbol}"
            )
        diagnostic_mode = FROZEN_PARAMETER_DIAGNOSTIC_MODE
        optimization_performed = False
        refit_performed = False
        parameter_source = "frozen_formal_development_fit_metadata"
        fit_metadata = {
            **specification.as_dict(),
            "nobs": int(result.nobs),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "hqic": float(result.hqic),
            "log_likelihood": float(result.llf),
            "parameters": {
                name: value
                for name, value in zip(
                    expected_parameter_names,
                    parameter_values,
                    strict=True,
                )
            },
            "convergence_status": frozen_fit.get("convergence_status"),
            "fit_attempts": frozen_fit.get("fit_attempts", []),
            "state_space_reconstruction": True,
            "optimization_performed": False,
        }
    else:
        fitted = fit_function(
            development.closes,
            specification,
            config=config,
        )
        if (
            config.require_confirmed_convergence
            and fitted.convergence is not ConvergenceStatus.CONFIRMED_CONVERGED
        ):
            raise ArimaDiagnosticReconstructionError(
                f"Diagnostic-only ARIMA fit did not confirm convergence for {symbol}"
            )
        result = fitted.result
        fit_metadata = fitted.fit_metadata()
        fitted_parameters = fit_metadata.get("parameters", {})
        if not isinstance(fitted_parameters, dict) or not fitted_parameters:
            raise ArimaDiagnosticReconstructionError(
                f"Diagnostic-only ARIMA refit parameters are missing for {symbol}"
            )
        expected_parameter_names = tuple(str(name) for name in fitted_parameters)
        frozen_parameter_names = ()
        diagnostic_mode = DIAGNOSTIC_ONLY_REFIT_MODE
        optimization_performed = True
        refit_performed = True
        parameter_source = None
    if int(fit_metadata.get("nobs", -1)) != len(development.closes):
        raise ArimaDiagnosticReconstructionError(
            f"Diagnostic ARIMA observation count is wrong for {symbol}"
        )
    diagnostics = diagnostics_function(
        result,
        order=specification.order,
    )
    diagnostics_payload = diagnostics.as_dict()
    fitted_residuals = diagnostics_payload.get("fitted_residuals", {})
    if (
        diagnostics_payload.get("available") is not True
        or fitted_residuals.get("available") is not True
        or fitted_residuals.get("acf_available") is not True
        or fitted_residuals.get("ljung_box", {}).get("available") is not True
    ):
        reason = diagnostics_payload.get("unavailable_reason") or fitted_residuals.get(
            "unavailable_reason"
        )
        raise ArimaDiagnosticReconstructionError(
            f"Enhanced fitted ARIMA diagnostics unavailable for {symbol}: {reason}"
        )
    try:
        original_holdout = evidence["arima_diagnostics"][
            "holdout_forecast_errors"
        ]
    except (KeyError, TypeError) as exc:
        raise ArimaDiagnosticReconstructionError(
            f"Original frozen holdout diagnostics are missing for {symbol}"
        ) from exc
    if not isinstance(original_holdout, dict):
        raise ArimaDiagnosticReconstructionError(
            f"Original frozen holdout diagnostics are malformed for {symbol}"
        )

    fit_provenance = {
        "diagnostic_mode": diagnostic_mode,
        "source_formal_run_id": source_formal_run_id,
        "selected_configuration_source": "frozen_formal_evidence",
        "data_source": "formal_archive_frozen_raw",
        "fit_scope": "frozen_development_period_only",
        "development_start": development.start.isoformat(),
        "development_end": development.end.isoformat(),
        "development_observation_count": len(development.closes),
        "first_holdout_target_date": development.first_holdout_target_date.isoformat(),
        "selected_order": list(specification.order),
        "selected_trend": specification.trend,
        "parameter_source": parameter_source,
        "expected_parameter_names": list(expected_parameter_names),
        "frozen_parameter_names": list(frozen_parameter_names),
        "parameter_count": len(expected_parameter_names),
        "optimization_performed": optimization_performed,
        "refit_performed": refit_performed,
        "grid_search_performed": False,
        "candidate_scoring_performed": False,
        "model_selection_performed": False,
        "holdout_used_for_fit": False,
        "holdout_forecasts_regenerated": False,
        "formal_metrics_recomputed": False,
        "production_artifact_created": False,
    }
    return {
        "symbol": symbol,
        "enhanced_standardized_residual_diagnostics_available": True,
        "diagnostic_mode": diagnostic_mode,
        "selected_order": list(specification.order),
        "selected_trend": specification.trend,
        "frozen_arima_config": arima_config_as_dict(config),
        "fit_provenance": fit_provenance,
        "fit_metadata": fit_metadata,
        "fitted_model_diagnostics": diagnostics_payload,
        "original_frozen_holdout_forecast_error_diagnostics": dict(
            original_holdout
        ),
    }


def reconstruct_arima_diagnostic_status_payload(
    *,
    source_formal_run_id: str,
    company_order: Sequence[str],
    evidence_by_symbol: Mapping[str, Mapping[str, object]],
    frozen_raw_directory: Path,
) -> dict[str, object]:
    """Build schema v2 only when every frozen selected fit is available."""

    symbols = tuple(company_order)
    if not symbols or set(evidence_by_symbol) != set(symbols):
        raise ArimaDiagnosticReconstructionError(
            "ARIMA reconstruction company universe is incomplete"
        )
    companies = [
        reconstruct_company_arima_diagnostics(
            symbol,
            evidence_by_symbol[symbol],
            Path(frozen_raw_directory) / f"{symbol}.csv",
            source_formal_run_id=source_formal_run_id,
        )
        for symbol in symbols
    ]
    if any(
        item["enhanced_standardized_residual_diagnostics_available"] is not True
        for item in companies
    ):
        raise ArimaDiagnosticReconstructionError(
            "Every company must have available enhanced ARIMA diagnostics"
        )
    modes = {str(item["diagnostic_mode"]) for item in companies}
    package_mode = (
        FROZEN_PARAMETER_DIAGNOSTIC_MODE
        if modes == {FROZEN_PARAMETER_DIAGNOSTIC_MODE}
        else DIAGNOSTIC_ONLY_REFIT_MODE
        if modes == {DIAGNOSTIC_ONLY_REFIT_MODE}
        else "frozen_parameter_reconstruction_with_diagnostic_only_refit_fallback"
    )
    return {
        "schema_id": ARIMA_DIAGNOSTIC_STATUS_SCHEMA_ID,
        "schema_version": ARIMA_DIAGNOSTIC_STATUS_SCHEMA_VERSION,
        "company_order": list(symbols),
        "diagnostic_mode": package_mode,
        "companies": companies,
        "grid_search_performed": False,
        "candidate_scoring_performed": False,
        "model_selection_performed": False,
        "holdout_forecasts_regenerated": False,
        "formal_metrics_recomputed": False,
        "production_artifact_created": False,
    }
