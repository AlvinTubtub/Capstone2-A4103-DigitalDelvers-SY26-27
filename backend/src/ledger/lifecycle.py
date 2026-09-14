"""Prospective ledger steps surrounding persisted-model daily inference."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
import json
import logging
import math
from pathlib import Path

from config.companies import get_company
from config.model_config import ModelId
from config.settings import SETTINGS, manila_now
from src.data.calendar import PSETradingCalendar
from src.data.validator import OhlcvRecord, require_chronological_records
from src.inference.next_day import CompanyNextDayForecast, NextDayPrediction
from src.ledger.schema import (
    ForecastIssued,
    ForecastOutcomeObserved,
    LedgerValidationError,
    NAIVE_MODEL_VERSION,
)
from src.ledger.store import AppendResult, ForecastLedger
from src.training.production_refit import (
    PRINCIPAL_MODELS,
    validate_model_artifact_metadata,
)


LOGGER = logging.getLogger(__name__)


class LedgerLifecycleError(RuntimeError):
    """Raised when EOD observations and prospective forecasts do not align."""


def production_model_versions(
    symbol: str,
    *,
    artifacts_root: Path = SETTINGS.artifacts_dir,
) -> dict[ModelId, str]:
    """Read validated immutable model identities without fitting or forecasting."""

    company = get_company(symbol)
    versions: dict[ModelId, str] = {}
    for model in PRINCIPAL_MODELS:
        path = Path(artifacts_root) / "models" / company.symbol / f"{model.value}.metadata.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LedgerLifecycleError(
                f"Cannot read production metadata for {company.symbol}/{model.value}"
            ) from exc
        if not isinstance(payload, dict):
            raise LedgerLifecycleError("Production metadata must be an object")
        metadata = validate_model_artifact_metadata(
            payload,
            expected_symbol=company.symbol,
            expected_model=model,
        )
        versions[model] = (
            f"{metadata.implementation_version}:{metadata.artifact_sha256}"
        )
    return versions


def load_persisted_next_day_forecast(
    symbol: str,
    *,
    artifacts_root: Path = SETTINGS.artifacts_dir,
) -> CompanyNextDayForecast:
    """Strictly reconstruct the current three-model forecast artifact."""

    company = get_company(symbol)
    path = Path(artifacts_root) / "forecasts" / f"{company.symbol}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload["schema_id"] != "forecastph.next-day-forecast"
            or type(payload["schema_version"]) is not int
            or payload["schema_version"] != 1
            or payload["symbol"] != company.symbol
        ):
            raise LedgerLifecycleError("Persisted forecast identity is incompatible")
        origin_date = date.fromisoformat(payload["origin_date"])
        target_date = date.fromisoformat(payload["forecastFor"])
        predictions = tuple(
            NextDayPrediction(
                symbol=item["symbol"],
                model=ModelId(item["model"]),
                origin_date=date.fromisoformat(item["origin_date"]),
                forecast_for=date.fromisoformat(item["forecastFor"]),
                origin_close=float(item["origin_close"]),
                predicted_delta=float(item["predicted_delta"]),
                predicted_close=float(item["predicted_close"]),
                inference_at=datetime.fromisoformat(item["inference_at"]),
            )
            for item in payload["predictions"]
        )
    except LedgerLifecycleError:
        raise
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise LedgerLifecycleError(
            f"Cannot read valid persisted forecast for {company.symbol}"
        ) from exc
    return CompanyNextDayForecast(
        symbol=company.symbol,
        origin_date=origin_date,
        forecast_for=target_date,
        predictions=predictions,
    )


def resolve_pending_outcomes(
    ledger: ForecastLedger,
    records_by_symbol: Mapping[str, Sequence[OhlcvRecord]],
    *,
    observed_at: datetime | None = None,
) -> tuple[AppendResult, ...]:
    """Append actuals for exact pending target dates; never use a later-row substitute."""

    timestamp = manila_now() if observed_at is None else observed_at
    snapshot = ledger.read()
    outcomes: list[ForecastOutcomeObserved] = []
    for record in snapshot.pending:
        symbol = record.issuance.symbol
        if symbol not in records_by_symbol:
            continue
        history = tuple(records_by_symbol[symbol])
        require_chronological_records(history)
        by_date = {item.trading_date: item.close for item in history}
        target_date = record.issuance.target_date
        if target_date in by_date:
            outcomes.append(
                ForecastOutcomeObserved.create(
                    record.issuance,
                    observed_at=timestamp,
                    actual_close=by_date[target_date],
                )
            )
        elif history[-1].trading_date > target_date:
            raise LedgerLifecycleError(
                f"Missing target-date Close for pending forecast "
                f"{symbol}/{target_date.isoformat()}"
            )
    results = ledger.append_outcomes(outcomes)
    LOGGER.info(
        "Prospective outcomes resolved pending=%d appended=%d",
        len(outcomes),
        sum(result.appended for result in results),
    )
    return results


def issue_company_forecasts(
    ledger: ForecastLedger,
    forecast: CompanyNextDayForecast,
    records: Sequence[OhlcvRecord],
    *,
    model_versions: Mapping[ModelId, str],
    calendar: PSETradingCalendar,
    production_run_id: str | None = None,
    source_commit: str | None = None,
) -> tuple[AppendResult, ...]:
    """Append three deployed forecasts and the same-origin Naive benchmark."""

    company = get_company(forecast.symbol)
    history = tuple(records)
    require_chronological_records(history)
    latest = history[-1]
    predictions = tuple(forecast.predictions)
    if (
        len(predictions) != len(PRINCIPAL_MODELS)
        or {item.model for item in predictions} != set(PRINCIPAL_MODELS)
        or set(model_versions) != set(PRINCIPAL_MODELS)
    ):
        raise LedgerLifecycleError(
            "Prospective issuance requires exactly the three principal methods"
        )
    if (
        forecast.origin_date != latest.trading_date
        or forecast.forecast_for != calendar.next_trading_day(latest.trading_date)
    ):
        raise LedgerLifecycleError(
            "Forecast origin/target does not align with latest raw data and PSE calendar"
        )
    inference_times = {item.inference_at for item in predictions}
    if len(inference_times) != 1:
        raise LedgerLifecycleError("Principal forecasts must share one issuance timestamp")
    created_at = inference_times.pop()
    issuances: list[ForecastIssued] = []
    for prediction in predictions:
        if (
            prediction.symbol != company.symbol
            or prediction.origin_date != forecast.origin_date
            or prediction.forecast_for != forecast.forecast_for
            or prediction.origin_close != latest.close
            or not math.isclose(
                prediction.predicted_close,
                prediction.origin_close + prediction.predicted_delta,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise LedgerLifecycleError("Principal forecast metadata is inconsistent")
        issuances.append(
            ForecastIssued.create(
                created_at=created_at,
                symbol=company.symbol,
                origin_date=forecast.origin_date,
                target_date=forecast.forecast_for,
                method=prediction.model,
                model_version=model_versions[prediction.model],
                prediction=prediction.predicted_close,
                production_run_id=production_run_id,
                source_commit=source_commit,
            )
        )
    issuances.append(
        ForecastIssued.create(
            created_at=created_at,
            symbol=company.symbol,
            origin_date=forecast.origin_date,
            target_date=forecast.forecast_for,
            method=ModelId.NAIVE,
            model_version=NAIVE_MODEL_VERSION,
            prediction=latest.close,
            production_run_id=production_run_id,
            source_commit=source_commit,
        )
    )
    results = ledger.append_issuances(issuances)
    LOGGER.info(
        "Prospective forecasts issued symbol=%s target=%s appended=%d",
        company.symbol,
        forecast.forecast_for,
        sum(result.appended for result in results),
    )
    return results
