"""Unified OOS alignment, metric, benchmark, ranking, and leakage tests."""

from datetime import date, timedelta
import json
import math
from types import SimpleNamespace

import pytest

from config.model_config import ModelConfig, ModelId
from src.data.split import build_company_evaluation_plan
from src.data.validator import OhlcvRecord
from src.evaluation.backtest import (
    BacktestAlignmentError,
    canonical_records_from_arrays,
    naive_prediction_records,
)
from src.evaluation.evaluator import (
    ModelPredictionOutput,
    development_close_series,
    evaluate_company,
    evaluate_prediction_outputs,
)
from src.evaluation.metrics import (
    compute_evaluation_metrics,
    serialize_metrics,
)


def synthetic_records(count: int = 36) -> tuple[OhlcvRecord, ...]:
    start = date(2025, 1, 2)
    closes = [100.0]
    for index in range(1, count):
        closes.append(closes[-1] + (0.5 if index % 3 else -0.25))
    return tuple(
        OhlcvRecord(
            trading_date=start + timedelta(days=index),
            open=close - 0.1,
            high=close + 0.6,
            low=close - 0.6,
            close=close,
            volume=10_000.0 + index,
        )
        for index, close in enumerate(closes)
    )


def prediction_outputs(plan) -> tuple[ModelPredictionOutput, ...]:
    dates = plan.evaluation_target_dates
    actual = tuple(pair.actual_close for pair in plan.evaluation_pairs)
    return (
        ModelPredictionOutput(
            symbol=plan.symbol,
            model=ModelId.LAG_REGRESSION,
            target_dates=dates,
            actual_closes=actual,
            predicted_closes=tuple(value + 0.1 for value in actual),
        ),
        ModelPredictionOutput(
            symbol=plan.symbol,
            model=ModelId.ARIMA,
            target_dates=tuple(reversed(dates)),
            actual_closes=tuple(reversed(actual)),
            predicted_closes=tuple(value + 0.2 for value in reversed(actual)),
        ),
        ModelPredictionOutput(
            symbol=plan.symbol,
            model=ModelId.LSTM,
            target_dates=dates,
            actual_closes=actual,
            predicted_closes=tuple(value + 0.3 for value in actual),
        ),
    )


def test_metric_correctness() -> None:
    metrics = compute_evaluation_metrics(
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 4.0],
        mase_denominator=2.0,
    )

    assert metrics.rmse == pytest.approx(math.sqrt(1.0 / 3.0))
    assert metrics.mae == pytest.approx(1.0 / 3.0)
    assert metrics.mase == pytest.approx(1.0 / 6.0)
    assert metrics.r2 == pytest.approx(0.5)
    assert metrics.observations == 3


def test_full_precision_metric_serialization() -> None:
    metrics = compute_evaluation_metrics(
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 4.0],
        mase_denominator=2.0,
    )

    encoded = serialize_metrics(metrics)
    decoded = json.loads(encoded)

    assert decoded["rmse"] == metrics.rmse
    assert decoded["mae"] == metrics.mae
    assert "0.5773502691896257" in encoded


def test_one_canonical_mase_denominator_is_used_for_every_model() -> None:
    records = synthetic_records()
    plan = build_company_evaluation_plan(
        "ALI",
        records,
        model_config=ModelConfig(evaluation_proportion=0.2),
    )
    evaluation = evaluate_prediction_outputs(plan, prediction_outputs(plan))
    expected_development_closes = tuple(
        record.close for record in records[: len(plan.development_pairs) + 1]
    )
    expected = sum(
        abs(current - previous)
        for previous, current in zip(
            expected_development_closes,
            expected_development_closes[1:],
        )
    ) / (len(expected_development_closes) - 1)

    assert development_close_series(plan) == expected_development_closes
    assert evaluation.mase_denominator == expected
    for model in ModelId.LAG_REGRESSION, ModelId.ARIMA, ModelId.LSTM, ModelId.NAIVE:
        metrics = evaluation.metrics_for(model)
        assert metrics.mase == metrics.mae / expected


def test_naive_benchmark_is_date_indexed_origin_close() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    records = naive_prediction_records(plan)

    assert tuple(record.target_date for record in records) == plan.evaluation_target_dates
    assert tuple(record.predicted_close for record in records) == tuple(
        pair.origin_close for pair in plan.evaluation_pairs
    )
    assert tuple(record.actual_close for record in records) == tuple(
        pair.actual_close for pair in plan.evaluation_pairs
    )


def test_every_model_has_the_identical_aligned_target_date_set() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    evaluation = evaluate_prediction_outputs(plan, prediction_outputs(plan))

    for model in ModelId.LAG_REGRESSION, ModelId.ARIMA, ModelId.LSTM, ModelId.NAIVE:
        records = evaluation.backtest.records_for(model)
        assert tuple(record.target_date for record in records) == (
            plan.evaluation_target_dates
        )
    assert evaluation.backtest.records_for(ModelId.ARIMA)[0].target_date == (
        plan.evaluation_target_dates[0]
    )


