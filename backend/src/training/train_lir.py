"""Chronological tuning, evaluation fitting, and production refitting for LIR."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
import logging
import math
from pathlib import Path
from typing import Final
import warnings

import numpy as np

from config.model_config import DEFAULT_MODEL_CONFIG, LagRegressionConfig
from config.settings import SETTINGS
from src.artifacts.io import atomic_write_json
from src.artifacts.manager import ArtifactManager
from src.data.split import CompanyEvaluationPlan
from src.features.regression_features import (
    RegressionDataset,
    RegressionSample,
    feature_names_for_pacf_lags,
)
from src.models.lag_regression import LagRegressionFitMetadata, LagRegressionModel
from src.training.cross_validation import expanding_window_folds, select_pacf_lags


LOGGER = logging.getLogger(__name__)
LIR_EVALUATION_SCHEMA_ID: Final[str] = "forecastph.lir-evaluation"
LIR_EVALUATION_SCHEMA_VERSION: Final[int] = 1


class AlphaGridBoundaryWarning(UserWarning):
    """Warn that the best LASSO alpha lies at an explored grid boundary."""


@dataclass(frozen=True, slots=True)
class AlphaGridPosition:
    """Structured location of the selected alpha within the configured grid."""

    classification: str
    lower: bool
    upper: bool
    interior: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "classification": self.classification,
            "lower": self.lower,
            "upper": self.upper,
            "interior": self.interior,
        }


def classify_alpha_grid_position(
    chosen_alpha: float,
    alpha_grid: Sequence[float],
) -> AlphaGridPosition:
    """Classify a selected grid value without hiding a singleton upper boundary."""

    grid = tuple(alpha_grid)
    if not grid or chosen_alpha not in grid:
        raise ValueError("chosen_alpha must be present in a non-empty alpha_grid")
    lower = chosen_alpha == grid[0]
    upper = chosen_alpha == grid[-1]
    interior = not lower and not upper
    if lower and upper:
        classification = "lower_and_upper"
    elif lower:
        classification = "lower"
    elif upper:
        classification = "upper"
    else:
        classification = "interior"
    return AlphaGridPosition(
        classification=classification,
        lower=lower,
        upper=upper,
        interior=interior,
    )


@dataclass(frozen=True, slots=True)
class LIRFoldScore:
    """Reproducible result for one alpha on one chronological fold."""

    alpha: float
    fold_index: int
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    train_size: int
    validation_size: int
    rmse: float
    pacf_selected_lags: tuple[int, ...]
    feature_names: tuple[str, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "alpha": self.alpha,
            "fold_index": self.fold_index,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "validation_start": self.validation_start.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "train_size": self.train_size,
            "validation_size": self.validation_size,
            "rmse": self.rmse,
            "pacf_selected_lags": list(self.pacf_selected_lags),
            "feature_names": list(self.feature_names),
            "scaler_mean": dict(zip(self.feature_names, self.scaler_mean)),
            "scaler_scale": dict(zip(self.feature_names, self.scaler_scale)),
        }


@dataclass(frozen=True, slots=True)
class LIRTuningResult:
    """Alpha chosen by mean chronological validation RMSE."""

    chosen_alpha: float
    mean_validation_rmse: tuple[tuple[float, float], ...]
    fold_scores: tuple[LIRFoldScore, ...]
    alpha_grid_position: AlphaGridPosition

    @property
    def alpha_at_grid_boundary(self) -> bool:
        """Retain the existing aggregate boundary signal for compatibility."""

        return self.alpha_grid_position.lower or self.alpha_grid_position.upper

    def as_dict(self) -> dict[str, object]:
        return {
            "chosen_alpha": self.chosen_alpha,
            "mean_validation_rmse": {
                str(alpha): score for alpha, score in self.mean_validation_rmse
            },
            "alpha_at_grid_boundary": self.alpha_at_grid_boundary,
            "alpha_grid_position": self.alpha_grid_position.as_dict(),
            "fold_scores": [score.as_dict() for score in self.fold_scores],
        }


@dataclass(frozen=True, slots=True)
class LIRFittedModel:
    """A fitted estimator and its fold-appropriate PACF/parameter metadata."""

    model: LagRegressionModel
    pacf_selected_lags: tuple[int, ...]
    fit_metadata: LagRegressionFitMetadata

    def as_dict(self) -> dict[str, object]:
        return {
            "pacf_selected_lags": list(self.pacf_selected_lags),
            **self.fit_metadata.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class LIREvaluationResult:
    """Fresh development fit and forecasts on the untouched evaluation dates."""

    symbol: str
    tuning: LIRTuningResult
    fitted: LIRFittedModel
    target_dates: tuple[date, ...]
    predicted_deltas: tuple[float, ...]
    predicted_closes: tuple[float, ...]
    actual_deltas: tuple[float, ...]
    actual_closes: tuple[float, ...]
    configuration: LagRegressionConfig

    def as_metadata_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "target": "next_day_close_delta",
            "configuration": asdict(self.configuration),
            "tuning": self.tuning.as_dict(),
            "development_fit": self.fitted.as_dict(),
            "evaluation_target_dates": [value.isoformat() for value in self.target_dates],
        }


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(math.sqrt(float(np.mean(np.square(actual - predicted)))))


def _new_model(alpha: float, config: LagRegressionConfig) -> LagRegressionModel:
    return LagRegressionModel(
        alpha=alpha,
        max_iterations=config.max_iterations,
        tolerance=config.tolerance,
        coefficient_zero_tolerance=config.coefficient_zero_tolerance,
    )


def tune_lir_alpha(
    dataset: RegressionDataset,
    development_samples: Sequence[RegressionSample],
    *,
    config: LagRegressionConfig = DEFAULT_MODEL_CONFIG.lag_regression,
) -> LIRTuningResult:
    """Tune LASSO alpha with expanding folds and fold-local PACF/scaling."""

    samples = tuple(development_samples)
    folds = expanding_window_folds(len(samples), n_splits=config.cv_splits)
    scores: list[LIRFoldScore] = []
    scores_by_alpha: dict[float, list[float]] = {alpha: [] for alpha in config.alpha_grid}

    LOGGER.info(
        "Starting LIR chronological tuning samples=%d folds=%d alphas=%d",
        len(samples),
        len(folds),
        len(config.alpha_grid),
    )
    for fold in folds:
        training = tuple(samples[index] for index in fold.train_indices)
        validation = tuple(samples[index] for index in fold.validation_indices)
        training_returns = dataset.returns_through(training[-1].target_date)
        pacf_lags = select_pacf_lags(
            training_returns,
            max_lag=config.pacf_max_lag,
            significance_z=config.pacf_significance_z,
        )
        feature_names = feature_names_for_pacf_lags(dataset.feature_names, pacf_lags)
        train_matrix = dataset.matrix(training, feature_names=feature_names)
        validation_matrix = dataset.matrix(validation, feature_names=feature_names)
        train_targets = dataset.targets(training)
        validation_targets = dataset.targets(validation)

        for alpha in config.alpha_grid:
            model = _new_model(alpha, config).fit(
                train_matrix, train_targets, feature_names
            )
            predicted = model.predict_delta(validation_matrix)
            score = _rmse(validation_targets, predicted)
            metadata = model.metadata
            scores_by_alpha[alpha].append(score)
            scores.append(
                LIRFoldScore(
                    alpha=alpha,
                    fold_index=fold.fold_index,
                    train_start=training[0].target_date,
                    train_end=training[-1].target_date,
                    validation_start=validation[0].target_date,
                    validation_end=validation[-1].target_date,
                    train_size=len(training),
                    validation_size=len(validation),
                    rmse=score,
                    pacf_selected_lags=pacf_lags,
                    feature_names=feature_names,
                    scaler_mean=metadata.scaler_mean,
                    scaler_scale=metadata.scaler_scale,
                )
            )

    means = tuple(
        (alpha, float(np.mean(scores_by_alpha[alpha]))) for alpha in config.alpha_grid
    )
    chosen_alpha = min(means, key=lambda item: (item[1], item[0]))[0]
    grid_position = classify_alpha_grid_position(chosen_alpha, config.alpha_grid)
    if grid_position.lower or grid_position.upper:
        boundary_label = grid_position.classification.replace("_and_", " and ")
        warnings.warn(
            f"Winning LASSO alpha {chosen_alpha} is at the configured "
            f"{boundary_label} grid boundary",
            AlphaGridBoundaryWarning,
            stacklevel=2,
        )
    LOGGER.info(
        "Completed LIR tuning chosen_alpha=%s grid_position=%s mean_rmse=%.8f",
        chosen_alpha,
        grid_position.classification,
        dict(means)[chosen_alpha],
    )
    return LIRTuningResult(
        chosen_alpha=chosen_alpha,
        mean_validation_rmse=means,
        fold_scores=tuple(scores),
        alpha_grid_position=grid_position,
    )


def _fit_with_local_pacf(
    dataset: RegressionDataset,
    samples: Sequence[RegressionSample],
    *,
    alpha: float,
    config: LagRegressionConfig,
) -> LIRFittedModel:
    chosen_samples = tuple(samples)
    training_returns = dataset.returns_through(chosen_samples[-1].target_date)
    pacf_lags = select_pacf_lags(
        training_returns,
        max_lag=config.pacf_max_lag,
        significance_z=config.pacf_significance_z,
    )
    feature_names = feature_names_for_pacf_lags(dataset.feature_names, pacf_lags)
    model = _new_model(alpha, config).fit(
        dataset.matrix(chosen_samples, feature_names=feature_names),
        dataset.targets(chosen_samples),
        feature_names,
    )
    return LIRFittedModel(
        model=model,
        pacf_selected_lags=pacf_lags,
        fit_metadata=model.metadata,
    )


def train_lir_for_evaluation(
    dataset: RegressionDataset,
    plan: CompanyEvaluationPlan,
    *,
    config: LagRegressionConfig = DEFAULT_MODEL_CONFIG.lag_regression,
) -> LIREvaluationResult:
    """Tune on development only, refit fresh, then forecast common evaluation dates."""

    development_dates = set(plan.development_target_dates)
    development_samples = tuple(
        sample for sample in dataset.samples if sample.target_date in development_dates
    )
    if not development_samples:
        raise ValueError("No post-warm-up development samples are available")
    evaluation_samples = dataset.samples_for_target_dates(plan.evaluation_target_dates)
    tuning = tune_lir_alpha(dataset, development_samples, config=config)
    fitted = _fit_with_local_pacf(
        dataset,
        development_samples,
        alpha=tuning.chosen_alpha,
        config=config,
    )
    evaluation_matrix = dataset.matrix(
        evaluation_samples, feature_names=fitted.fit_metadata.feature_names
    )
    predicted_deltas_array = fitted.model.predict_delta(evaluation_matrix)
    predicted_closes_array = fitted.model.predict_close(
        evaluation_matrix, dataset.origin_closes(evaluation_samples)
    )
    target_dates = tuple(sample.target_date for sample in evaluation_samples)
    if target_dates != plan.evaluation_target_dates:
        raise RuntimeError("LIR evaluation targets diverged from the common company plan")
    LOGGER.info(
        "Completed LIR evaluation symbol=%s development=%d evaluation=%d",
        plan.symbol,
        len(development_samples),
        len(evaluation_samples),
    )
    return LIREvaluationResult(
        symbol=plan.symbol,
        tuning=tuning,
        fitted=fitted,
        target_dates=target_dates,
        predicted_deltas=tuple(float(value) for value in predicted_deltas_array),
        predicted_closes=tuple(float(value) for value in predicted_closes_array),
        actual_deltas=tuple(sample.target_delta for sample in evaluation_samples),
        actual_closes=tuple(sample.actual_close for sample in evaluation_samples),
        configuration=config,
    )


def refit_lir_for_production(
    dataset: RegressionDataset,
    *,
    chosen_alpha: float,
    config: LagRegressionConfig = DEFAULT_MODEL_CONFIG.lag_regression,
) -> LIRFittedModel:
    """Fit a separate production estimator on all currently labeled samples."""

    LOGGER.info(
        "Refitting LIR production model samples=%d alpha=%s",
        len(dataset.samples),
        chosen_alpha,
    )
    return _fit_with_local_pacf(
        dataset,
        dataset.samples,
        alpha=chosen_alpha,
        config=config,
    )


def persist_lir_metadata(
    result: LIREvaluationResult,
    *,
    artifact_name: str,
    artifacts_root: Path | None = None,
) -> Path:
    """Persist LIR evaluation metadata under backend/artifacts/evaluations."""

    if not artifact_name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in artifact_name):
        raise ValueError("artifact_name may contain only letters, numbers, hyphens, and underscores")
    root = SETTINGS.artifacts_dir if artifacts_root is None else Path(artifacts_root)
    output_dir = ArtifactManager(root).ensure_directories().evaluations / "lir"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{artifact_name}.json"
    payload = {
        "schema_id": LIR_EVALUATION_SCHEMA_ID,
        "schema_version": LIR_EVALUATION_SCHEMA_VERSION,
        **result.as_metadata_dict(),
    }
    atomic_write_json(destination, payload)
    LOGGER.info("Persisted LIR metadata path=%s", destination)
    return destination
