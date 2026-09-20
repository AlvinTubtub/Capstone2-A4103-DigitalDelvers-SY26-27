"""Next-day movement diagnostics and frozen-origin validation tests."""

from datetime import date, timedelta
import json

import pytest

from config.model_config import ModelId
from src.evaluation.backtest import (
    BacktestData,
    CanonicalPrediction,
    REQUIRED_EVALUATION_MODELS,
)
from src.evaluation.change_diagnostics import (
    CHANGE_ZERO_TOLERANCE,
    ChangeDiagnosticError,
    archived_change_diagnostics,
    backtest_from_archived_holdout,
    compute_change_diagnostics,
    direction_class,
)


def make_backtest(
    *,
    origins: tuple[float, ...] = (100.0, 105.0, 100.0),
    actuals: tuple[float, ...] = (102.0, 103.0, 101.0),
) -> BacktestData:
    start = date(2026, 1, 5)
    dates = tuple(start + timedelta(days=index) for index in range(len(origins)))
    predicted_changes = {
        ModelId.LAG_REGRESSION: (1.0, -1.0, 2.0),
        ModelId.ARIMA: (0.5, -0.5, 1.0),
        ModelId.LSTM: (2.0, -2.0, 0.0),
        ModelId.NAIVE: (0.0, 0.0, 0.0),
    }
    grouped = []
    for model in REQUIRED_EVALUATION_MODELS:
        records = tuple(
            CanonicalPrediction.create(
                symbol="ALI",
                model=model,
                origin_date=target - timedelta(days=1),
                target_date=target,
                origin_close=origins[index],
                actual_close=actuals[index],
                predicted_close=origins[index] + predicted_changes[model][index],
            )
            for index, target in enumerate(dates)
        )
        grouped.append((model, records))
    return BacktestData(
        symbol="ALI",
        target_dates=dates,
        actual_closes=actuals,
        records_by_model=tuple(grouped),
    )


def by_model(backtest: BacktestData):
    return {item.model: item for item in compute_change_diagnostics(backtest)}


def test_changes_use_origin_close_not_consecutive_predictions() -> None:
    backtest = make_backtest()
    diagnostics = by_model(backtest)
    lir = diagnostics[ModelId.LAG_REGRESSION]

    assert lir.actual_changes == (2.0, -2.0, 1.0)
    assert lir.predicted_changes == (1.0, -1.0, 2.0)
    consecutive_prediction_differences = tuple(
        right.predicted_close - left.predicted_close
        for left, right in zip(
            backtest.records_for(ModelId.LAG_REGRESSION),
            backtest.records_for(ModelId.LAG_REGRESSION)[1:],
        )
    )
    assert lir.predicted_changes[1:] != consecutive_prediction_differences


def test_naive_change_rate_and_constant_correlation_are_explicit() -> None:
    naive = by_model(make_backtest())[ModelId.NAIVE]

    assert naive.predicted_changes == (0.0, 0.0, 0.0)
    assert naive.near_zero_prediction_rate == 1.0
    assert naive.correlation is None
    assert naive.correlation_status == "undefined_constant_prediction"


def test_all_models_share_dates_origins_and_actual_changes() -> None:
    diagnostics = compute_change_diagnostics(make_backtest())

    assert len(diagnostics) == 4
    assert len({item.target_dates for item in diagnostics}) == 1
    assert len({item.actual_changes for item in diagnostics}) == 1
    assert all(item.observation_count == 3 for item in diagnostics)


def test_direction_rule_includes_zero_matches_and_uses_one_tolerance() -> None:
    tolerance = CHANGE_ZERO_TOLERANCE
    assert direction_class(tolerance * 2.0) == 1
    assert direction_class(-tolerance * 2.0) == -1
    assert direction_class(tolerance) == 0
    assert direction_class(-tolerance) == 0

    backtest = make_backtest(
        origins=(100.0, 100.0, 100.0),
        actuals=(101.0, 99.0, 100.0),
    )
    lstm = by_model(backtest)[ModelId.LSTM]
    assert lstm.predicted_changes == (2.0, -2.0, 0.0)
    assert lstm.directional_accuracy == 1.0


