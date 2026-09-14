"""Prospective ledger immutability, materialization, and EOD lifecycle tests."""

from datetime import date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from config.model_config import ModelId
from src.data.calendar import PSETradingCalendar
from src.data.validator import OhlcvRecord
from src.inference.next_day import CompanyNextDayForecast, NextDayPrediction
from src.ledger.lifecycle import (
    LedgerLifecycleError,
    issue_company_forecasts,
    resolve_pending_outcomes,
)
from src.ledger.schema import (
    ForecastIssued,
    ForecastOutcomeObserved,
    LedgerValidationError,
    NAIVE_MODEL_VERSION,
)
from src.ledger.store import ForecastLedger


MANILA = ZoneInfo("Asia/Manila")
CREATED = datetime(2026, 1, 2, 16, 0, tzinfo=MANILA)
OBSERVED = datetime(2026, 1, 5, 16, 0, tzinfo=MANILA)


def issuance(
    *,
    prediction: float = 101.0,
    method: ModelId = ModelId.LAG_REGRESSION,
    created_at: datetime = CREATED,
) -> ForecastIssued:
    return ForecastIssued.create(
        created_at=created_at,
        symbol="ALI",
        origin_date=date(2026, 1, 2),
        target_date=date(2026, 1, 5),
        method=method,
        model_version="backend-from-scratch-v1:abc123",
        prediction=prediction,
        production_run_id="98765",
        source_commit="a" * 40,
    )


def raw_record(trading_date: date, close: float) -> OhlcvRecord:
    return OhlcvRecord(
        trading_date=trading_date,
        open=close - 0.5,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=10_000.0,
    )


def company_forecast(*, target: date = date(2026, 1, 5)) -> CompanyNextDayForecast:
    predictions = tuple(
        NextDayPrediction(
            symbol="ALI",
            model=model,
            origin_date=date(2026, 1, 2),
            forecast_for=target,
            origin_close=100.0,
            predicted_delta=delta,
            predicted_close=100.0 + delta,
            inference_at=CREATED,
        )
        for model, delta in (
            (ModelId.LAG_REGRESSION, 1.0),
            (ModelId.ARIMA, 2.0),
            (ModelId.LSTM, 3.0),
        )
    )
    return CompanyNextDayForecast("ALI", date(2026, 1, 2), target, predictions)


def test_forecast_issuance_is_materialized_pending_with_model_version(
    tmp_path: Path,
) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    event = issuance()

    result = ledger.append_issued(event)
    snapshot = ledger.read()

    assert result.appended
    assert len(snapshot.pending) == 1
    assert not snapshot.resolved
    assert snapshot.pending[0].issuance.model_version == event.model_version
    assert snapshot.pending[0].as_dict()["status"] == "pending"
    payload = json.loads(ledger.path.read_text(encoding="utf-8"))
    assert payload["event_type"] == "forecast_issued"


def test_exact_duplicate_is_idempotent_but_changed_prediction_is_rejected(
    tmp_path: Path,
) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    original = issuance()
    ledger.append_issued(original)
    retry = issuance(created_at=CREATED + timedelta(minutes=5))

    assert not ledger.append_issued(retry).appended
    assert len(ledger.path.read_text(encoding="utf-8").splitlines()) == 1
    with pytest.raises(LedgerValidationError, match="changed prediction"):
        ledger.append_issued(issuance(prediction=101.01))
    assert ledger.read().pending[0].issuance.prediction == 101.0


def test_outcome_requires_issuance_and_validates_derived_errors(tmp_path: Path) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    event = issuance(prediction=101.0)
    valid = ForecastOutcomeObserved.create(
        event,
        observed_at=OBSERVED,
        actual_close=99.5,
    )

    with pytest.raises(LedgerValidationError, match="without issuance"):
        ledger.append_outcome(valid)
    ledger.append_issued(event)
    malformed = ForecastOutcomeObserved(
        forecast_id=event.forecast_id,
        observed_at=OBSERVED,
        actual_close=99.5,
        error=0.0,
        absolute_error=0.0,
        squared_error=0.0,
    )
    with pytest.raises(LedgerValidationError, match="derived errors"):
        ledger.append_outcome(malformed)

    result = ledger.append_outcome(valid)
    resolved = ledger.read().resolved[0]
    assert result.appended
    assert resolved.outcome.error == pytest.approx(1.5)
    assert resolved.outcome.absolute_error == pytest.approx(1.5)
    assert resolved.outcome.squared_error == pytest.approx(2.25)
    assert resolved.as_dict()["status"] == "resolved"


