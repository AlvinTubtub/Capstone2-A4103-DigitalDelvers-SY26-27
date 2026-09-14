"""Strict schemas for immutable prospective forecast ledger events."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
import hashlib
import math
from typing import Final

from config.companies import get_company
from config.model_config import ModelId
from config.settings import MANILA_TIMEZONE


LEDGER_SCHEMA_ID: Final[str] = "forecastph.prospective-forecast-ledger-event"
LEDGER_SCHEMA_VERSION: Final[int] = 1
NAIVE_MODEL_VERSION: Final[str] = "naive-close-persistence-v1"


class LedgerValidationError(ValueError):
    """Raised when an event would make prospective evidence ambiguous."""


class LedgerEventType(StrEnum):
    FORECAST_ISSUED = "forecast_issued"
    FORECAST_OUTCOME_OBSERVED = "forecast_outcome_observed"


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LedgerValidationError(f"{name} must be timezone-aware")


def _require_finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LedgerValidationError(f"{name} must be numeric")
    if not math.isfinite(float(value)):
        raise LedgerValidationError(f"{name} must be finite")


def build_forecast_id(
    symbol: str,
    origin_date: date,
    target_date: date,
    method: ModelId,
) -> str:
    """Build a stable ID for one symbol/origin/target/method issuance slot."""

    normalized_symbol = get_company(symbol).symbol
    if origin_date >= target_date:
        raise LedgerValidationError("Forecast origin must precede its target")
    identity = "|".join(
        (
            "forecastph-v1",
            normalized_symbol,
            origin_date.isoformat(),
            target_date.isoformat(),
            method.value,
        )
    )
    return f"forecastph-v1-{hashlib.sha256(identity.encode()).hexdigest()}"


@dataclass(frozen=True, slots=True)
class ForecastIssued:
    forecast_id: str
    created_at: datetime
    symbol: str
    origin_date: date
    target_date: date
    method: ModelId
    model_version: str
    prediction: float
    production_run_id: str | None = None
    source_commit: str | None = None

    def __post_init__(self) -> None:
        company = get_company(self.symbol)
        if company.symbol != self.symbol:
            raise LedgerValidationError("Forecast symbol must be canonical uppercase")
        _require_aware(self.created_at, "created_at")
        _require_finite(self.prediction, "prediction")
        if self.prediction <= 0:
            raise LedgerValidationError("Forecast Close prediction must be positive")
        if not isinstance(self.model_version, str) or not self.model_version.strip():
            raise LedgerValidationError("model_version cannot be blank")
        if self.method is ModelId.NAIVE and self.model_version != NAIVE_MODEL_VERSION:
            raise LedgerValidationError(
                "Prospective Naive forecasts require the canonical Naive model version"
            )
        for name, value in (
            ("production_run_id", self.production_run_id),
            ("source_commit", self.source_commit),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise LedgerValidationError(f"{name} must be a non-empty string or null")
        expected_id = build_forecast_id(
            self.symbol,
            self.origin_date,
            self.target_date,
            self.method,
        )
        if self.forecast_id != expected_id:
            raise LedgerValidationError("forecast_id does not match its issuance slot")

    @classmethod
    def create(
        cls,
        *,
        created_at: datetime,
        symbol: str,
        origin_date: date,
        target_date: date,
        method: ModelId,
        model_version: str,
        prediction: float,
        production_run_id: str | None = None,
        source_commit: str | None = None,
    ) -> "ForecastIssued":
        normalized = get_company(symbol).symbol
        return cls(
            forecast_id=build_forecast_id(
                normalized, origin_date, target_date, method
            ),
            created_at=created_at,
            symbol=normalized,
            origin_date=origin_date,
            target_date=target_date,
            method=method,
            model_version=model_version,
            prediction=float(prediction),
            production_run_id=production_run_id,
            source_commit=source_commit,
        )

    def immutable_payload(self) -> tuple[object, ...]:
        """Exclude retry time while retaining every forecast-defining field."""

        return (
            self.forecast_id,
            self.symbol,
            self.origin_date,
            self.target_date,
            self.method,
            self.model_version,
            self.prediction,
            self.production_run_id,
            self.source_commit,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_id": LEDGER_SCHEMA_ID,
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event_type": LedgerEventType.FORECAST_ISSUED.value,
            "forecast_id": self.forecast_id,
            "created_at": self.created_at.isoformat(),
            "symbol": self.symbol,
            "origin_date": self.origin_date.isoformat(),
            "target_date": self.target_date.isoformat(),
            "method": self.method.value,
            "model_version": self.model_version,
            "prediction": self.prediction,
            "production_run_id": self.production_run_id,
            "source_commit": self.source_commit,
        }


@dataclass(frozen=True, slots=True)
class ForecastOutcomeObserved:
    forecast_id: str
    observed_at: datetime
    actual_close: float
    error: float
    absolute_error: float
    squared_error: float

    def __post_init__(self) -> None:
        if not isinstance(self.forecast_id, str) or not self.forecast_id.strip():
            raise LedgerValidationError("forecast_id cannot be blank")
        _require_aware(self.observed_at, "observed_at")
        for name, value in (
            ("actual_close", self.actual_close),
            ("error", self.error),
            ("absolute_error", self.absolute_error),
            ("squared_error", self.squared_error),
        ):
            _require_finite(value, name)
        if self.actual_close <= 0:
            raise LedgerValidationError("Observed Close must be positive")
        if self.absolute_error < 0 or self.squared_error < 0:
            raise LedgerValidationError("Derived error magnitudes cannot be negative")

    @classmethod
    def create(
        cls,
        issuance: ForecastIssued,
        *,
        observed_at: datetime,
        actual_close: float,
    ) -> "ForecastOutcomeObserved":
        actual = float(actual_close)
        error = issuance.prediction - actual
        return cls(
            forecast_id=issuance.forecast_id,
            observed_at=observed_at,
            actual_close=actual,
            error=error,
            absolute_error=abs(error),
            squared_error=error * error,
        )

    def validate_against(self, issuance: ForecastIssued) -> None:
        if self.forecast_id != issuance.forecast_id:
            raise LedgerValidationError("Outcome does not reference this issuance")
        if self.observed_at < issuance.created_at:
            raise LedgerValidationError("Outcome cannot precede forecast issuance")
        if self.observed_at.astimezone(MANILA_TIMEZONE).date() < issuance.target_date:
            raise LedgerValidationError("Outcome cannot precede the target session")
        expected_error = issuance.prediction - self.actual_close
        expected = (expected_error, abs(expected_error), expected_error * expected_error)
        observed = (self.error, self.absolute_error, self.squared_error)
        if any(
            not math.isclose(actual, wanted, rel_tol=1e-12, abs_tol=1e-12)
            for actual, wanted in zip(observed, expected, strict=True)
        ):
            raise LedgerValidationError(
                "Outcome derived errors disagree with the immutable prediction"
            )

    def immutable_payload(self) -> tuple[object, ...]:
        return (
            self.forecast_id,
            self.actual_close,
            self.error,
            self.absolute_error,
            self.squared_error,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_id": LEDGER_SCHEMA_ID,
            "schema_version": LEDGER_SCHEMA_VERSION,
            "event_type": LedgerEventType.FORECAST_OUTCOME_OBSERVED.value,
            "forecast_id": self.forecast_id,
            "observed_at": self.observed_at.isoformat(),
            "actual_close": self.actual_close,
            "error": self.error,
            "absolute_error": self.absolute_error,
            "squared_error": self.squared_error,
        }


LedgerEvent = ForecastIssued | ForecastOutcomeObserved


def parse_ledger_event(payload: object) -> LedgerEvent:
    if not isinstance(payload, dict):
        raise LedgerValidationError("Ledger event must be a JSON object")
    if (
        payload.get("schema_id") != LEDGER_SCHEMA_ID
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != LEDGER_SCHEMA_VERSION
    ):
        raise LedgerValidationError("Ledger event schema is incompatible")
    event_type = payload.get("event_type")
    try:
        if event_type == LedgerEventType.FORECAST_ISSUED.value:
            expected_fields = {
                "schema_id", "schema_version", "event_type", "forecast_id",
                "created_at", "symbol", "origin_date", "target_date", "method",
                "model_version", "prediction", "production_run_id", "source_commit",
            }
            if set(payload) != expected_fields:
                raise LedgerValidationError("Forecast-issued fields are incomplete")
            return ForecastIssued(
                forecast_id=payload["forecast_id"],
                created_at=datetime.fromisoformat(payload["created_at"]),
                symbol=payload["symbol"],
                origin_date=date.fromisoformat(payload["origin_date"]),
                target_date=date.fromisoformat(payload["target_date"]),
                method=ModelId(payload["method"]),
                model_version=payload["model_version"],
                prediction=payload["prediction"],
                production_run_id=payload["production_run_id"],
                source_commit=payload["source_commit"],
            )
        if event_type == LedgerEventType.FORECAST_OUTCOME_OBSERVED.value:
            expected_fields = {
                "schema_id", "schema_version", "event_type", "forecast_id",
                "observed_at", "actual_close", "error", "absolute_error",
                "squared_error",
            }
            if set(payload) != expected_fields:
                raise LedgerValidationError("Forecast-outcome fields are incomplete")
            return ForecastOutcomeObserved(
                forecast_id=payload["forecast_id"],
                observed_at=datetime.fromisoformat(payload["observed_at"]),
                actual_close=payload["actual_close"],
                error=payload["error"],
                absolute_error=payload["absolute_error"],
                squared_error=payload["squared_error"],
            )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, LedgerValidationError):
            raise
        raise LedgerValidationError("Ledger event values are malformed") from exc
    raise LedgerValidationError(f"Unsupported ledger event type: {event_type!r}")
