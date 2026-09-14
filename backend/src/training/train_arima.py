"""Chronological ARIMA tuning, evaluation walk-forward, and production refit."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
import logging
import math
from pathlib import Path
from typing import Final
import warnings

import numpy as np
from statsmodels.tsa.stattools import adfuller

from config.model_config import ArimaConfig, DEFAULT_MODEL_CONFIG
from config.settings import SETTINGS
from src.artifacts.io import atomic_write_json
from src.artifacts.manager import ArtifactManager
from src.data.split import CompanyEvaluationPlan
from src.data.validator import OhlcvRecord, require_chronological_records
from src.evaluation.arima_diagnostics import (
    ArimaDiagnostics,
    SelectedArimaFitDiagnostics,
    compute_fitted_arima_diagnostics,
    compute_holdout_error_diagnostics,
)
from src.models.arima import (
    ArimaError,
    ArimaFitAttempt,
    ArimaSpecification,
    FittedArimaModel,
    candidate_specifications,
    fit_arima,
)
from src.training.cross_validation import expanding_window_folds


LOGGER = logging.getLogger(__name__)
ARIMA_EVALUATION_SCHEMA_ID: Final[str] = "forecastph.arima-evaluation"
ARIMA_EVALUATION_SCHEMA_VERSION: Final[int] = 1


class ArimaTuningError(ArimaError):
    """Raised when no candidate completes every chronological CV fold."""


@dataclass(frozen=True, slots=True)
class AdfDiagnostic:
    """Augmented Dickey-Fuller result or an explicit unavailability reason."""

    available: bool
    statistic: float | None = None
    p_value: float | None = None
    used_lag: int | None = None
    observations: int | None = None
    critical_values: tuple[tuple[str, float], ...] = ()
    information_criterion: float | None = None
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "used_lag": self.used_lag,
            "observations": self.observations,
            "critical_values": dict(self.critical_values),
            "information_criterion": self.information_criterion,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class ArimaFoldScore:
    """One candidate's one-step walk-forward score on one validation block."""

    fold_index: int
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    train_size: int
    validation_size: int
    rmse: float
    fit_attempts: tuple[ArimaFitAttempt, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "fold_index": self.fold_index,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "validation_start": self.validation_start.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "train_size": self.train_size,
            "validation_size": self.validation_size,
            "rmse": self.rmse,
            "convergence_evidence": [
                attempt.as_dict() for attempt in self.fit_attempts
            ],
        }


@dataclass(frozen=True, slots=True)
class ArimaCandidateResult:
    """Complete or explicitly failed CV result for one ARIMA specification."""

    specification: ArimaSpecification
    completed_all_folds: bool
    mean_validation_rmse: float | None
    fold_scores: tuple[ArimaFoldScore, ...]
    failure: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            **self.specification.as_dict(),
            "completed_all_folds": self.completed_all_folds,
            "mean_validation_rmse": self.mean_validation_rmse,
            "fold_scores": [score.as_dict() for score in self.fold_scores],
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class ArimaTuningResult:
    """Configuration selected solely by mean chronological validation RMSE."""

    selected_specification: ArimaSpecification
    selected_mean_validation_rmse: float
    candidates: tuple[ArimaCandidateResult, ...]

    @property
    def selected_candidate(self) -> ArimaCandidateResult:
        return next(
            candidate
            for candidate in self.candidates
            if candidate.specification == self.selected_specification
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "selected_specification": self.selected_specification.as_dict(),
            "selected_mean_validation_rmse": self.selected_mean_validation_rmse,
            "selected_fold_rmse": [
                score.rmse for score in self.selected_candidate.fold_scores
            ],
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class ArimaEvaluationResult:
    """Fresh development fit and state-updated forecasts on common target dates."""

    symbol: str
    tuning: ArimaTuningResult
    target_dates: tuple[date, ...]
    predicted_closes: tuple[float, ...]
    actual_closes: tuple[float, ...]
    adf_diagnostic: AdfDiagnostic
    development_fit_metadata: dict[str, object]
    diagnostics: ArimaDiagnostics
    configuration: ArimaConfig

    def as_metadata_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "target": "next_session_close",
            "forecast_horizon_sessions": 1,
            "configuration": asdict(self.configuration),
            "adf_diagnostic": self.adf_diagnostic.as_dict(),
            "tuning": self.tuning.as_dict(),
            "development_fit": self.development_fit_metadata,
            "diagnostics": self.diagnostics.as_dict(),
            "evaluation_target_dates": [value.isoformat() for value in self.target_dates],
        }


@dataclass(frozen=True, slots=True)
class ArimaProductionFit:
    """A separately fitted all-data production model and its metadata."""

    model: FittedArimaModel
    fit_metadata: dict[str, object]
    adf_diagnostic: AdfDiagnostic
    fitted_diagnostics: SelectedArimaFitDiagnostics