def test_duplicate_outcome_is_deterministic_and_issuance_remains_immutable(
    tmp_path: Path,
) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    event = issuance()
    ledger.append_issued(event)
    first = ForecastOutcomeObserved.create(
        event, observed_at=OBSERVED, actual_close=100.0
    )
    ledger.append_outcome(first)
    retry = ForecastOutcomeObserved.create(
        event,
        observed_at=OBSERVED + timedelta(minutes=10),
        actual_close=100.0,
    )

    assert not ledger.append_outcome(retry).appended
    assert not ledger.append_issued(event).appended
    with pytest.raises(LedgerValidationError, match="Conflicting observed outcome"):
        ledger.append_outcome(
            ForecastOutcomeObserved.create(
                event,
                observed_at=OBSERVED + timedelta(minutes=20),
                actual_close=100.5,
            )
        )
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event_type"] for line in lines] == [
        "forecast_issued",
        "forecast_outcome_observed",
    ]


def test_company_issuance_adds_aligned_naive_forecast(tmp_path: Path) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    records = (raw_record(date(2026, 1, 2), 100.0),)
    versions = {
        model: f"version-{model.value}"
        for model in (
            ModelId.LAG_REGRESSION,
            ModelId.ARIMA,
            ModelId.LSTM,
        )
    }

    results = issue_company_forecasts(
        ledger,
        company_forecast(),
        records,
        model_versions=versions,
        calendar=PSETradingCalendar(frozenset()),
        production_run_id="98765",
        source_commit="a" * 40,
    )
    snapshot = ledger.read()

    assert len(results) == 4
    assert all(result.appended for result in results)
    assert {record.issuance.method for record in snapshot.pending} == set(ModelId)
    assert {record.issuance.target_date for record in snapshot.pending} == {
        date(2026, 1, 5)
    }
    naive = next(
        record for record in snapshot.pending
        if record.issuance.method is ModelId.NAIVE
    )
    assert naive.issuance.prediction == 100.0
    assert naive.issuance.model_version == NAIVE_MODEL_VERSION


def test_company_issuance_rejects_wrong_target_date(tmp_path: Path) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    versions = {
        model: f"version-{model.value}"
        for model in (ModelId.LAG_REGRESSION, ModelId.ARIMA, ModelId.LSTM)
    }
    with pytest.raises(LedgerLifecycleError, match="does not align"):
        issue_company_forecasts(
            ledger,
            company_forecast(target=date(2026, 1, 6)),
            (raw_record(date(2026, 1, 2), 100.0),),
            model_versions=versions,
            calendar=PSETradingCalendar(frozenset()),
        )


def test_eod_resolution_uses_exact_target_close_and_preserves_issued_event(
    tmp_path: Path,
) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    versions = {
        model: f"version-{model.value}"
        for model in (ModelId.LAG_REGRESSION, ModelId.ARIMA, ModelId.LSTM)
    }
    history = (raw_record(date(2026, 1, 2), 100.0),)
    issue_company_forecasts(
        ledger,
        company_forecast(),
        history,
        model_versions=versions,
        calendar=PSETradingCalendar(frozenset()),
    )
    issued_lines = ledger.path.read_text(encoding="utf-8").splitlines()

    results = resolve_pending_outcomes(
        ledger,
        {"ALI": history + (raw_record(date(2026, 1, 5), 104.0),)},
        observed_at=OBSERVED,
    )

    assert len(results) == 4
    assert all(result.appended for result in results)
    snapshot = ledger.read()
    assert not snapshot.pending
    assert len(snapshot.resolved) == 4
    assert all(record.outcome.actual_close == 104.0 for record in snapshot.resolved)
    assert ledger.path.read_text(encoding="utf-8").splitlines()[:4] == issued_lines
