"""Resolved prospective-ledger to frontend-history bridge tests."""

from datetime import date, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from config.companies import COMPANIES
from config.model_config import ModelId
from config.ledger_config import DEFAULT_FORECAST_LEDGER_PATH
from src.data.loader import load_company_history
from src.export.production_history import (
    DEFAULT_POST_FORMAL_BACKFILL_PATH,
    DISPLAY_HISTORY_MODELS,
    POST_FORMAL_BACKFILL_SOURCE,
    ProductionHistoryPoint,
    ProductionModelEvidence,
    ProductionHistoryError,
    REQUIRED_PRODUCTION_MODELS,
    build_post_formal_backfill_document,
    combine_post_formal_history,
    load_post_formal_backfill,
    load_resolved_production_history,
    reconstruct_post_formal_backfill,
    select_resolved_production_history,
)
from src.data.calendar import PSETradingCalendar
from src.data.validator import OhlcvRecord
from src.inference.next_day import CompanyNextDayForecast, NextDayPrediction
from src.ledger.materializer import materialize_events
from src.ledger.schema import (
    NAIVE_MODEL_VERSION,
    ForecastIssued,
    ForecastOutcomeObserved,
)
from src.ledger.store import ForecastLedger


MANILA = ZoneInfo("Asia/Manila")
FORMAL_CUTOFF = date(2026, 9, 11)


def issuance(
    method: ModelId,
    *,
    target_date: date,
    prediction: float,
    symbol: str = "ALI",
    origin_date: date | None = None,
) -> ForecastIssued:
    origin = origin_date or date.fromordinal(target_date.toordinal() - 1)
    return ForecastIssued.create(
        created_at=datetime.combine(target_date, datetime.min.time(), MANILA),
        symbol=symbol,
        origin_date=origin,
        target_date=target_date,
        method=method,
        model_version=(
            NAIVE_MODEL_VERSION if method is ModelId.NAIVE else f"model-{method.value}-v1"
        ),
        prediction=prediction,
        production_run_id="run-123",
        source_commit="a" * 40,
    )


def resolved_events(
    target_date: date,
    *,
    actual_close: float = 100.0,
    methods: tuple[ModelId, ...] = DISPLAY_HISTORY_MODELS,
) -> tuple[ForecastIssued | ForecastOutcomeObserved, ...]:
    events: list[ForecastIssued | ForecastOutcomeObserved] = []
    for index, method in enumerate(methods, start=1):
        issued = issuance(
            method,
            target_date=target_date,
            prediction=actual_close + index,
        )
        events.extend(
            (
                issued,
                ForecastOutcomeObserved.create(
                    issued,
                    observed_at=datetime.combine(
                        target_date, datetime.max.time(), MANILA
                    ),
                    actual_close=actual_close,
                ),
            )
        )
    return tuple(events)


def test_only_complete_resolved_post_formal_dates_are_selected() -> None:
    pending = tuple(
        issuance(model, target_date=date(2026, 9, 16), prediction=101.0)
        for model in DISPLAY_HISTORY_MODELS
    )
    events = (
        *resolved_events(date(2026, 9, 18), actual_close=104.0),
        *resolved_events(date(2026, 9, 10), actual_close=99.0),
        *pending,
        *resolved_events(
            date(2026, 9, 17),
            actual_close=103.0,
            methods=REQUIRED_PRODUCTION_MODELS[:2],
        ),
        *resolved_events(date(2026, 9, 15), actual_close=102.0),
    )

    selected = select_resolved_production_history(
        materialize_events(tuple(events)),
        formal_cutoffs={"ALI": FORMAL_CUTOFF},
    )

    assert [point.target_date for point in selected["ALI"]] == [
        date(2026, 9, 15),
        date(2026, 9, 18),
    ]
    assert all(point.source == "prospective" for point in selected["ALI"])
    assert all(
        tuple(evidence.method for evidence in point.models)
        == DISPLAY_HISTORY_MODELS
        for point in selected["ALI"]
    )
    assert selected["ALI"][0].evidence_for(ModelId.LAG_REGRESSION).error == 1.0


def test_mismatched_actual_close_across_methods_is_rejected() -> None:
    events: list[ForecastIssued | ForecastOutcomeObserved] = []
    target = date(2026, 9, 15)
    for index, model in enumerate(DISPLAY_HISTORY_MODELS):
        issued = issuance(model, target_date=target, prediction=105.0 + index)
        events.extend(
            (
                issued,
                ForecastOutcomeObserved.create(
                    issued,
                    observed_at=datetime(2026, 9, 15, 17, 0, tzinfo=MANILA),
                    actual_close=100.0 + index,
                ),
            )
        )

    with pytest.raises(ProductionHistoryError, match="actual Close differs"):
        select_resolved_production_history(
            materialize_events(tuple(events)),
            formal_cutoffs={"ALI": FORMAL_CUTOFF},
        )