def _rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    actual_values = np.asarray(actual, dtype=np.float64)
    predicted_values = np.asarray(predicted, dtype=np.float64)
    return float(math.sqrt(float(np.mean(np.square(actual_values - predicted_values)))))


def compute_adf_diagnostic(close_values: Sequence[float]) -> AdfDiagnostic:
    """Compute ADF on the supplied chronological fit series as a diagnostic only."""

    values = np.asarray(close_values, dtype=np.float64).reshape(-1)
    if values.size < 4 or not np.isfinite(values).all():
        return AdfDiagnostic(
            available=False,
            unavailable_reason="ADF requires at least four finite Close values",
        )
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="adfuller currently returns a plain tuple.*",
                category=FutureWarning,
            )
            statistic, p_value, used_lag, observations, critical, icbest = adfuller(
                values,
                autolag="AIC",
            )
    except (ValueError, np.linalg.LinAlgError) as exc:
        return AdfDiagnostic(
            available=False,
            unavailable_reason=f"{type(exc).__name__}: {exc}",
        )
    return AdfDiagnostic(
        available=True,
        statistic=float(statistic),
        p_value=float(p_value),
        used_lag=int(used_lag),
        observations=int(observations),
        critical_values=tuple(
            (str(name), float(value)) for name, value in critical.items()
        ),
        information_criterion=float(icbest),
    )


def score_arima_candidate(
    close_values: Sequence[float],
    close_dates: Sequence[date],
    specification: ArimaSpecification,
    *,
    config: ArimaConfig,
) -> ArimaCandidateResult:
    """Score a candidate; any failed fold makes the whole candidate ineligible."""

    values = tuple(float(value) for value in close_values)
    dates = tuple(close_dates)
    if len(values) != len(dates):
        raise ValueError("close_values and close_dates must have equal length")
    folds = expanding_window_folds(len(values), n_splits=config.cv_splits)
    fold_scores: list[ArimaFoldScore] = []
    try:
        for fold in folds:
            train_values = tuple(values[index] for index in fold.train_indices)
            validation_values = tuple(
                values[index] for index in fold.validation_indices
            )
            fitted = fit_arima(train_values, specification, config=config)
            predicted: list[float] = []
            current = fitted
            for actual in validation_values:
                predicted.append(current.forecast_one())
                current = current.append_actual(actual)
            fold_scores.append(
                ArimaFoldScore(
                    fold_index=fold.fold_index,
                    train_start=dates[fold.train_indices[0]],
                    train_end=dates[fold.train_indices[-1]],
                    validation_start=dates[fold.validation_indices[0]],
                    validation_end=dates[fold.validation_indices[-1]],
                    train_size=len(train_values),
                    validation_size=len(validation_values),
                    rmse=_rmse(validation_values, predicted),
                    fit_attempts=fitted.attempts,
                )
            )
    except Exception as exc:
        return ArimaCandidateResult(
            specification=specification,
            completed_all_folds=False,
            mean_validation_rmse=None,
            fold_scores=tuple(fold_scores),
            failure=f"fold {len(fold_scores)}: {type(exc).__name__}: {exc}",
        )
    if len(fold_scores) != len(folds):
        raise RuntimeError("ARIMA candidate was marked complete without every CV fold")
    return ArimaCandidateResult(
        specification=specification,
        completed_all_folds=True,
        mean_validation_rmse=float(np.mean([score.rmse for score in fold_scores])),
        fold_scores=tuple(fold_scores),
    )


def tune_arima(
    close_values: Sequence[float],
    close_dates: Sequence[date],
    *,
    config: ArimaConfig = DEFAULT_MODEL_CONFIG.arima,
) -> ArimaTuningResult:
    """Search all configured candidates using expanding-window one-step CV."""

    specifications = candidate_specifications(config)
    LOGGER.info(
        "Starting ARIMA chronological tuning observations=%d folds=%d candidates=%d",
        len(close_values),
        config.cv_splits,
        len(specifications),
    )
    candidates = tuple(
        score_arima_candidate(
            close_values,
            close_dates,
            specification,
            config=config,
        )
        for specification in specifications
    )
    eligible = tuple(
        candidate
        for candidate in candidates
        if candidate.completed_all_folds
        and candidate.mean_validation_rmse is not None
        and math.isfinite(candidate.mean_validation_rmse)
    )
    if not eligible:
        failures = "; ".join(
            f"ARIMA{candidate.specification.order}/{candidate.specification.trend}: "
            f"{candidate.failure}"
            for candidate in candidates
        )
        raise ArimaTuningError(
            f"No ARIMA candidate completed all {config.cv_splits} folds. {failures}"
        )
    winner = min(
        eligible,
        key=lambda candidate: (
            candidate.mean_validation_rmse,
            candidate.specification.order,
            candidate.specification.trend,
        ),
    )
    LOGGER.info(
        "Completed ARIMA tuning order=%s trend=%s mean_rmse=%.8f eligible=%d",
        winner.specification.order,
        winner.specification.trend,
        winner.mean_validation_rmse,
        len(eligible),
    )
    return ArimaTuningResult(
        selected_specification=winner.specification,
        selected_mean_validation_rmse=float(winner.mean_validation_rmse),
        candidates=candidates,
    )


