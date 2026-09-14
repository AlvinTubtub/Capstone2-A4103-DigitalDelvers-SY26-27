"""Canonical wide, date-aligned representation of complete OOS holdout records."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import math

from config.model_config import ModelId
from src.evaluation.backtest import (
    BacktestAlignmentError,
    BacktestData,
    CanonicalPrediction,
    REQUIRED_EVALUATION_MODELS,
)


PREDICTION_FIELD_BY_MODEL: Mapping[ModelId, str] = {
    ModelId.LAG_REGRESSION: "lir_prediction",
    ModelId.ARIMA: "arima_prediction",
    ModelId.LSTM: "lstm_prediction",
    ModelId.NAIVE: "naive_prediction",
}


@dataclass(frozen=True, slots=True)
class AlignedHoldoutRow:
    """One target date with the actual Close and all four method predictions."""

    company: str
    target_date: date
    actual_close: float
    lir_prediction: float
    arima_prediction: float
    lstm_prediction: float
    naive_prediction: float

    def __post_init__(self) -> None:
        if not self.company or self.company != self.company.upper():
            raise BacktestAlignmentError("Holdout company must be non-empty and uppercase")
        values = (
            self.actual_close,
            self.lir_prediction,
            self.arima_prediction,
            self.lstm_prediction,
            self.naive_prediction,
        )
        if not all(math.isfinite(value) for value in values):
            raise BacktestAlignmentError("Holdout prices must all be finite")

    def prediction_for(self, model: ModelId) -> float:
        try:
            field = PREDICTION_FIELD_BY_MODEL[model]
        except KeyError as exc:
            raise BacktestAlignmentError(
                f"Unsupported holdout model {model.value}"
            ) from exc
        return float(getattr(self, field))

    def error_for(self, model: ModelId) -> float:
        return self.prediction_for(model) - self.actual_close

    def as_dict(self) -> dict[str, str | float]:
        return {
            "company": self.company,
            "target_date": self.target_date.isoformat(),
            "actual_close": self.actual_close,
            "lir_prediction": self.lir_prediction,
            "arima_prediction": self.arima_prediction,
            "lstm_prediction": self.lstm_prediction,
            "naive_prediction": self.naive_prediction,
        }


@dataclass(frozen=True, slots=True)
class CanonicalHoldout:
    """Unique chronological dates containing every evaluated method."""

    company: str
    rows: tuple[AlignedHoldoutRow, ...]

    def __post_init__(self) -> None:
        if not self.rows:
            raise BacktestAlignmentError("Aligned holdout cannot be empty")
        if any(row.company != self.company for row in self.rows):
            raise BacktestAlignmentError("Aligned holdout contains another company")
        dates = tuple(row.target_date for row in self.rows)
        if dates != tuple(sorted(dates)):
            raise BacktestAlignmentError("Aligned holdout dates must be chronological")
        if len(set(dates)) != len(dates):
            raise BacktestAlignmentError("Aligned holdout dates must be unique")

    @property
    def target_dates(self) -> tuple[date, ...]:
        return tuple(row.target_date for row in self.rows)

    @property
    def actual_closes(self) -> tuple[float, ...]:
        return tuple(row.actual_close for row in self.rows)

    def predictions(self, model: ModelId) -> tuple[float, ...]:
        return tuple(row.prediction_for(model) for row in self.rows)

    def errors(self, model: ModelId) -> tuple[float, ...]:
        return tuple(row.error_for(model) for row in self.rows)

    def as_dict(self) -> dict[str, object]:
        return {
            "company": self.company,
            "source": "complete_chronological_out_of_sample_evaluation",
            "records": [row.as_dict() for row in self.rows],
        }


def align_holdout_records(
    company: str,
    records_by_model: Mapping[ModelId, Sequence[CanonicalPrediction]],
) -> CanonicalHoldout:
    """Join by target date and reject missing, extra, or duplicate observations."""

    supplied_models = set(records_by_model)
    required_models = set(REQUIRED_EVALUATION_MODELS)
    if supplied_models != required_models:
        missing = sorted(model.value for model in required_models - supplied_models)
        extra = sorted(model.value for model in supplied_models - required_models)
        raise BacktestAlignmentError(
            f"Aligned holdout model-set mismatch; missing={missing} extra={extra}"
        )

    indexed: dict[ModelId, dict[date, CanonicalPrediction]] = {}
    for model in REQUIRED_EVALUATION_MODELS:
        records = tuple(records_by_model[model])
        by_date = {record.target_date: record for record in records}
        if len(by_date) != len(records):
            raise BacktestAlignmentError(
                f"Aligned holdout model {model.value} has duplicate target dates"
            )
        for record in records:
            if record.model is not model or record.symbol != company:
                raise BacktestAlignmentError(
                    f"Aligned holdout record identity mismatch for {model.value}"
                )
        indexed[model] = by_date

    expected_dates = set(indexed[REQUIRED_EVALUATION_MODELS[0]])
    if not expected_dates:
        raise BacktestAlignmentError("Aligned holdout cannot be empty")
    for model in REQUIRED_EVALUATION_MODELS[1:]:
        dates = set(indexed[model])
        if dates != expected_dates:
            missing = sorted(expected_dates - dates)
            extra = sorted(dates - expected_dates)
            raise BacktestAlignmentError(
                f"Aligned holdout target-date mismatch for {model.value}; "
                f"missing={[value.isoformat() for value in missing]} "
                f"extra={[value.isoformat() for value in extra]}"
            )

    rows: list[AlignedHoldoutRow] = []
    for target_date in sorted(expected_dates):
        records = {
            model: indexed[model][target_date] for model in REQUIRED_EVALUATION_MODELS
        }
        actuals = {record.actual_close for record in records.values()}
        if len(actuals) != 1:
            raise BacktestAlignmentError(
                f"Aligned holdout actual Close mismatch on {target_date}"
            )
        rows.append(
            AlignedHoldoutRow(
                company=company,
                target_date=target_date,
                actual_close=actuals.pop(),
                lir_prediction=records[ModelId.LAG_REGRESSION].predicted_close,
                arima_prediction=records[ModelId.ARIMA].predicted_close,
                lstm_prediction=records[ModelId.LSTM].predicted_close,
                naive_prediction=records[ModelId.NAIVE].predicted_close,
            )
        )
    return CanonicalHoldout(company=company, rows=tuple(rows))


def aligned_holdout_from_backtest(backtest: BacktestData) -> CanonicalHoldout:
    """Build the canonical wide view from the complete validated backtest."""

    holdout = align_holdout_records(
        backtest.symbol,
        {
            model: backtest.records_for(model)
            for model in REQUIRED_EVALUATION_MODELS
        },
    )
    if holdout.target_dates != tuple(sorted(backtest.target_dates)):
        raise BacktestAlignmentError("Backtest and aligned holdout target dates disagree")
    if holdout.actual_closes != tuple(
        actual
        for _, actual in sorted(
            zip(backtest.target_dates, backtest.actual_closes, strict=True)
        )
    ):
        raise BacktestAlignmentError("Backtest and aligned holdout actual Closes disagree")
    return holdout