def test_duplicate_method_for_one_target_date_is_rejected() -> None:
    events = list(resolved_events(date(2026, 9, 15)))
    duplicate = issuance(
        ModelId.LAG_REGRESSION,
        target_date=date(2026, 9, 15),
        origin_date=date(2026, 9, 13),
        prediction=101.0,
    )
    events.extend(
        (
            duplicate,
            ForecastOutcomeObserved.create(
                duplicate,
                observed_at=datetime(2026, 9, 15, 17, 0, tzinfo=MANILA),
                actual_close=100.0,
            ),
        )
    )

    with pytest.raises(ProductionHistoryError, match="Duplicate production method"):
        select_resolved_production_history(
            materialize_events(tuple(events)),
            formal_cutoffs={"ALI": FORMAL_CUTOFF},
        )


def test_repeated_ledger_exports_are_deterministic_and_read_only(
    tmp_path: Path,
) -> None:
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    events = resolved_events(date(2026, 9, 15))
    ledger.append_issuances(tuple(event for event in events if isinstance(event, ForecastIssued)))
    ledger.append_outcomes(
        tuple(event for event in events if isinstance(event, ForecastOutcomeObserved))
    )
    before = ledger.path.read_bytes()

    first = load_resolved_production_history(
        formal_cutoffs={"ALI": FORMAL_CUTOFF},
        ledger_path=ledger.path,
    )
    second = load_resolved_production_history(
        formal_cutoffs={"ALI": FORMAL_CUTOFF},
        ledger_path=ledger.path,
    )

    assert first == second
    assert ledger.path.read_bytes() == before


def test_repository_ledger_has_no_sep14_backfill_and_sep15_is_resolved() -> None:
    snapshot = ForecastLedger(DEFAULT_FORECAST_LEDGER_PATH).read()

    assert not any(
        record.issuance.target_date == date(2026, 9, 14)
        for record in snapshot.records
    )
    sep15 = tuple(
        record
        for record in snapshot.resolved
        if record.issuance.target_date == date(2026, 9, 15)
    )
    assert len(sep15) == 60
    assert {record.issuance.symbol for record in sep15} == {
        "ALI", "APX", "BPI", "GLO", "ICT", "JFC", "MBT", "MEG", "MER",
        "NIKL", "PGOLD", "SCC", "SECB", "SHLPH", "SMPH",
    }


def test_repository_backfill_has_one_sep14_point_for_every_company() -> None:
    symbols = tuple(company.symbol for company in COMPANIES)
    history = load_post_formal_backfill(
        formal_cutoffs={symbol: FORMAL_CUTOFF for symbol in symbols},
        records_by_symbol={symbol: load_company_history(symbol) for symbol in symbols},
        path=DEFAULT_POST_FORMAL_BACKFILL_PATH,
    )

    assert set(history) == set(symbols)
    assert all(len(history[symbol]) == 1 for symbol in symbols)
    assert all(
        history[symbol][0].origin_date == FORMAL_CUTOFF
        and history[symbol][0].target_date == date(2026, 9, 14)
        and history[symbol][0].source == "post_formal_backfill"
        and tuple(item.method for item in history[symbol][0].models)
        == DISPLAY_HISTORY_MODELS
        and all(item.forecast_id is None for item in history[symbol][0].models)
        for symbol in symbols
    )


def raw_record(day: date, close: float) -> OhlcvRecord:
    return OhlcvRecord(
        trading_date=day,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1_000.0,
    )


def backfill_point(symbol: str = "ALI") -> ProductionHistoryPoint:
    actual = 101.0
    return ProductionHistoryPoint(
        symbol=symbol,
        origin_date=FORMAL_CUTOFF,
        target_date=date(2026, 9, 14),
        actual_close=actual,
        source=POST_FORMAL_BACKFILL_SOURCE,
        models=tuple(
            ProductionModelEvidence(
                method=model,
                prediction=100.0 if model is ModelId.NAIVE else 100.0 + index,
                error=(100.0 if model is ModelId.NAIVE else 100.0 + index) - actual,
                model_version=(
                    "naive-origin-close-v1"
                    if model is ModelId.NAIVE
                    else f"backend-from-scratch-v1:{model.value[0] * 64}"
                ),
                artifact_sha256=(
                    None
                    if model is ModelId.NAIVE
                    else {
                        ModelId.LAG_REGRESSION: "a",
                        ModelId.ARIMA: "b",
                        ModelId.LSTM: "c",
                    }[model]
                    * 64
                ),
                artifact_created_at=(
                    None
                    if model is ModelId.NAIVE
                    else "2026-09-14T18:00:00+08:00"
                ),
                artifact_trained_through=FORMAL_CUTOFF,
            )
            for index, model in enumerate(DISPLAY_HISTORY_MODELS)
        ),
    )