def _development_records(
    records: Sequence[OhlcvRecord],
    plan: CompanyEvaluationPlan,
) -> tuple[OhlcvRecord, ...]:
    first_evaluation_origin = plan.evaluation_pairs[0].origin_date
    development = tuple(
        record for record in records if record.trading_date <= first_evaluation_origin
    )
    if not development or development[-1].trading_date != first_evaluation_origin:
        raise ValueError("Evaluation origin date is missing from chronological OHLCV records")
    return development


def train_arima_for_evaluation(
    records: Sequence[OhlcvRecord],
    plan: CompanyEvaluationPlan,
    *,
    config: ArimaConfig = DEFAULT_MODEL_CONFIG.arima,
) -> ArimaEvaluationResult:
    """Tune on development, fit once, then append revealed evaluation actuals."""

    require_chronological_records(records)
    development = _development_records(records, plan)
    development_closes = tuple(record.close for record in development)
    development_dates = tuple(record.trading_date for record in development)
    tuning = tune_arima(development_closes, development_dates, config=config)
    fitted = fit_arima(
        development_closes,
        tuning.selected_specification,
        config=config,
    )
    development_fit_metadata = fitted.fit_metadata()
    fitted_diagnostics = compute_fitted_arima_diagnostics(
        getattr(fitted, "result", None),
        order=tuning.selected_specification.order,
    )
    predicted: list[float] = []
    actual: list[float] = []
    target_dates: list[date] = []
    current = fitted
    for pair in plan.evaluation_pairs:
        predicted.append(current.forecast_one())
        actual.append(pair.actual_close)
        target_dates.append(pair.target_date)
        current = current.append_actual(pair.actual_close)
    result_dates = tuple(target_dates)
    if result_dates != plan.evaluation_target_dates:
        raise RuntimeError("ARIMA evaluation targets diverged from the common company plan")
    LOGGER.info(
        "Completed ARIMA evaluation symbol=%s development=%d evaluation=%d",
        plan.symbol,
        len(development),
        len(target_dates),
    )
    return ArimaEvaluationResult(
        symbol=plan.symbol,
        tuning=tuning,
        target_dates=result_dates,
        predicted_closes=tuple(predicted),
        actual_closes=tuple(actual),
        adf_diagnostic=compute_adf_diagnostic(development_closes),
        development_fit_metadata=development_fit_metadata,
        diagnostics=ArimaDiagnostics(
            selected_fitted_model=fitted_diagnostics,
            holdout_forecast_errors=compute_holdout_error_diagnostics(
                tuple(
                    prediction - observed
                    for prediction, observed in zip(predicted, actual, strict=True)
                )
            ),
        ),
        configuration=config,
    )


def refit_arima_for_production(
    records: Sequence[OhlcvRecord],
    *,
    selected_specification: ArimaSpecification,
    config: ArimaConfig = DEFAULT_MODEL_CONFIG.arima,
) -> ArimaProductionFit:
    """Fit the selected configuration once using all available Close values."""

    require_chronological_records(records)
    close_values = tuple(record.close for record in records)
    LOGGER.info(
        "Refitting ARIMA production model observations=%d order=%s trend=%s",
        len(close_values),
        selected_specification.order,
        selected_specification.trend,
    )
    fitted = fit_arima(close_values, selected_specification, config=config)
    fitted_diagnostics = compute_fitted_arima_diagnostics(
        fitted.result,
        order=selected_specification.order,
    )
    return ArimaProductionFit(
        model=fitted,
        fit_metadata={
            **fitted.fit_metadata(),
            "diagnostics": fitted_diagnostics.as_dict(),
        },
        adf_diagnostic=compute_adf_diagnostic(close_values),
        fitted_diagnostics=fitted_diagnostics,
    )


def persist_arima_metadata(
    result: ArimaEvaluationResult,
    *,
    artifact_name: str,
    artifacts_root: Path | None = None,
) -> Path:
    """Persist ARIMA evaluation metadata under backend/artifacts/evaluations."""

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    if not artifact_name or any(character not in allowed for character in artifact_name):
        raise ValueError(
            "artifact_name may contain only letters, numbers, hyphens, and underscores"
        )
    root = SETTINGS.artifacts_dir if artifacts_root is None else Path(artifacts_root)
    output_dir = ArtifactManager(root).ensure_directories().evaluations / "arima"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{artifact_name}.json"
    payload = {
        "schema_id": ARIMA_EVALUATION_SCHEMA_ID,
        "schema_version": ARIMA_EVALUATION_SCHEMA_VERSION,
        **result.as_metadata_dict(),
    }
    atomic_write_json(destination, payload)
    LOGGER.info("Persisted ARIMA metadata path=%s", destination)
    return destination
