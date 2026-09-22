"""Single authoritative univariate PyTorch LSTM for next-day Close deltas."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import math
from typing import TYPE_CHECKING

import numpy as np
import torch
from torch import Tensor, nn

from src.features.targets import NextDayForecastPair
from src.models.base import reconstruct_close

if TYPE_CHECKING:
    from src.training.train_lstm import LstmTrainingHistory


@dataclass(frozen=True, slots=True, order=True)
class LstmSpecification:
    """One centrally configured univariate LSTM candidate."""

    lookback: int
    hidden_size: int
    learning_rate: float
    batch_size: int

    def __post_init__(self) -> None:
        if self.lookback < 1 or self.hidden_size < 1 or self.batch_size < 1:
            raise ValueError("LSTM integer hyperparameters must be positive")
        if self.learning_rate <= 0:
            raise ValueError("LSTM learning_rate must be positive")

    def as_dict(self) -> dict[str, int | float]:
        return {
            "lookback": self.lookback,
            "hidden_size": self.hidden_size,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
        }


@dataclass(frozen=True, slots=True)
class DeltaSequenceSample:
    """Past deltas available at an origin and its immediately following target."""

    source_pair_index: int
    origin_date: date
    target_date: date
    origin_close: float
    input_deltas: tuple[float, ...]
    target_delta: float
    actual_close: float


def build_delta_sequence_samples(
    pairs: Sequence[NextDayForecastPair],
    *,
    lookback: int,
) -> tuple[DeltaSequenceSample, ...]:
    """Build causal univariate sequences from historical delta-then-target pairs."""

    if lookback < 1:
        raise ValueError("lookback must be positive")
    ordered_pairs = tuple(pairs)
    if len(ordered_pairs) <= lookback:
        raise ValueError("Not enough next-day pairs for the requested lookback")
    for previous, current in zip(ordered_pairs, ordered_pairs[1:]):
        if previous.target_date != current.origin_date:
            raise ValueError("Next-day pairs must form one contiguous chronological series")
        if previous.target_date >= current.target_date:
            raise ValueError("Next-day pair targets must be strictly chronological")

    samples = tuple(
        DeltaSequenceSample(
            source_pair_index=index,
            origin_date=pair.origin_date,
            target_date=pair.target_date,
            origin_close=float(pair.origin_close),
            input_deltas=tuple(
                float(previous.target_delta)
                for previous in ordered_pairs[index - lookback : index]
            ),
            target_delta=float(pair.target_delta),
            actual_close=float(pair.actual_close),
        )
        for index, pair in enumerate(ordered_pairs)
        if index >= lookback
    )
    if any(len(sample.input_deltas) != lookback for sample in samples):
        raise RuntimeError("LSTM sequence construction produced an invalid width")
    return samples


@dataclass(slots=True)
class DeltaScaler:
    """Fold-local standardizer for the sole LSTM variable, daily Close delta."""

    mean: float | None = None
    scale: float | None = None
    observations: int = 0

    def fit(self, values: Sequence[float]) -> "DeltaScaler":
        array = np.asarray(values, dtype=np.float64).reshape(-1)
        if array.size < 1 or not np.isfinite(array).all():
            raise ValueError("Scaler values must be a non-empty finite sequence")
        self.mean = float(np.mean(array))
        standard_deviation = float(np.std(array))
        self.scale = standard_deviation if standard_deviation > 0.0 else 1.0
        self.observations = int(array.size)
        return self

    def transform(self, values: Sequence[float] | np.ndarray) -> np.ndarray:
        if self.mean is None or self.scale is None:
            raise RuntimeError("DeltaScaler must be fitted before transformation")
        array = np.asarray(values, dtype=np.float64)
        if not np.isfinite(array).all():
            raise ValueError("Scaler inputs must be finite")
        return (array - self.mean) / self.scale

    def inverse_transform(self, values: Sequence[float] | np.ndarray) -> np.ndarray:
        if self.mean is None or self.scale is None:
            raise RuntimeError("DeltaScaler must be fitted before inverse transformation")
        array = np.asarray(values, dtype=np.float64)
        if not np.isfinite(array).all():
            raise ValueError("Scaler inputs must be finite")
        return array * self.scale + self.mean

    def state_dict(self) -> dict[str, float | int]:
        if self.mean is None or self.scale is None:
            raise RuntimeError("DeltaScaler must be fitted before state export")
        return {
            "mean": self.mean,
            "scale": self.scale,
            "observations": self.observations,
        }


def scaler_values_for_samples(samples: Sequence[DeltaSequenceSample]) -> tuple[float, ...]:
    """Return each chronological delta once through the last training target."""

    chosen = tuple(samples)
    if not chosen:
        raise ValueError("At least one sequence sample is required")
    if any(
        current.source_pair_index + 1 != following.source_pair_index
        for current, following in zip(chosen, chosen[1:])
    ):
        raise ValueError("Scaler samples must be one contiguous chronological block")
    return chosen[0].input_deltas + tuple(sample.target_delta for sample in chosen)


def fit_delta_scaler(samples: Sequence[DeltaSequenceSample]) -> DeltaScaler:
    """Fit a fresh scaler using only one declared training block."""

    return DeltaScaler().fit(scaler_values_for_samples(samples))


def sequence_matrix(samples: Sequence[DeltaSequenceSample]) -> np.ndarray:
    chosen = tuple(samples)
    if not chosen:
        raise ValueError("At least one sequence sample is required")
    matrix = np.asarray([sample.input_deltas for sample in chosen], dtype=np.float64)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("LSTM sequences must form a finite two-dimensional matrix")
    return matrix


def target_array(samples: Sequence[DeltaSequenceSample]) -> np.ndarray:
    values = np.asarray(
        [sample.target_delta for sample in samples], dtype=np.float64
    ).reshape(-1)
    if values.size < 1 or not np.isfinite(values).all():
        raise ValueError("LSTM targets must be a non-empty finite sequence")
    return values


class UnivariateDeltaLSTM(nn.Module):
    """A one-feature LSTM followed by a scalar next-delta head."""

    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        if hidden_size < 1:
            raise ValueError("hidden_size must be positive")
        self.lstm = nn.LSTM(input_size=1, hidden_size=hidden_size, batch_first=True)
        self.output = nn.Linear(hidden_size, 1)

    def forward(self, inputs: Tensor) -> Tensor:
        if inputs.ndim != 3 or inputs.shape[-1] != 1:
            raise ValueError("Univariate LSTM input must have shape [batch, time, 1]")
        outputs, _ = self.lstm(inputs)
        return self.output(outputs[:, -1, :]).squeeze(-1)


@dataclass(slots=True)
class FittedLstmModel:
    """Fresh scaler/model state produced by a fixed-epoch training stage."""

    network: UnivariateDeltaLSTM
    scaler: DeltaScaler
    specification: LstmSpecification
    epoch_count: int
    seed: int
    training_size: int
    training_history: LstmTrainingHistory | None = None

    def predict_delta(
        self,
        samples: Sequence[DeltaSequenceSample],
    ) -> np.ndarray:
        chosen = tuple(samples)
        matrix = sequence_matrix(chosen)
        return self.predict_delta_sequences(matrix)

    def predict_delta_sequences(
        self,
        sequences: Sequence[Sequence[float]] | np.ndarray,
    ) -> np.ndarray:
        """Predict unlabeled next deltas from causal production sequences."""

        matrix = np.asarray(sequences, dtype=np.float64)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.ndim != 2 or not np.isfinite(matrix).all():
            raise ValueError("Prediction sequences must be a finite two-dimensional matrix")
        if matrix.shape[1] != self.specification.lookback:
            raise ValueError("Prediction sequence width does not match model lookback")
        scaled = self.scaler.transform(matrix)
        inputs = torch.as_tensor(scaled, dtype=torch.float32).unsqueeze(-1)
        self.network.eval()
        with torch.no_grad():
            scaled_predictions = self.network(inputs).cpu().numpy().astype(np.float64)
        predictions = self.scaler.inverse_transform(scaled_predictions).reshape(-1)
        if predictions.shape != (len(matrix),) or not np.isfinite(predictions).all():
            raise RuntimeError("LSTM produced invalid prediction output")
        return predictions

    def predict_close(
        self,
        samples: Sequence[DeltaSequenceSample],
    ) -> np.ndarray:
        chosen = tuple(samples)
        origin_closes = np.asarray(
            [sample.origin_close for sample in chosen], dtype=np.float64
        )
        return np.asarray(
            reconstruct_close(origin_closes, self.predict_delta(chosen)),
            dtype=np.float64,
        )

    def metadata(self) -> dict[str, object]:
        return {
            **self.specification.as_dict(),
            "selected_epoch_count": self.epoch_count,
            "seed": self.seed,
            "training_size": self.training_size,
            "scaler": self.scaler.state_dict(),
            "input_features": ["historical_close_delta"],
            "target": "next_day_close_delta",
        }

    def cpu_state_dict(self) -> dict[str, Tensor]:
        """Copy tensors to CPU for portable artifact persistence."""

        return {
            name: value.detach().cpu().clone()
            for name, value in self.network.state_dict().items()
        }


def validate_model_state(model: FittedLstmModel) -> None:
    """Reject non-finite fitted tensors before forecasting or persistence."""

    for name, value in model.network.state_dict().items():
        if not torch.isfinite(value).all():
            raise RuntimeError(f"LSTM model state contains non-finite values in {name}")
    if model.scaler.mean is None or model.scaler.scale is None:
        raise RuntimeError("LSTM scaler has not been fitted")
    if not math.isfinite(model.scaler.mean) or not math.isfinite(model.scaler.scale):
        raise RuntimeError("LSTM scaler state is not finite")
    if model.scaler.scale <= 0:
        raise RuntimeError("LSTM scaler scale must be positive")