def test_near_zero_tolerance_is_inclusive_and_serialization_is_finite() -> None:
    backtest = make_backtest()
    records = dict(backtest.records_by_model)
    tiny = (0.0, CHANGE_ZERO_TOLERANCE, CHANGE_ZERO_TOLERANCE * 2.0)
    records[ModelId.LAG_REGRESSION] = tuple(
        CanonicalPrediction.create(
            symbol=record.symbol,
            model=record.model,
            origin_date=record.origin_date,
            target_date=record.target_date,
            origin_close=record.origin_close,
            actual_close=record.actual_close,
            predicted_close=record.origin_close + tiny[index],
        )
        for index, record in enumerate(records[ModelId.LAG_REGRESSION])
    )
    modified = BacktestData(
        symbol=backtest.symbol,
        target_dates=backtest.target_dates,
        actual_closes=backtest.actual_closes,
        records_by_model=tuple(
            (model, records[model]) for model in REQUIRED_EVALUATION_MODELS
        ),
    )

    diagnostic = by_model(modified)[ModelId.LAG_REGRESSION]
    assert diagnostic.near_zero_prediction_rate == pytest.approx(2.0 / 3.0)
    json.dumps(diagnostic.as_dict(), allow_nan=False)


def test_zero_actual_variance_makes_correlation_and_amplitude_unavailable() -> None:
    diagnostic = by_model(
        make_backtest(
            origins=(100.0, 101.0, 102.0),
            actuals=(101.0, 102.0, 103.0),
        )
    )[ModelId.LAG_REGRESSION]

    assert diagnostic.actual_change_std == 0.0
    assert diagnostic.correlation is None
    assert diagnostic.correlation_status == "undefined_constant_actual"
    assert diagnostic.amplitude_ratio is None
    assert diagnostic.amplitude_ratio_status == "undefined_zero_actual_variance"


def write_raw(path) -> None:
    path.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-01-02,99,101,98,100,1000\n"
        "2026-01-05,100,103,99,102,1100\n"
        "2026-01-06,102,104,101,103,1200\n",
        encoding="utf-8",
    )


def archived_rows() -> list[dict[str, object]]:
    return [
        {
            "company": "ALI",
            "target_date": "2026-01-05",
            "actual_close": 102.0,
            "lir_prediction": 101.0,
            "arima_prediction": 100.5,
            "lstm_prediction": 102.0,
            "naive_prediction": 100.0,
        },
        {
            "company": "ALI",
            "target_date": "2026-01-06",
            "actual_close": 103.0,
            "lir_prediction": 103.0,
            "arima_prediction": 102.5,
            "lstm_prediction": 104.0,
            "naive_prediction": 102.0,
        },
    ]


def test_archived_origin_is_immediately_previous_raw_close(tmp_path) -> None:
    raw = tmp_path / "ALI.csv"
    write_raw(raw)
    backtest = backtest_from_archived_holdout("ALI", archived_rows(), raw)

    records = backtest.records_for(ModelId.LAG_REGRESSION)
    assert tuple(record.origin_date.isoformat() for record in records) == (
        "2026-01-02",
        "2026-01-05",
    )
    assert tuple(record.origin_close for record in records) == (100.0, 102.0)
    diagnostics = archived_change_diagnostics("ALI", archived_rows(), raw)
    assert all(item.observation_count == 2 for item in diagnostics)


def test_target_close_cannot_masquerade_as_archived_origin(tmp_path) -> None:
    raw = tmp_path / "ALI.csv"
    write_raw(raw)
    rows = archived_rows()
    rows[0]["naive_prediction"] = rows[0]["actual_close"]

    with pytest.raises(ChangeDiagnosticError, match="verified origin Close"):
        backtest_from_archived_holdout("ALI", rows, raw)


@pytest.mark.parametrize("defect", ("duplicate", "reversed", "misaligned_actual"))
def test_malformed_or_misaligned_backtests_fail_closed(defect: str) -> None:
    backtest = make_backtest()
    dates = backtest.target_dates
    actuals = backtest.actual_closes
    if defect == "duplicate":
        dates = (dates[0], dates[0], dates[2])
    elif defect == "reversed":
        dates = tuple(reversed(dates))
    else:
        actuals = (actuals[0] + 1.0, *actuals[1:])
    malformed = BacktestData(
        symbol=backtest.symbol,
        target_dates=dates,
        actual_closes=actuals,
        records_by_model=backtest.records_by_model,
    )

    with pytest.raises(ChangeDiagnosticError):
        compute_change_diagnostics(malformed)
