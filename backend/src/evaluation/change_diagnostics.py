"""Supplementary diagnostics for one-step changes implied by OOS Close forecasts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
from dataclasses import dataclass
from datetime import date
import math
from pathlib import Path

import numpy as np

from config.model_config import ModelId
from src.evaluation.backtest import (
    BacktestData,
    CanonicalPrediction,
    REQUIRED_EVALUATION_MODELS,
)


# This is numerical-zero tolerance, not an economically meaningful price threshold.
CHANGE_ZERO_TOLERANCE = 1e-8


class ChangeDiagnosticError(ValueError):
    """Raised when movement diagnostics receive incomplete or misaligned evidence."""


@dataclass(frozen=True, slots=True)
class ChangeDiagnostic:
    """Full dated movement evidence for one company and one evaluated method."""

    symbol: str
    model: ModelId
    target_dates: tuple[date, ...]
    actual_changes: tuple[float, ...]
    predicted_changes: tuple[float, ...]
    correlation: float | None
    correlation_status: str
    predicted_change_std: float
    actual_change_std: float
    amplitude_ratio: float | None
    amplitude_ratio_status: str
    directional_accuracy: float
    mean_predicted_change: float
    mean_actual_change: float
    near_zero_prediction_rate: float
    zero_tolerance: float = CHANGE_ZERO_TOLERANCE

    @property
    def observation_count(self) -> int:
        return len(self.target_dates)

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "model": self.model.value,
            "observation_count": self.observation_count,
            "target_dates": [value.isoformat() for value in self.target_dates],
            "actual_changes": list(self.actual_changes),
            "predicted_changes": list(self.predicted_changes),
            "correlation": self.correlation,
            "correlation_status": self.correlation_status,
            "predicted_change_std": self.predicted_change_std,
            "actual_change_std": self.actual_change_std,
            "standard_deviation_convention": "sample_ddof_1",
            "amplitude_ratio": self.amplitude_ratio,
            "amplitude_ratio_status": self.amplitude_ratio_status,
            "directional_accuracy": self.directional_accuracy,
            "direction_rule": {
                "positive": "change > tolerance",
                "negative": "change < -tolerance",
                "zero": "otherwise",
                "zero_to_zero_is_correct": True,
            },
            "mean_predicted_change": self.mean_predicted_change,
            "mean_actual_change": self.mean_actual_change,
            "near_zero_prediction_rate": self.near_zero_prediction_rate,
            "zero_tolerance": self.zero_tolerance,
            "zero_tolerance_role": "numerical_zero_only",
        }


def direction_class(
    change: float,
    *,
    tolerance: float = CHANGE_ZERO_TOLERANCE,
) -> int:
    """Map a finite movement to the declared negative/zero/positive classes."""

    if not math.isfinite(change):
        raise ChangeDiagnosticError("Direction input must be finite")
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ChangeDiagnosticError("Direction tolerance must be finite and non-negative")
    if change > tolerance:
        return 1
    if change < -tolerance:
        return -1
    return 0


def _validate_backtest(backtest: BacktestData) -> None:
    dates = tuple(backtest.target_dates)
    if len(dates) < 2:
        raise ChangeDiagnosticError(
            "Change diagnostics require at least two target observations"
        )
    if dates != tuple(sorted(dates)):
        raise ChangeDiagnosticError("Target dates must be chronological")
    if len(set(dates)) != len(dates):
        raise ChangeDiagnosticError("Target dates must be unique")
    if len(backtest.actual_closes) != len(dates):
        raise ChangeDiagnosticError("Target dates and actual Close values must align")
    supplied_models = tuple(model for model, _ in backtest.records_by_model)
    if len(set(supplied_models)) != len(supplied_models):
        raise ChangeDiagnosticError("Backtest contains duplicate model groups")
    if set(supplied_models) != set(REQUIRED_EVALUATION_MODELS):
        raise ChangeDiagnosticError("Backtest must contain all four evaluated methods")

    reference_origins: tuple[tuple[date, float], ...] | None = None
    for model in REQUIRED_EVALUATION_MODELS:
        records = backtest.records_for(model)
        if len(records) != len(dates):
            raise ChangeDiagnosticError(
                f"Model {model.value} observation count does not match target dates"
            )
        model_dates = tuple(record.target_date for record in records)
        if model_dates != dates:
            raise ChangeDiagnosticError(
                f"Model {model.value} target dates are misaligned"
            )
        origins = tuple((record.origin_date, record.origin_close) for record in records)
        if reference_origins is None:
            reference_origins = origins
        elif origins != reference_origins:
            raise ChangeDiagnosticError(
                f"Model {model.value} origin dates or closes are misaligned"
            )
        for index, record in enumerate(records):
            if record.symbol != backtest.symbol or record.model is not model:
                raise ChangeDiagnosticError("Prediction identity is inconsistent")
            if record.actual_close != backtest.actual_closes[index]:
                raise ChangeDiagnosticError(
                    f"Model {model.value} actual Close is inconsistent"
                )
            values = (
                record.origin_close,
                record.actual_close,
                record.predicted_close,
            )
            if not all(math.isfinite(value) for value in values):
                raise ChangeDiagnosticError("Prediction values must all be finite")
            if model is ModelId.NAIVE and record.predicted_close != record.origin_close:
                raise ChangeDiagnosticError(
                    "Naive predicted Close must equal the forecast-origin Close"
                )


def compute_change_diagnostics(
    backtest: BacktestData,
    *,
    tolerance: float = CHANGE_ZERO_TOLERANCE,
) -> tuple[ChangeDiagnostic, ...]:
    """Calculate level-independent next-session movement diagnostics."""

    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ChangeDiagnosticError("Change tolerance must be finite and non-negative")
    _validate_backtest(backtest)
    output: list[ChangeDiagnostic] = []
    reference_actual_changes: tuple[float, ...] | None = None
    for model in REQUIRED_EVALUATION_MODELS:
        records = backtest.records_for(model)
        actual_changes = tuple(
            float(record.actual_close - record.origin_close) for record in records
        )
        predicted_changes = tuple(
            float(record.predicted_close - record.origin_close) for record in records
        )
        if reference_actual_changes is None:
            reference_actual_changes = actual_changes
        elif actual_changes != reference_actual_changes:
            raise ChangeDiagnosticError("Actual changes differ between model records")
        actual = np.asarray(actual_changes, dtype=np.float64)
        predicted = np.asarray(predicted_changes, dtype=np.float64)
        if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
            raise ChangeDiagnosticError("Computed changes must all be finite")

        actual_std = float(np.std(actual, ddof=1))
        predicted_std = float(np.std(predicted, ddof=1))
        if not math.isfinite(actual_std) or not math.isfinite(predicted_std):
            raise ChangeDiagnosticError("Change standard deviations must be finite")
        if predicted_std <= tolerance:
            correlation = None
            correlation_status = "undefined_constant_prediction"
        elif actual_std <= tolerance:
            correlation = None
            correlation_status = "undefined_constant_actual"
        else:
            correlation = float(np.corrcoef(actual, predicted)[0, 1])
            if not math.isfinite(correlation):
                raise ChangeDiagnosticError("Change correlation is non-finite")
            correlation_status = "available"

        if actual_std <= tolerance:
            amplitude_ratio = None
            amplitude_ratio_status = "undefined_zero_actual_variance"
        else:
            amplitude_ratio = float(predicted_std / actual_std)
            if not math.isfinite(amplitude_ratio):
                raise ChangeDiagnosticError("Amplitude ratio is non-finite")
            amplitude_ratio_status = "available"

        actual_directions = np.asarray(
            [direction_class(value, tolerance=tolerance) for value in actual],
            dtype=np.int8,
        )
        predicted_directions = np.asarray(
            [direction_class(value, tolerance=tolerance) for value in predicted],
            dtype=np.int8,
        )
        directional_accuracy = float(
            np.mean(predicted_directions == actual_directions)
        )
        near_zero_rate = float(np.mean(np.abs(predicted) <= tolerance))
        diagnostic = ChangeDiagnostic(
            symbol=backtest.symbol,
            model=model,
            target_dates=tuple(backtest.target_dates),
            actual_changes=actual_changes,
            predicted_changes=predicted_changes,
            correlation=correlation,
            correlation_status=correlation_status,
            predicted_change_std=predicted_std,
            actual_change_std=actual_std,
            amplitude_ratio=amplitude_ratio,
            amplitude_ratio_status=amplitude_ratio_status,
            directional_accuracy=directional_accuracy,
            mean_predicted_change=float(np.mean(predicted)),
            mean_actual_change=float(np.mean(actual)),
            near_zero_prediction_rate=near_zero_rate,
            zero_tolerance=tolerance,
        )
        output.append(diagnostic)
    return tuple(output)


def backtest_from_archived_holdout(
    symbol: str,
    archived_records: Sequence[Mapping[str, object]],
    frozen_raw_csv: Path,
) -> BacktestData:
    """Reconstruct origins from frozen raw data and validate archived Naive levels."""

    raw_dates: list[date] = []
    raw_closes: list[float] = []
    try:
        with Path(frozen_raw_csv).open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or not {"Date", "Close"}.issubset(
                reader.fieldnames
            ):
                raise ChangeDiagnosticError("Frozen raw CSV requires Date and Close")
            for row in reader:
                raw_dates.append(date.fromisoformat(str(row["Date"])))
                raw_closes.append(float(str(row["Close"])))
    except (OSError, TypeError, ValueError) as exc:
        raise ChangeDiagnosticError(f"Cannot read frozen raw evidence: {exc}") from exc
    if not raw_dates or len(set(raw_dates)) != len(raw_dates):
        raise ChangeDiagnosticError("Frozen raw dates must be non-empty and unique")
    if tuple(raw_dates) != tuple(sorted(raw_dates)):
        raise ChangeDiagnosticError("Frozen raw dates must be chronological")
    if not all(math.isfinite(value) for value in raw_closes):
        raise ChangeDiagnosticError("Frozen raw Close values must be finite")
    raw_index = {value: index for index, value in enumerate(raw_dates)}

    prediction_field = {
        ModelId.LAG_REGRESSION: "lir_prediction",
        ModelId.ARIMA: "arima_prediction",
        ModelId.LSTM: "lstm_prediction",
        ModelId.NAIVE: "naive_prediction",
    }
    records_by_model: dict[ModelId, list[CanonicalPrediction]] = {
        model: [] for model in REQUIRED_EVALUATION_MODELS
    }
    target_dates: list[date] = []
    actual_closes: list[float] = []
    for item in archived_records:
        try:
            if item["company"] != symbol:
                raise ChangeDiagnosticError("Archived holdout contains another company")
            target_date = date.fromisoformat(str(item["target_date"]))
            actual_close = float(item["actual_close"])
            naive_prediction = float(item["naive_prediction"])
            target_index = raw_index[target_date]
        except (KeyError, TypeError, ValueError) as exc:
            raise ChangeDiagnosticError(
                f"Archived holdout record is malformed: {exc}"
            ) from exc
        if target_index == 0:
            raise ChangeDiagnosticError(
                f"Target date {target_date} has no preceding frozen trading row"
            )
        origin_date = raw_dates[target_index - 1]
        origin_close = raw_closes[target_index - 1]
        if actual_close != raw_closes[target_index]:
            raise ChangeDiagnosticError(
                f"Archived actual Close disagrees with frozen raw on {target_date}"
            )
        if naive_prediction != origin_close:
            raise ChangeDiagnosticError(
                f"Archived Naive prediction disagrees with verified origin Close on {target_date}"
            )
        target_dates.append(target_date)
        actual_closes.append(actual_close)
        for model in REQUIRED_EVALUATION_MODELS:
            try:
                predicted_close = float(item[prediction_field[model]])
            except (KeyError, TypeError, ValueError) as exc:
                raise ChangeDiagnosticError(
                    f"Archived {model.value} prediction is malformed"
                ) from exc
            records_by_model[model].append(
                CanonicalPrediction.create(
                    symbol=symbol,
                    model=model,
                    origin_date=origin_date,
                    target_date=target_date,
                    origin_close=origin_close,
                    actual_close=actual_close,
                    predicted_close=predicted_close,
                )
            )
    backtest = BacktestData(
        symbol=symbol,
        target_dates=tuple(target_dates),
        actual_closes=tuple(actual_closes),
        records_by_model=tuple(
            (model, tuple(records_by_model[model]))
            for model in REQUIRED_EVALUATION_MODELS
        ),
    )
    _validate_backtest(backtest)
    return backtest


def archived_change_diagnostics(
    symbol: str,
    archived_records: Sequence[Mapping[str, object]],
    frozen_raw_csv: Path,
    *,
    tolerance: float = CHANGE_ZERO_TOLERANCE,
) -> tuple[ChangeDiagnostic, ...]:
    """Validate a frozen formal holdout and calculate its movement diagnostics."""

    return compute_change_diagnostics(
        backtest_from_archived_holdout(symbol, archived_records, frozen_raw_csv),
        tolerance=tolerance,
    )