def test_canonical_prediction_record_contains_required_fields_and_error_sign() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    output = prediction_outputs(plan)[0]
    records = canonical_records_from_arrays(
        plan,
        model=output.model,
        target_dates=output.target_dates,
        actual_closes=output.actual_closes,
        predicted_closes=output.predicted_closes,
    )
    first = records[0]

    assert set(first.as_dict()) == {
        "symbol",
        "model",
        "origin_date",
        "target_date",
        "origin_close",
        "actual_close",
        "predicted_close",
        "error",
    }
    assert first.error == first.predicted_close - first.actual_close


def test_missing_principal_model_fails_evaluation() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())

    with pytest.raises(BacktestAlignmentError, match="missing=.*lstm"):
        evaluate_prediction_outputs(plan, prediction_outputs(plan)[:-1])


def test_missing_model_date_fails_evaluation() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    outputs = list(prediction_outputs(plan))
    lstm = outputs[-1]
    outputs[-1] = ModelPredictionOutput(
        symbol=lstm.symbol,
        model=lstm.model,
        target_dates=lstm.target_dates[:-1],
        actual_closes=lstm.actual_closes[:-1],
        predicted_closes=lstm.predicted_closes[:-1],
    )

    with pytest.raises(BacktestAlignmentError, match="target-date mismatch"):
        evaluate_prediction_outputs(plan, outputs)


def test_in_sample_date_cannot_enter_backtest() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    dates = list(plan.evaluation_target_dates)
    dates[0] = plan.development_target_dates[-1]
    actual = tuple(pair.actual_close for pair in plan.evaluation_pairs)

    with pytest.raises(BacktestAlignmentError, match="target-date mismatch"):
        canonical_records_from_arrays(
            plan,
            model=ModelId.LAG_REGRESSION,
            target_dates=dates,
            actual_closes=actual,
            predicted_closes=actual,
        )


def test_backtest_payload_contains_only_oos_records() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    evaluation = evaluate_prediction_outputs(plan, prediction_outputs(plan))
    payload = evaluation.backtest.as_dict()

    assert payload["source"] == "chronological_out_of_sample_evaluation"
    assert all(
        record.target_date > plan.development_target_dates[-1]
        for record in evaluation.backtest.all_records
    )
    assert len(payload["records"]) == 4 * len(plan.evaluation_pairs)


def test_default_principal_ranking_uses_lowest_evaluation_rmse() -> None:
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    evaluation = evaluate_prediction_outputs(plan, prediction_outputs(plan))

    assert evaluation.principal_ranking.criterion == "rmse"
    assert evaluation.principal_ranking.best_model is ModelId.LAG_REGRESSION
    assert ModelId.NAIVE not in {
        ranked.model for ranked in evaluation.principal_ranking.ranked_models
    }
    assert evaluation.evaluated_ranking.criterion == "rmse"
    assert evaluation.evaluated_ranking.best_model is ModelId.LAG_REGRESSION
    assert evaluation.best_principal_beats_naive is True
    payload = evaluation.as_dict()
    assert payload["best_principal_model"] == "lag_reg"
    assert payload["best_evaluated_method"] == "lag_reg"
    assert payload["best_principal_beats_naive"] is True
    assert payload["all_principals_worse_than_naive"] is False


def test_company_evaluator_builds_dynamic_split_and_only_uses_oos_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = synthetic_records(31)
    config = ModelConfig(evaluation_proportion=0.2)
    observed_plan_lengths: list[tuple[int, int]] = []

    def result_for(plan, offset):
        observed_plan_lengths.append(
            (len(plan.development_pairs), len(plan.evaluation_pairs))
        )
        actual = tuple(pair.actual_close for pair in plan.evaluation_pairs)
        return SimpleNamespace(
            symbol=plan.symbol,
            target_dates=plan.evaluation_target_dates,
            actual_closes=actual,
            predicted_closes=tuple(value + offset for value in actual),
        )

    monkeypatch.setattr(
        "src.evaluation.evaluator.build_regression_dataset",
        lambda records, feature_config: object(),
    )
    monkeypatch.setattr(
        "src.evaluation.evaluator.load_company_history",
        lambda symbol: records,
    )
    monkeypatch.setattr(
        "src.evaluation.evaluator.train_lir_for_evaluation",
        lambda dataset, plan, *, config: result_for(plan, 0.1),
    )
    monkeypatch.setattr(
        "src.evaluation.evaluator.train_arima_for_evaluation",
        lambda records, plan, *, config: result_for(plan, 0.2),
    )
    monkeypatch.setattr(
        "src.evaluation.evaluator.train_lstm_for_evaluation",
        lambda records, plan, *, config: result_for(plan, 0.3),
    )

    evaluation = evaluate_company("ALI", model_config=config)

    assert len(evaluation.plan.development_pairs) == 24
    assert len(evaluation.plan.evaluation_pairs) == 6
    assert observed_plan_lengths == [(24, 6), (24, 6), (24, 6)]
    assert evaluation.backtest.target_dates == evaluation.plan.evaluation_target_dates
