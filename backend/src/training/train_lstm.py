"""Chronological tuning and two-stage refitting for the univariate LSTM."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import logging
import math
from pathlib import Path
import random
from typing import Final

import numpy as np
import torch
from torch import nn

from config.model_config import DEFAULT_MODEL_CONFIG, LstmConfig
from config.settings import SETTINGS
from src.artifacts.io import (
    atomic_write_json,
    atomic_write_json_gzip,
    validated_json_text,
)
from src.artifacts.manager import ArtifactManager
from src.data.split import CompanyEvaluationPlan
from src.data.validator import OhlcvRecord, require_chronological_records
from src.features.targets import NextDayForecastPair, build_next_day_pairs
from src.models.lstm import (
    DeltaScaler,
    DeltaSequenceSample,
    FittedLstmModel,
    LstmSpecification,
    UnivariateDeltaLSTM,
    build_delta_sequence_samples,
    fit_delta_scaler,
    sequence_matrix,
    target_array,
    validate_model_state,
)
from src.training.cross_validation import ExpandingWindowFold, expanding_window_folds


LOGGER = logging.getLogger(__name__)
LSTM_EVALUATION_SCHEMA_ID: Final[str] = "forecastph.lstm-evaluation"
LSTM_EVALUATION_SCHEMA_VERSION: Final[int] = 1
LSTM_TRAINING_HISTORY_SCHEMA_ID: Final[str] = "forecastph.lstm-training-history"
LSTM_TRAINING_HISTORY_SCHEMA_VERSION: Final[int] = 1
TUNING_EARLY_STOPPING_STAGE: Final[str] = "tuning_early_stopping"
FINAL_EPOCH_SELECTION_STAGE: Final[str] = "final_development_epoch_selection"
FIXED_EPOCH_REFIT_STAGE: Final[str] = "fixed_epoch_refit"
_TRAINING_STAGES: Final[frozenset[str]] = frozenset(
    {
        TUNING_EARLY_STOPPING_STAGE,
        FINAL_EPOCH_SELECTION_STAGE,
        FIXED_EPOCH_REFIT_STAGE,
    }
)


class LstmTrainingError(RuntimeError):
    """Raised when chronological LSTM tuning or fitting cannot be completed."""


def lstm_configuration_id(specification: LstmSpecification) -> str:
    """Return a stable, readable ID derived only from one LSTM specification."""

    canonical = json.dumps(
        specification.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    learning_rate = format(specification.learning_rate, ".17g")
    return (
        f"lstm-v1-lb{specification.lookback}-h{specification.hidden_size}"
        f"-lr{learning_rate}-bs{specification.batch_size}-{digest}"
    )


@dataclass(frozen=True, slots=True)
class LstmEpochRecord:
    """Loss values already produced during one chronological training epoch."""

    epoch: int
    training_loss: float
    stopping_loss: float | None
    best_stopping_loss_so_far: float | None
    best_epoch_so_far: int | None
    learning_rate: float

    def __post_init__(self) -> None:
        numeric_values = (self.training_loss, self.learning_rate)
        optional_values = (self.stopping_loss, self.best_stopping_loss_so_far)
        if self.epoch < 1 or not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("LSTM epoch records require positive epochs and finite values")
        if self.learning_rate <= 0:
            raise ValueError("LSTM epoch learning_rate must be positive")
        if any(value is not None and not math.isfinite(value) for value in optional_values):
            raise ValueError("LSTM stopping losses must be finite when present")
        stopping_fields = (
            self.stopping_loss,
            self.best_stopping_loss_so_far,
            self.best_epoch_so_far,
        )
        if any(value is None for value in stopping_fields) and not all(
            value is None for value in stopping_fields
        ):
            raise ValueError("LSTM stopping-history fields must be present or null together")
        if self.best_epoch_so_far is not None and not (
            1 <= self.best_epoch_so_far <= self.epoch
        ):
            raise ValueError("LSTM running best epoch must refer to an observed epoch")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LstmTrainingHistory:
    """Immutable audit trail for one LSTM early-stop or fixed-epoch operation."""

    configuration_id: str
    training_stage: str
    fold_index: int | None
    seed: int
    epochs: tuple[LstmEpochRecord, ...]
    best_epoch: int | None
    epochs_trained: int
    early_stopped: bool
    core_target_dates: tuple[date, ...]
    stopping_target_dates: tuple[date, ...]

    def __post_init__(self) -> None:
        if not self.configuration_id or self.training_stage not in _TRAINING_STAGES:
            raise ValueError("LSTM training history has an invalid identity or stage")
        if self.seed < 0 or self.epochs_trained < 1:
            raise ValueError("LSTM history seed and epoch count are invalid")
        if len(self.epochs) != self.epochs_trained:
            raise ValueError("LSTM history epoch count does not match its records")
        if tuple(record.epoch for record in self.epochs) != tuple(
            range(1, self.epochs_trained + 1)
        ):
            raise ValueError("LSTM history epochs must be consecutive from one")
        if tuple(sorted(self.core_target_dates)) != self.core_target_dates:
            raise ValueError("LSTM core target dates must be chronological")
        if tuple(sorted(self.stopping_target_dates)) != self.stopping_target_dates:
            raise ValueError("LSTM stopping target dates must be chronological")
        if set(self.core_target_dates) & set(self.stopping_target_dates):
            raise ValueError("LSTM core and stopping target dates must not overlap")
        if self.training_stage == FIXED_EPOCH_REFIT_STAGE:
            if self.best_epoch is not None or self.stopping_target_dates or self.early_stopped:
                raise ValueError("Fixed-epoch history cannot claim early-stopping evidence")
            if any(record.stopping_loss is not None for record in self.epochs):
                raise ValueError("Fixed-epoch history must use null stopping fields")
        else:
            if self.best_epoch is None or not self.stopping_target_dates:
                raise ValueError("Early-stopping history requires a selected best epoch")
            if self.best_epoch != self.epochs[-1].best_epoch_so_far:
                raise ValueError("LSTM history best epoch is inconsistent")
            if any(record.stopping_loss is None for record in self.epochs):
                raise ValueError("Early-stopping history requires stopping loss per epoch")
            running_best = tuple(
                record.best_stopping_loss_so_far for record in self.epochs
            )
            if any(
                current > previous
                for previous, current in zip(running_best, running_best[1:])
            ):
                raise ValueError("LSTM running best stopping loss cannot increase")
            selected_record = self.epochs[self.best_epoch - 1]
            if selected_record.stopping_loss != running_best[-1]:
                raise ValueError("LSTM selected epoch does not match its best stopping loss")

    @property
    def identity(self) -> tuple[str, str, int | None, int]:
        return (
            self.configuration_id,
            self.training_stage,
            self.fold_index,
            self.seed,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "configuration_id": self.configuration_id,
            "training_stage": self.training_stage,
            "fold_index": self.fold_index,
            "seed": self.seed,
            "epochs": [record.as_dict() for record in self.epochs],
            "best_epoch": self.best_epoch,
            "epochs_trained": self.epochs_trained,
            "early_stopped": self.early_stopped,
            "core_target_dates": [value.isoformat() for value in self.core_target_dates],
            "stopping_target_dates": [
                value.isoformat() for value in self.stopping_target_dates
            ],
        }


@dataclass(frozen=True, slots=True)
class EpochSelection:
    """Stage-A epoch count selected only by an inner chronological stopping tail."""

    selected_epoch_count: int
    best_stopping_rmse: float
    core_target_dates: tuple[date, ...]
    stopping_target_dates: tuple[date, ...]
    scaler_mean: float
    scaler_scale: float
    training_history: LstmTrainingHistory

    def as_dict(self) -> dict[str, object]:
        return {
            "selected_epoch_count": self.selected_epoch_count,
            "best_stopping_rmse": self.best_stopping_rmse,
            "core_target_dates": [value.isoformat() for value in self.core_target_dates],
            "stopping_target_dates": [
                value.isoformat() for value in self.stopping_target_dates
            ],
            "scaler": {"mean": self.scaler_mean, "scale": self.scaler_scale},
        }


@dataclass(frozen=True, slots=True)
class LstmFoldSeedScore:
    """Outer-fold score for one predeclared seed after isolated early stopping."""

    fold_index: int
    seed: int
    rmse: float
    selected_epoch_count: int
    outer_training_target_dates: tuple[date, ...]
    stopping_target_dates: tuple[date, ...]
    validation_target_dates: tuple[date, ...]
    scaler_mean: float
    scaler_scale: float
    scaler_observations: int

    def as_dict(self) -> dict[str, object]:
        return {
            "fold_index": self.fold_index,
            "seed": self.seed,
            "rmse": self.rmse,
            "selected_epoch_count": self.selected_epoch_count,
            "outer_training_target_dates": [
                value.isoformat() for value in self.outer_training_target_dates
            ],
            "stopping_target_dates": [
                value.isoformat() for value in self.stopping_target_dates
            ],
            "validation_target_dates": [
                value.isoformat() for value in self.validation_target_dates
            ],
            "scaler": {
                "mean": self.scaler_mean,
                "scale": self.scaler_scale,
                "observations": self.scaler_observations,
            },
        }


@dataclass(frozen=True, slots=True)
class LstmSeedSummary:
    """Fold-aggregated performance for one tuning seed."""

    seed: int
    mean_rmse: float
    rmse_standard_deviation: float

    def as_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LstmCandidateResult:
    """All-fold, all-seed result for one hyperparameter configuration."""

    specification: LstmSpecification
    completed: bool
    mean_validation_rmse: float | None
    validation_rmse_standard_deviation: float | None
    seed_summaries: tuple[LstmSeedSummary, ...]
    fold_seed_scores: tuple[LstmFoldSeedScore, ...]
    failure: str | None = None
    training_histories: tuple[LstmTrainingHistory, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            **self.specification.as_dict(),
            "completed": self.completed,
            "mean_validation_rmse": self.mean_validation_rmse,
            "validation_rmse_standard_deviation": (
                self.validation_rmse_standard_deviation
            ),
            "seed_summaries": [summary.as_dict() for summary in self.seed_summaries],
            "fold_seed_scores": [score.as_dict() for score in self.fold_seed_scores],
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class LstmTuningResult:
    """Candidate selected by mean RMSE across every fold and tuning seed."""

    selected_specification: LstmSpecification
    selected_mean_validation_rmse: float
    selected_validation_rmse_standard_deviation: float
    common_validation_target_dates_by_fold: tuple[tuple[date, ...], ...]
    candidates: tuple[LstmCandidateResult, ...]

    @property
    def selected_candidate(self) -> LstmCandidateResult:
        return next(
            candidate
            for candidate in self.candidates
            if candidate.specification == self.selected_specification
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "selected_specification": self.selected_specification.as_dict(),
            "selected_mean_validation_rmse": self.selected_mean_validation_rmse,
            "selected_validation_rmse_standard_deviation": (
                self.selected_validation_rmse_standard_deviation
            ),
            "common_validation_target_dates_by_fold": [
                [value.isoformat() for value in fold_dates]
                for fold_dates in self.common_validation_target_dates_by_fold
            ],
            "selected_seed_scores": [
                summary.as_dict()
                for summary in self.selected_candidate.seed_summaries
            ],
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class LstmEvaluationResult:
    """Two-stage development fit and forecasts on common evaluation dates."""

    symbol: str
    tuning: LstmTuningResult
    epoch_selection: EpochSelection
    fitted: FittedLstmModel
    target_dates: tuple[date, ...]
    predicted_deltas: tuple[float, ...]
    predicted_closes: tuple[float, ...]
    actual_deltas: tuple[float, ...]
    actual_closes: tuple[float, ...]
    configuration: LstmConfig

    def training_histories(self) -> tuple[LstmTrainingHistory, ...]:
        """Return all tuning and final-development histories without duplication."""

        tuning_histories = tuple(
            history
            for candidate in self.tuning.candidates
            for history in candidate.training_histories
        )
        fixed_history = self.fitted.training_history
        if fixed_history is None:
            raise LstmTrainingError("Final fixed-epoch LSTM history is missing")
        histories = tuning_histories + (
            self.epoch_selection.training_history,
            fixed_history,
        )
        identities = tuple(history.identity for history in histories)
        if len(set(identities)) != len(identities):
            raise LstmTrainingError("LSTM training histories contain duplicate identities")
        return histories

    def as_metadata_dict(self, *, model_state_file: str | None = None) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "target": "next_day_close_delta",
            "input_features": ["historical_close_delta"],
            "configuration": asdict(self.configuration),
            "tuning": self.tuning.as_dict(),
            "final_development_stage_a": self.epoch_selection.as_dict(),
            "final_development_stage_b": self.fitted.metadata(),
            "evaluation_target_dates": [value.isoformat() for value in self.target_dates],
            "model_state_file": model_state_file,
            "reproducibility_note": (
                "Deterministic algorithms and fixed seeds are enabled, but exact numerical "
                "identity can still vary across PyTorch, operating-system, and hardware versions."
            ),
        }


@dataclass(frozen=True, slots=True)
class LstmProductionFit:
    """Corresponding Stage-A/Stage-B refit using all available labeled history."""

    epoch_selection: EpochSelection
    fitted: FittedLstmModel


@dataclass(frozen=True, slots=True)
class LstmArtifactPaths:
    metadata: Path
    model_state: Path
    training_history: Path | None = None


def candidate_specifications(config: LstmConfig) -> tuple[LstmSpecification, ...]:
    """Enumerate the centrally declared hyperparameter grid."""

    return tuple(
        LstmSpecification(lookback, hidden_size, learning_rate, batch_size)
        for lookback in config.lookback_lengths
        for hidden_size in config.hidden_sizes
        for learning_rate in config.learning_rates
        for batch_size in config.batch_sizes
    )


def set_deterministic_controls(seed: int) -> None:
    """Enable supported deterministic controls for the CPU training path."""

    if seed < 0:
        raise ValueError("seed cannot be negative")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def chronological_stopping_tail(
    samples: Sequence[DeltaSequenceSample],
    *,
    config: LstmConfig,
) -> tuple[tuple[DeltaSequenceSample, ...], tuple[DeltaSequenceSample, ...]]:
    """Reserve only the newest part of an outer training block for stopping."""

    chosen = tuple(samples)
    if len(chosen) < 2:
        raise LstmTrainingError("At least two samples are required for a stopping split")
    tail_size = max(
        config.minimum_stopping_samples,
        math.ceil(len(chosen) * config.stopping_tail_proportion),
    )
    tail_size = min(tail_size, len(chosen) - 1)
    core = chosen[:-tail_size]
    stopping = chosen[-tail_size:]
    if not core or not stopping or core[-1].target_date >= stopping[0].target_date:
        raise LstmTrainingError("Chronological stopping-tail construction failed")
    return core, stopping


def _scaled_tensors(
    samples: Sequence[DeltaSequenceSample],
    scaler: DeltaScaler,
) -> tuple[torch.Tensor, torch.Tensor]:
    features = scaler.transform(sequence_matrix(samples))
    targets = scaler.transform(target_array(samples))
    return (
        torch.as_tensor(features, dtype=torch.float32).unsqueeze(-1),
        torch.as_tensor(targets, dtype=torch.float32),
    )


def _train_one_epoch(
    network: UnivariateDeltaLSTM,
    optimizer: torch.optim.Optimizer,
    features: torch.Tensor,
    targets: torch.Tensor,
    *,
    batch_size: int,
) -> float:
    """Train once and return the weighted mean of already-computed batch MSEs."""

    network.train()
    loss_function = nn.MSELoss()
    total_squared_error = 0.0
    observation_count = 0
    for start in range(0, len(features), batch_size):
        batch_features = features[start : start + batch_size]
        batch_targets = targets[start : start + batch_size]
        optimizer.zero_grad(set_to_none=True)
        predicted = network(batch_features)
        loss = loss_function(predicted, batch_targets)
        if not torch.isfinite(loss):
            raise LstmTrainingError("LSTM training produced a non-finite loss")
        batch_count = len(batch_targets)
        total_squared_error += float(loss.detach().item()) * batch_count
        observation_count += batch_count
        loss.backward()
        optimizer.step()
    training_loss = total_squared_error / observation_count
    if not math.isfinite(training_loss):
        raise LstmTrainingError("LSTM epoch produced a non-finite training loss")
    return training_loss


def _scaled_rmse(
    network: UnivariateDeltaLSTM,
    features: torch.Tensor,
    targets: torch.Tensor,
) -> float:
    network.eval()
    with torch.no_grad():
        predicted = network(features)
        loss = torch.mean(torch.square(targets - predicted))
    value = float(torch.sqrt(loss).item())
    if not math.isfinite(value):
        raise LstmTrainingError("LSTM validation produced a non-finite loss")
    return value


def select_epoch_count(
    samples: Sequence[DeltaSequenceSample],
    specification: LstmSpecification,
    *,
    seed: int,
    config: LstmConfig,
    training_stage: str = FINAL_EPOCH_SELECTION_STAGE,
    fold_index: int | None = None,
) -> EpochSelection:
    """Stage A: choose epochs from an inner tail; no outer validation is accepted."""

    if training_stage not in {
        TUNING_EARLY_STOPPING_STAGE,
        FINAL_EPOCH_SELECTION_STAGE,
    }:
        raise ValueError("Epoch selection requires an early-stopping training stage")
    if training_stage == TUNING_EARLY_STOPPING_STAGE and fold_index is None:
        raise ValueError("Tuning early-stopping history requires a fold index")
    if training_stage == FINAL_EPOCH_SELECTION_STAGE and fold_index is not None:
        raise ValueError("Final epoch-selection history cannot have an outer fold index")

    core, stopping = chronological_stopping_tail(samples, config=config)
    scaler = fit_delta_scaler(core)
    core_features, core_targets = _scaled_tensors(core, scaler)
    stopping_features, stopping_targets = _scaled_tensors(stopping, scaler)
    set_deterministic_controls(seed)
    network = UnivariateDeltaLSTM(specification.hidden_size)
    optimizer = torch.optim.Adam(network.parameters(), lr=specification.learning_rate)
    best_epoch = 1
    best_rmse = math.inf
    epochs_without_improvement = 0
    epoch_records: list[LstmEpochRecord] = []
    for epoch in range(1, config.max_epochs + 1):
        training_loss = _train_one_epoch(
            network,
            optimizer,
            core_features,
            core_targets,
            batch_size=specification.batch_size,
        )
        stopping_rmse = _scaled_rmse(network, stopping_features, stopping_targets)
        if stopping_rmse < best_rmse - config.early_stopping_min_delta:
            best_rmse = stopping_rmse
            best_epoch = epoch
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        epoch_records.append(
            LstmEpochRecord(
                epoch=epoch,
                training_loss=training_loss,
                stopping_loss=stopping_rmse,
                best_stopping_loss_so_far=best_rmse,
                best_epoch_so_far=best_epoch,
                learning_rate=float(optimizer.param_groups[0]["lr"]),
            )
        )
        if epochs_without_improvement >= config.early_stopping_patience:
            break
    history = LstmTrainingHistory(
        configuration_id=lstm_configuration_id(specification),
        training_stage=training_stage,
        fold_index=fold_index,
        seed=seed,
        epochs=tuple(epoch_records),
        best_epoch=best_epoch,
        epochs_trained=len(epoch_records),
        early_stopped=len(epoch_records) < config.max_epochs,
        core_target_dates=tuple(sample.target_date for sample in core),
        stopping_target_dates=tuple(sample.target_date for sample in stopping),
    )
    return EpochSelection(
        selected_epoch_count=best_epoch,
        best_stopping_rmse=best_rmse,
        core_target_dates=tuple(sample.target_date for sample in core),
        stopping_target_dates=tuple(sample.target_date for sample in stopping),
        scaler_mean=float(scaler.mean),
        scaler_scale=float(scaler.scale),
        training_history=history,
    )


def fit_fixed_epochs(
    samples: Sequence[DeltaSequenceSample],
    specification: LstmSpecification,
    *,
    epoch_count: int,
    seed: int,
    fold_index: int | None = None,
) -> FittedLstmModel:
    """Stage B: create fresh scaler/model and train the entire supplied block."""

    chosen = tuple(samples)
    if not chosen or epoch_count < 1:
        raise ValueError("Fixed-epoch fitting requires samples and a positive epoch count")
    scaler = fit_delta_scaler(chosen)
    features, targets = _scaled_tensors(chosen, scaler)
    set_deterministic_controls(seed)
    network = UnivariateDeltaLSTM(specification.hidden_size)
    optimizer = torch.optim.Adam(network.parameters(), lr=specification.learning_rate)
    epoch_records: list[LstmEpochRecord] = []
    for epoch in range(1, epoch_count + 1):
        training_loss = _train_one_epoch(
            network,
            optimizer,
            features,
            targets,
            batch_size=specification.batch_size,
        )
        epoch_records.append(
            LstmEpochRecord(
                epoch=epoch,
                training_loss=training_loss,
                stopping_loss=None,
                best_stopping_loss_so_far=None,
                best_epoch_so_far=None,
                learning_rate=float(optimizer.param_groups[0]["lr"]),
            )
        )
    history = LstmTrainingHistory(
        configuration_id=lstm_configuration_id(specification),
        training_stage=FIXED_EPOCH_REFIT_STAGE,
        fold_index=fold_index,
        seed=seed,
        epochs=tuple(epoch_records),
        best_epoch=None,
        epochs_trained=len(epoch_records),
        early_stopped=False,
        core_target_dates=tuple(sample.target_date for sample in chosen),
        stopping_target_dates=(),
    )
    fitted = FittedLstmModel(
        network=network,
        scaler=scaler,
        specification=specification,
        epoch_count=epoch_count,
        seed=seed,
        training_size=len(chosen),
        training_history=history,
    )
    validate_model_state(fitted)
    return fitted


def _rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    actual_values = np.asarray(actual, dtype=np.float64)
    predicted_values = np.asarray(predicted, dtype=np.float64)
    return float(math.sqrt(float(np.mean(np.square(actual_values - predicted_values)))))


def _samples_for_dates(
    samples: Sequence[DeltaSequenceSample],
    target_dates: Sequence[date],
) -> tuple[DeltaSequenceSample, ...]:
    by_date = {sample.target_date: sample for sample in samples}
    missing = [value for value in target_dates if value not in by_date]
    if missing:
        raise LstmTrainingError(
            "Missing LSTM samples for target dates: "
            + ", ".join(value.isoformat() for value in missing)
        )
    return tuple(by_date[value] for value in target_dates)


def _common_development_samples(
    development_pairs: Sequence[NextDayForecastPair],
    config: LstmConfig,
) -> tuple[DeltaSequenceSample, ...]:
    return build_delta_sequence_samples(
        development_pairs,
        lookback=max(config.lookback_lengths),
    )


def score_lstm_candidate(
    development_pairs: Sequence[NextDayForecastPair],
    common_target_dates: Sequence[date],
    common_folds: Sequence[ExpandingWindowFold],
    specification: LstmSpecification,
    *,
    config: LstmConfig,
) -> LstmCandidateResult:
    """Score every outer fold and every seed on the precomputed common dates."""

    candidate_samples = build_delta_sequence_samples(
        development_pairs,
        lookback=specification.lookback,
    )
    aligned = _samples_for_dates(candidate_samples, common_target_dates)
    scores: list[LstmFoldSeedScore] = []
    histories: list[LstmTrainingHistory] = []
    try:
        for fold in common_folds:
            training = tuple(aligned[index] for index in fold.train_indices)
            validation = tuple(aligned[index] for index in fold.validation_indices)
            for seed in config.tuning_seeds:
                epoch_selection = select_epoch_count(
                    training,
                    specification,
                    seed=seed,
                    config=config,
                    training_stage=TUNING_EARLY_STOPPING_STAGE,
                    fold_index=fold.fold_index,
                )
                histories.append(epoch_selection.training_history)
                fitted = fit_fixed_epochs(
                    training,
                    specification,
                    epoch_count=epoch_selection.selected_epoch_count,
                    seed=seed,
                    fold_index=fold.fold_index,
                )
                if fitted.training_history is None:
                    raise LstmTrainingError("Tuning fixed-epoch history is missing")
                histories.append(fitted.training_history)
                predicted = fitted.predict_delta(validation)
                scores.append(
                    LstmFoldSeedScore(
                        fold_index=fold.fold_index,
                        seed=seed,
                        rmse=_rmse(target_array(validation), predicted),
                        selected_epoch_count=epoch_selection.selected_epoch_count,
                        outer_training_target_dates=tuple(
                            sample.target_date for sample in training
                        ),
                        stopping_target_dates=epoch_selection.stopping_target_dates,
                        validation_target_dates=tuple(
                            sample.target_date for sample in validation
                        ),
                        scaler_mean=float(fitted.scaler.mean),
                        scaler_scale=float(fitted.scaler.scale),
                        scaler_observations=fitted.scaler.observations,
                    )
                )
    except Exception as exc:
        return LstmCandidateResult(
            specification=specification,
            completed=False,
            mean_validation_rmse=None,
            validation_rmse_standard_deviation=None,
            seed_summaries=(),
            fold_seed_scores=tuple(scores),
            training_histories=tuple(histories),
            failure=f"{type(exc).__name__}: {exc}",
        )
    required_scores = len(common_folds) * len(config.tuning_seeds)
    if len(scores) != required_scores:
        raise RuntimeError("LSTM candidate lacks required fold/seed scores")
    configuration_id = lstm_configuration_id(specification)
    expected_keys = {
        (configuration_id, fold.fold_index, seed)
        for fold in common_folds
        for seed in config.tuning_seeds
    }
    early_stopping_keys = {
        (history.configuration_id, history.fold_index, history.seed)
        for history in histories
        if history.training_stage == TUNING_EARLY_STOPPING_STAGE
    }
    fixed_epoch_keys = {
        (history.configuration_id, history.fold_index, history.seed)
        for history in histories
        if history.training_stage == FIXED_EPOCH_REFIT_STAGE
    }
    if early_stopping_keys != expected_keys or fixed_epoch_keys != expected_keys:
        raise RuntimeError("LSTM candidate lacks required fold/seed training histories")
    if len(histories) != required_scores * 2:
        raise RuntimeError("LSTM candidate contains duplicate training histories")
    score_values = np.asarray([score.rmse for score in scores], dtype=np.float64)
    seed_summaries = tuple(
        LstmSeedSummary(
            seed=seed,
            mean_rmse=float(
                np.mean([score.rmse for score in scores if score.seed == seed])
            ),
            rmse_standard_deviation=float(
                np.std([score.rmse for score in scores if score.seed == seed])
            ),
        )
        for seed in config.tuning_seeds
    )
    return LstmCandidateResult(
        specification=specification,
        completed=True,
        mean_validation_rmse=float(np.mean(score_values)),
        validation_rmse_standard_deviation=float(np.std(score_values)),
        seed_summaries=seed_summaries,
        fold_seed_scores=tuple(scores),
        training_histories=tuple(histories),
    )


def tune_lstm(
    development_pairs: Sequence[NextDayForecastPair],
    *,
    config: LstmConfig = DEFAULT_MODEL_CONFIG.lstm,
) -> LstmTuningResult:
    """Tune all candidates using maximum-lookback common validation targets."""

    common_samples = _common_development_samples(development_pairs, config)
    common_target_dates = tuple(sample.target_date for sample in common_samples)
    folds = expanding_window_folds(len(common_samples), n_splits=config.cv_splits)
    common_validation_dates = tuple(
        tuple(common_target_dates[index] for index in fold.validation_indices)
        for fold in folds
    )
    specifications = candidate_specifications(config)
    LOGGER.info(
        "Starting LSTM tuning common_samples=%d folds=%d candidates=%d seeds=%d max_lookback=%d",
        len(common_samples),
        len(folds),
        len(specifications),
        len(config.tuning_seeds),
        max(config.lookback_lengths),
    )
    candidates = tuple(
        score_lstm_candidate(
            development_pairs,
            common_target_dates,
            folds,
            specification,
            config=config,
        )
        for specification in specifications
    )
    eligible = tuple(
        candidate
        for candidate in candidates
        if candidate.completed
        and candidate.mean_validation_rmse is not None
        and math.isfinite(candidate.mean_validation_rmse)
    )
    if not eligible:
        failures = "; ".join(
            f"{candidate.specification.as_dict()}: {candidate.failure}"
            for candidate in candidates
        )
        raise LstmTrainingError(f"No LSTM candidate completed tuning. {failures}")
    winner = min(
        eligible,
        key=lambda candidate: (
            candidate.mean_validation_rmse,
            candidate.specification,
        ),
    )
    selected_std = winner.validation_rmse_standard_deviation
    if selected_std is None:
        raise RuntimeError("Winning LSTM candidate lacks variability metadata")
    for candidate in eligible:
        observed_by_fold = tuple(
            tuple(
                next(
                    score.validation_target_dates
                    for score in candidate.fold_seed_scores
                    if score.fold_index == fold_index
                )
            )
            for fold_index in range(len(folds))
        )
        if observed_by_fold != common_validation_dates:
            raise RuntimeError("LSTM candidates did not use identical validation dates")
    LOGGER.info(
        "Completed LSTM tuning lookback=%d hidden=%d learning_rate=%s batch=%d mean_rmse=%.8f std=%.8f",
        winner.specification.lookback,
        winner.specification.hidden_size,
        winner.specification.learning_rate,
        winner.specification.batch_size,
        winner.mean_validation_rmse,
        selected_std,
    )
    return LstmTuningResult(
        selected_specification=winner.specification,
        selected_mean_validation_rmse=float(winner.mean_validation_rmse),
        selected_validation_rmse_standard_deviation=float(selected_std),
        common_validation_target_dates_by_fold=common_validation_dates,
        candidates=candidates,
    )


def train_lstm_for_evaluation(
    records: Sequence[OhlcvRecord],
    plan: CompanyEvaluationPlan,
    *,
    config: LstmConfig = DEFAULT_MODEL_CONFIG.lstm,
) -> LstmEvaluationResult:
    """Tune on development and perform the required fresh two-stage final fit."""

    require_chronological_records(records)
    tuning = tune_lstm(plan.development_pairs, config=config)
    all_samples = build_delta_sequence_samples(
        build_next_day_pairs(records),
        lookback=tuning.selected_specification.lookback,
    )
    development_samples = _samples_for_dates(
        all_samples,
        tuple(
            value
            for value in plan.development_target_dates
            if value >= all_samples[0].target_date
        ),
    )
    evaluation_samples = _samples_for_dates(all_samples, plan.evaluation_target_dates)
    epoch_selection = select_epoch_count(
        development_samples,
        tuning.selected_specification,
        seed=config.final_seed,
        config=config,
    )
    fitted = fit_fixed_epochs(
        development_samples,
        tuning.selected_specification,
        epoch_count=epoch_selection.selected_epoch_count,
        seed=config.final_seed,
    )
    predicted_deltas = fitted.predict_delta(evaluation_samples)
    predicted_closes = fitted.predict_close(evaluation_samples)
    target_dates = tuple(sample.target_date for sample in evaluation_samples)
    if target_dates != plan.evaluation_target_dates:
        raise RuntimeError("LSTM evaluation targets diverged from the common company plan")
    LOGGER.info(
        "Completed LSTM evaluation symbol=%s development=%d evaluation=%d epochs=%d seed=%d",
        plan.symbol,
        len(development_samples),
        len(evaluation_samples),
        epoch_selection.selected_epoch_count,
        config.final_seed,
    )
    return LstmEvaluationResult(
        symbol=plan.symbol,
        tuning=tuning,
        epoch_selection=epoch_selection,
        fitted=fitted,
        target_dates=target_dates,
        predicted_deltas=tuple(float(value) for value in predicted_deltas),
        predicted_closes=tuple(float(value) for value in predicted_closes),
        actual_deltas=tuple(sample.target_delta for sample in evaluation_samples),
        actual_closes=tuple(sample.actual_close for sample in evaluation_samples),
        configuration=config,
    )


def refit_lstm_for_production(
    records: Sequence[OhlcvRecord],
    *,
    selected_specification: LstmSpecification,
    config: LstmConfig = DEFAULT_MODEL_CONFIG.lstm,
) -> LstmProductionFit:
    """Repeat Stage A and Stage B on every available selected-lookback sequence."""

    require_chronological_records(records)
    samples = build_delta_sequence_samples(
        build_next_day_pairs(records),
        lookback=selected_specification.lookback,
    )
    epoch_selection = select_epoch_count(
        samples,
        selected_specification,
        seed=config.final_seed,
        config=config,
    )
    fitted = fit_fixed_epochs(
        samples,
        selected_specification,
        epoch_count=epoch_selection.selected_epoch_count,
        seed=config.final_seed,
    )
    LOGGER.info(
        "Completed LSTM production refit samples=%d epochs=%d seed=%d",
        len(samples),
        epoch_selection.selected_epoch_count,
        config.final_seed,
    )
    return LstmProductionFit(epoch_selection=epoch_selection, fitted=fitted)


def persist_lstm_artifacts(
    result: LstmEvaluationResult,
    *,
    artifact_name: str,
    artifacts_root: Path | None = None,
) -> LstmArtifactPaths:
    """Persist LSTM evaluation artifacts under backend/artifacts/evaluations."""

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    if not artifact_name or any(character not in allowed for character in artifact_name):
        raise ValueError(
            "artifact_name may contain only letters, numbers, hyphens, and underscores"
        )
    validate_model_state(result.fitted)
    root = SETTINGS.artifacts_dir if artifacts_root is None else Path(artifacts_root)
    output_dir = ArtifactManager(root).ensure_directories().evaluations / "lstm"
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / f"{artifact_name}.pt"
    metadata_path = output_dir / f"{artifact_name}.json"
    history_path = output_dir / f"{artifact_name}-training-history.json.gz"
    state_payload = {
        "schema_id": LSTM_EVALUATION_SCHEMA_ID,
        "schema_version": LSTM_EVALUATION_SCHEMA_VERSION,
        "format_version": 1,
        "specification": result.fitted.specification.as_dict(),
        "selected_epoch_count": result.fitted.epoch_count,
        "seed": result.fitted.seed,
        "scaler": result.fitted.scaler.state_dict(),
        "model_state_dict": result.fitted.cpu_state_dict(),
    }
    metadata_payload = {
        "schema_id": LSTM_EVALUATION_SCHEMA_ID,
        "schema_version": LSTM_EVALUATION_SCHEMA_VERSION,
        **result.as_metadata_dict(model_state_file=state_path.name),
    }
    histories = result.training_histories()
    history_payload = {
        "schema_id": LSTM_TRAINING_HISTORY_SCHEMA_ID,
        "schema_version": LSTM_TRAINING_HISTORY_SCHEMA_VERSION,
        "symbol": result.symbol,
        "loss_definitions": {
            "training_loss": "mean_squared_error_on_scaled_training_batches",
            "stopping_loss": (
                "root_mean_squared_error_on_scaled_internal_chronological_stopping_tail"
            ),
        },
        "histories": [history.as_dict() for history in histories],
    }
    validated_json_text(metadata_payload)
    validated_json_text(history_payload)
    temporary_state = state_path.with_name(f".{state_path.name}.tmp")
    try:
        torch.save(state_payload, temporary_state)
        loaded_state = torch.load(
            temporary_state,
            map_location="cpu",
            weights_only=True,
        )
        if not isinstance(loaded_state, dict) or not loaded_state.get("model_state_dict"):
            raise LstmTrainingError("Persisted LSTM evaluation state is incomplete")
        temporary_state.replace(state_path)
        atomic_write_json(metadata_path, metadata_payload)
        atomic_write_json_gzip(history_path, history_payload)
    except Exception:
        temporary_state.unlink(missing_ok=True)
        raise
    LOGGER.info(
        "Persisted LSTM artifacts metadata=%s model_state=%s training_history=%s histories=%d",
        metadata_path,
        state_path,
        history_path,
        len(histories),
    )
    return LstmArtifactPaths(
        metadata=metadata_path,
        model_state=state_path,
        training_history=history_path,
    )
