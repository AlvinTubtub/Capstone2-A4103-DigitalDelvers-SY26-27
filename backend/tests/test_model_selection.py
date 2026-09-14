"""Focused selection and scale-independent cross-company reporting tests."""

import statistics
import warnings

import pytest

from config.model_config import ModelId
from src.evaluation.metrics import EvaluationMetrics, compute_evaluation_metrics
from src.evaluation.model_selection import (
    CROSS_COMPANY_TIE_POLICY,
    RMSE_TIE_POLICY,
    ModelSelectionError,
    PrincipalsUnderperformNaiveWarning,
    rank_evaluated_methods,
    rank_principal_models,
    select_company_models,
    summarize_cross_company_metrics,
)


def metric(rmse: float, *, mase: float | None = None, r2: float = 0.0) -> EvaluationMetrics:
    return EvaluationMetrics(
        rmse=rmse,
        mae=rmse,
        mase=rmse if mase is None else mase,
        r2=r2,
        observations=10,
    )


def metrics(
    lir: float,
    arima: float,
    lstm: float,
    naive: float,
    *,
    mase: tuple[float, float, float, float] | None = None,
) -> dict[ModelId, EvaluationMetrics]:
    mase_values = mase or (lir, arima, lstm, naive)
    return {
        ModelId.LAG_REGRESSION: metric(lir, mase=mase_values[0]),
        ModelId.ARIMA: metric(arima, mase=mase_values[1]),
        ModelId.LSTM: metric(lstm, mase=mase_values[2]),
        ModelId.NAIVE: metric(naive, mase=mase_values[3]),
    }


def test_principal_and_evaluated_winners_are_distinct_conclusions() -> None:
    source = metrics(lir=2.0, arima=1.0, lstm=3.0, naive=0.5)

    with pytest.warns(PrincipalsUnderperformNaiveWarning):
        selection = select_company_models(source, symbol="BPI")

    assert selection.best_principal_model is ModelId.ARIMA
    assert selection.best_evaluated_method is ModelId.NAIVE
    assert selection.best_principal_beats_naive is False
    assert selection.all_principals_worse_than_naive is True


def test_all_principals_lose_to_naive_emits_clear_warning() -> None:
    with pytest.warns(
        PrincipalsUnderperformNaiveWarning,
        match="All three principal models.*Naive benchmark.*GLO",
    ):
        selection = select_company_models(
            metrics(lir=2.0, arima=3.0, lstm=4.0, naive=1.0),
            symbol="GLO",
        )

    assert selection.as_dict()["all_principals_worse_than_naive"] is True
    assert selection.as_dict()["best_principal_beats_naive"] is False


def test_exact_rmse_ties_use_documented_canonical_order() -> None:
    source = metrics(lir=1.0, arima=1.0, lstm=1.0, naive=1.0)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        selection = select_company_models(source)

    assert not any(
        isinstance(item.message, PrincipalsUnderperformNaiveWarning) for item in caught
    )
    assert tuple(
        item.model for item in selection.principal_ranking.ranked_models
    ) == (ModelId.LAG_REGRESSION, ModelId.ARIMA, ModelId.LSTM)
    assert tuple(
        item.model for item in selection.evaluated_ranking.ranked_models
    ) == (
        ModelId.LAG_REGRESSION,
        ModelId.ARIMA,
        ModelId.LSTM,
        ModelId.NAIVE,
    )
    assert selection.best_principal_beats_naive is False
    assert selection.principal_ranking.as_dict()["tie_policy"] == RMSE_TIE_POLICY


def test_cross_company_result_never_uses_mean_raw_peso_rmse_as_winner() -> None:
    source = {
        "A": metrics(1.0, 2.0, 3.0, 4.0, mase=(0.5, 1.0, 1.5, 2.0)),
        "B": metrics(1.0, 2.0, 3.0, 4.0, mase=(0.5, 1.0, 1.5, 2.0)),
        "C": metrics(
            1_000.0,
            100.0,
            200.0,
            300.0,
            mase=(4.0, 0.4, 0.8, 1.2),
        ),
    }
    mean_peso_rmse = {
        model: statistics.fmean(company[model].rmse for company in source.values())
        for model in ModelId
    }

    summary = summarize_cross_company_metrics(source)

    assert min(mean_peso_rmse, key=mean_peso_rmse.get) is ModelId.ARIMA
    assert summary.best_method is ModelId.LAG_REGRESSION
    assert summary.for_model(ModelId.LAG_REGRESSION).median_rmse_rank == 1.0
    assert summary.for_model(ModelId.LAG_REGRESSION).median_mase == 0.5


def test_cross_company_summary_reports_median_ranks_wins_and_naive_counts() -> None:
    source = {
        "A": metrics(1.0, 2.0, 3.0, 4.0, mase=(0.4, 0.8, 1.2, 1.6)),
        "B": metrics(1.0, 2.0, 3.0, 4.0, mase=(0.5, 0.9, 1.3, 1.7)),
        "C": metrics(2.0, 1.0, 3.0, 4.0, mase=(0.7, 0.3, 1.1, 1.5)),
    }

    summary = summarize_cross_company_metrics(source)
    lir = summary.for_model(ModelId.LAG_REGRESSION)
    arima = summary.for_model(ModelId.ARIMA)
    naive = summary.for_model(ModelId.NAIVE)

    assert lir.median_mase == 0.5
    assert lir.median_rmse_rank == 1.0
    assert lir.principal_win_count == 2
    assert lir.evaluated_win_count == 2
    assert lir.beats_naive_count == 3
    assert arima.principal_win_count == 1
    assert naive.principal_win_count == 0
    assert naive.beats_naive_count == 0
    assert summary.as_dict()["tie_policy"] == CROSS_COMPANY_TIE_POLICY


def test_cross_company_rmse_ties_receive_average_ranks() -> None:
    summary = summarize_cross_company_metrics(
        {"ALI": metrics(1.0, 1.0, 1.0, 1.0, mase=(1.0, 1.0, 1.0, 1.0))}
    )

    assert all(method.median_rmse_rank == 2.5 for method in summary.methods)
    assert summary.best_method is ModelId.LAG_REGRESSION


def test_negative_r2_is_preserved_as_supplementary_metric() -> None:
    result = compute_evaluation_metrics(
        actual_closes=(1.0, 2.0, 3.0),
        predicted_closes=(10.0, 10.0, 10.0),
        mase_denominator=1.0,
    )

    assert result.r2 < 0.0
    assert result.as_dict()["r2"] == result.r2


def test_r2_cannot_control_company_or_cross_company_selection() -> None:
    source = {
        ModelId.LAG_REGRESSION: metric(1.0, mase=0.5, r2=-100.0),
        ModelId.ARIMA: metric(2.0, mase=1.0, r2=0.99),
        ModelId.LSTM: metric(3.0, mase=1.5, r2=0.999),
        ModelId.NAIVE: metric(4.0, mase=2.0, r2=1.0),
    }

    assert rank_principal_models(source).best_model is ModelId.LAG_REGRESSION
    assert rank_evaluated_methods(source).best_model is ModelId.LAG_REGRESSION
    assert summarize_cross_company_metrics({"ALI": source}).best_method is (
        ModelId.LAG_REGRESSION
    )
    with pytest.raises(ModelSelectionError, match="criterion must be rmse"):
        rank_principal_models(source, criterion="r2")
    with pytest.raises(ModelSelectionError, match="criterion must be rmse"):
        rank_evaluated_methods(source, criterion="r2")