def test_backfill_document_round_trip_validates_raw_actual_and_has_no_ledger_id(
    tmp_path: Path,
) -> None:
    point = backfill_point()
    document = build_post_formal_backfill_document(
        (point,),
        reconstructed_at=datetime(2026, 9, 15, 20, 0, tzinfo=MANILA),
    )
    path = tmp_path / "backfill.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    history = (
        raw_record(FORMAL_CUTOFF, 100.0),
        raw_record(date(2026, 9, 14), 101.0),
    )

    loaded = load_post_formal_backfill(
        formal_cutoffs={"ALI": FORMAL_CUTOFF},
        records_by_symbol={"ALI": history},
        path=path,
    )["ALI"][0]

    assert loaded.source == "post_formal_backfill"
    assert loaded.origin_date == FORMAL_CUTOFF
    assert loaded.target_date == date(2026, 9, 14)
    assert loaded.actual_close == 101.0
    assert all(evidence.forecast_id is None for evidence in loaded.models)
    assert all(
        evidence.error == pytest.approx(evidence.prediction - loaded.actual_close)
        for evidence in loaded.models
    )


def test_backfill_reconstruction_uses_only_cutoff_history_and_persisted_inference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    records = (
        raw_record(FORMAL_CUTOFF - timedelta(days=1), 99.0),
        raw_record(FORMAL_CUTOFF, 100.0),
        raw_record(date(2026, 9, 14), 101.0),
        raw_record(date(2026, 9, 15), 102.0),
    )
    loaded_models: list[ModelId] = []

    def load_model(symbol, model, *, artifacts_root):
        loaded_models.append(model)
        return SimpleNamespace(
            model_family=model,
            metadata=SimpleNamespace(
                symbol=symbol,
                trained_through=FORMAL_CUTOFF,
                data_row_count=2,
                implementation_version="backend-from-scratch-v1",
                artifact_sha256={
                    ModelId.LAG_REGRESSION: "a",
                    ModelId.ARIMA: "b",
                    ModelId.LSTM: "c",
                }[model]
                * 64,
                created_at=datetime(2026, 9, 14, 18, 0, tzinfo=MANILA),
            ),
        )

    def infer(symbol, history, artifacts, *, calendar):
        assert [record.trading_date for record in history] == [
            FORMAL_CUTOFF - timedelta(days=1),
            FORMAL_CUTOFF,
        ]
        assert tuple(artifact.model_family for artifact in artifacts) == REQUIRED_PRODUCTION_MODELS
        predictions = tuple(
            NextDayPrediction(
                symbol=symbol,
                model=model,
                origin_date=FORMAL_CUTOFF,
                forecast_for=date(2026, 9, 14),
                origin_close=100.0,
                predicted_delta=float(index),
                predicted_close=100.0 + index,
                inference_at=datetime(2026, 9, 15, 20, 0, tzinfo=MANILA),
            )
            for index, model in enumerate(REQUIRED_PRODUCTION_MODELS, start=1)
        )
        return CompanyNextDayForecast(
            symbol=symbol,
            origin_date=FORMAL_CUTOFF,
            forecast_for=date(2026, 9, 14),
            predictions=predictions,
        )

    monkeypatch.setattr("src.export.production_history.load_production_model", load_model)
    monkeypatch.setattr("src.export.production_history.predict_next_day_with_artifacts", infer)

    point = reconstruct_post_formal_backfill(
        symbol="ALI",
        records=records,
        formal_cutoff=FORMAL_CUTOFF,
        target_date=date(2026, 9, 14),
        calendar=PSETradingCalendar(),
        artifacts_root=tmp_path,
    )

    assert loaded_models == list(REQUIRED_PRODUCTION_MODELS)
    assert point.actual_close == 101.0
    assert point.evidence_for(ModelId.NAIVE).prediction == 100.0
    assert point.evidence_for(ModelId.NAIVE).error == -1.0


def test_bridge_and_prospective_history_are_unique_and_chronological() -> None:
    bridge = backfill_point()
    prospective = ProductionHistoryPoint(
        symbol="ALI",
        origin_date=date(2026, 9, 14),
        target_date=date(2026, 9, 15),
        actual_close=102.0,
        models=bridge.models,
    )

    combined = combine_post_formal_history(
        {"ALI": (prospective,)},
        {"ALI": (bridge,)},
    )

    assert [point.target_date for point in combined["ALI"]] == [
        date(2026, 9, 14),
        date(2026, 9, 15),
    ]
    with pytest.raises(ProductionHistoryError, match="Duplicate post-formal"):
        combine_post_formal_history({"ALI": (bridge,)}, {"ALI": (bridge,)})
