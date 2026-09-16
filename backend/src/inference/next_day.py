"""Exactly-one next-PSE-session forecast per company and principal model."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
import logging

from config.companies import get_company
from config.model_config import ModelId
from config.settings import manila_now
from src.data.calendar import PSETradingCalendar
from src.data.loader import load_company_history
from src.data.validator import OhlcvRecord, require_chronological_records
from src.inference.predictor import (
    load_production_model,
    predict_with_production_model,
)
from src.training.production_refit import (
    PRINCIPAL_MODELS,
    ProductionModelArtifact,
    ProductionRefitResult,
)


LOGGER = logging.getLogger(__name__)


class NextDayInferenceError(RuntimeError):
    """Raised when a complete three-model next-session result cannot be produced."""


@dataclass(frozen=True, slots=True)
class NextDayPrediction:
    symbol: str
    model: ModelId
    origin_date: date
    forecast_for: date
    origin_close: float
    predicted_delta: float
    predicted_close: float
    inference_at: datetime

    def as_dict(self) -> dict[str, str | float]:
        return {
            "symbol": self.symbol,
            "model": self.model.value,
            "origin_date": self.origin_date.isoformat(),
            "forecastFor": self.forecast_for.isoformat(),
            "origin_close": self.origin_close,
            "predicted_delta": self.predicted_delta,
            "predicted_close": self.predicted_close,
            "inference_at": self.inference_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CompanyNextDayForecast:
    symbol: str
    origin_date: date
    forecast_for: date
    predictions: tuple[NextDayPrediction, ...]

    def prediction_for(self, model: ModelId) -> NextDayPrediction:
        try:
            return {prediction.model: prediction for prediction in self.predictions}[model]
        except KeyError as exc:
            raise NextDayInferenceError(f"Missing next-day forecast for {model.value}") from exc

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "origin_date": self.origin_date.isoformat(),
            "forecastFor": self.forecast_for.isoformat(),
            "predictions": [prediction.as_dict() for prediction in self.predictions],
        }


def predict_next_day_with_artifacts(
    symbol: str,
    records: Sequence[OhlcvRecord],
    artifacts: Sequence[ProductionModelArtifact],
    *,
    calendar: PSETradingCalendar,
) -> CompanyNextDayForecast:
    """Forecast from already-loaded, checksum-validated production artifacts."""

    company = get_company(symbol)
    history = tuple(records)
    require_chronological_records(history)
    chosen_artifacts = tuple(artifacts)
    by_model = {artifact.model_family: artifact for artifact in chosen_artifacts}
    if len(by_model) != len(chosen_artifacts):
        raise NextDayInferenceError("Duplicate production model artifact")
    if set(by_model) != set(PRINCIPAL_MODELS):
        missing = sorted(model.value for model in set(PRINCIPAL_MODELS) - set(by_model))
        extra = sorted(model.value for model in set(by_model) - set(PRINCIPAL_MODELS))
        raise NextDayInferenceError(
            f"Principal production model mismatch; missing={missing} extra={extra}"
        )
    if any(artifact.metadata.symbol != company.symbol for artifact in chosen_artifacts):
        raise NextDayInferenceError("Production artifact symbol does not match company")
    origin_date = history[-1].trading_date
    forecast_for = calendar.next_trading_day(origin_date)
    inference_at = manila_now()
    predictions = tuple(
        NextDayPrediction(
            symbol=company.symbol,
            model=model,
            origin_date=origin_date,
            forecast_for=forecast_for,
            origin_close=history[-1].close,
            predicted_delta=forecast.predicted_delta,
            predicted_close=forecast.predicted_close,
            inference_at=inference_at,
        )
        for model in PRINCIPAL_MODELS
        for forecast in (predict_with_production_model(by_model[model], history),)
    )
    if len(predictions) != 3:
        raise NextDayInferenceError("Expected exactly three principal-model predictions")
    LOGGER.info(
        "Generated next-day forecasts symbol=%s origin=%s forecast_for=%s models=3",
        company.symbol,
        origin_date,
        forecast_for,
    )
    return CompanyNextDayForecast(
        symbol=company.symbol,
        origin_date=origin_date,
        forecast_for=forecast_for,
        predictions=predictions,
    )


def predict_next_day_from_fresh_refit(
    refit: ProductionRefitResult,
    records: Sequence[OhlcvRecord] | None = None,
    *,
    calendar: PSETradingCalendar,
) -> CompanyNextDayForecast:
    """Predict directly from fresh in-memory models without reloading old files."""

    history = (
        load_company_history(refit.symbol) if records is None else tuple(records)
    )
    return predict_next_day_with_artifacts(
        refit.symbol,
        history,
        refit.artifacts,
        calendar=calendar,
    )


def predict_next_day_from_artifacts(
    symbol: str,
    records: Sequence[OhlcvRecord] | None = None,
    *,
    calendar: PSETradingCalendar,
) -> CompanyNextDayForecast:
    """Load three compatible production artifacts, then forecast one PSE session."""

    company = get_company(symbol)
    history = (
        load_company_history(company.symbol) if records is None else tuple(records)
    )
    artifacts = tuple(
        load_production_model(company.symbol, model)
        for model in PRINCIPAL_MODELS
    )
    return predict_next_day_with_artifacts(
        company.symbol,
        history,
        artifacts,
        calendar=calendar,
    )
