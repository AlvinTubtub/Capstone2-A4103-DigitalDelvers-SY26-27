"""Date alignment and evaluation-only statistical comparison tests."""

from datetime import date, timedelta
import json
import warnings

import numpy as np
import pytest
from scipy.stats import skew

from config.model_config import ModelId
from src.evaluation.backtest import BacktestAlignmentError, CanonicalPrediction
from src.evaluation.holdout import align_holdout_records
from src.evaluation.metrics import EvaluationMetrics
from src.evaluation.statistical_tests import (
    LossType,
    MODEL_PAIRS,
    automatic_hac_lag,
    compare_methods_across_companies,
    diebold_mariano_test,
    run_within_company_dm_tests,
)


def aligned_holdout(
    errors_by_model: dict[ModelId, np.ndarray],
    *,
    reverse_arima: bool = False,
):
    sample_size = len(next(iter(errors_by_model.values())))
    start = date(2026, 1, 2)
    dates = tuple(start + timedelta(days=index + 1) for index in range(sample_size))
    actual = np.linspace(100.0, 120.0, sample_size)
    records: dict[ModelId, tuple[CanonicalPrediction, ...]] = {}
    for model in ModelId:
        model_records = tuple(
            CanonicalPrediction.create(
                symbol="ALI",
                model=model,
                origin_date=target_date - timedelta(days=1),
                target_date=target_date,
                origin_close=float(actual[index] - 0.1),
                actual_close=float(actual[index]),
                predicted_close=float(actual[index] + errors_by_model[model][index]),
            )
            for index, target_date in enumerate(dates)
        )
        records[model] = (
            tuple(reversed(model_records))
            if reverse_arima and model is ModelId.ARIMA
            else model_records
        )
    return align_holdout_records("ALI", records), records


def varied_errors(sample_size: int = 80) -> dict[ModelId, np.ndarray]:
    random = np.random.default_rng(731)
    return {
        ModelId.LAG_REGRESSION: random.normal(0.0, 0.20, sample_size),
        ModelId.ARIMA: random.normal(0.0, 0.55, sample_size),
        ModelId.LSTM: random.normal(0.0, 0.95, sample_size),
        ModelId.NAIVE: random.normal(2.25, 0.80, sample_size),
    }


def metric(rmse: float, mase: float) -> EvaluationMetrics:
    return EvaluationMetrics(rmse, rmse, mase, -2.0, 40)


def cross_company_metrics(
    *,
    companies: int = 16,
    equal: bool = False,
    reverse_rmse: bool = False,
) -> dict[str, dict[ModelId, EvaluationMetrics]]:
    output: dict[str, dict[ModelId, EvaluationMetrics]] = {}
    for index in range(companies):
        offset = index / 1_000.0
        mase = (1.0, 1.0, 1.0, 1.0) if equal else (
            0.2 + offset,
            0.8 + offset,
            1.4 + offset,
            2.0 + offset,
        )
        rmse = (4.0, 3.0, 2.0, 1.0) if reverse_rmse else (1.0, 2.0, 3.0, 4.0)
        output[f"C{index:02d}"] = {
            model: metric(rmse[model_index], mase[model_index])
            for model_index, model in enumerate(ModelId)
        }
    return output


def test_holdout_is_date_joined_unique_and_chronological() -> None:
    holdout, _ = aligned_holdout(varied_errors(12), reverse_arima=True)

    assert holdout.target_dates == tuple(sorted(holdout.target_dates))
    assert len(set(holdout.target_dates)) == len(holdout.target_dates)
    assert set(holdout.rows[0].as_dict()) == {
        "company",
        "target_date",
        "actual_close",
        "lir_prediction",
        "arima_prediction",
        "lstm_prediction",
        "naive_prediction",
    }


def test_holdout_rejects_missing_naive_without_positional_truncation() -> None:
    _, records = aligned_holdout(varied_errors(12))
    records.pop(ModelId.NAIVE)

    with pytest.raises(BacktestAlignmentError, match="missing=.*naive"):
        align_holdout_records("ALI", records)


def test_holdout_rejects_duplicate_and_missing_model_dates() -> None:
    _, records = aligned_holdout(varied_errors(12))
    duplicate = dict(records)
    duplicate[ModelId.LSTM] = records[ModelId.LSTM] + (records[ModelId.LSTM][0],)
    with pytest.raises(BacktestAlignmentError, match="duplicate target dates"):
        align_holdout_records("ALI", duplicate)

    missing = dict(records)
    missing[ModelId.ARIMA] = records[ModelId.ARIMA][:-1]
    with pytest.raises(BacktestAlignmentError, match="target-date mismatch"):
        align_holdout_records("ALI", missing)


def test_dm_runs_all_six_pairs_for_both_loss_families() -> None:
    holdout, _ = aligned_holdout(varied_errors())

    results = run_within_company_dm_tests(holdout)

    assert len(results.squared_error) == 6
    assert len(results.absolute_error) == 6
    assert {(item.model_1, item.model_2) for item in results.squared_error} == set(
        MODEL_PAIRS
    )
    assert {item.loss_type for item in results.all_tests} == set(LossType)
    assert all(item.sample_size == len(holdout.rows) for item in results.all_tests)


def test_hac_lag_and_hln_policies_are_deterministic() -> None:
    holdout, _ = aligned_holdout(varied_errors(100))
    result = diebold_mariano_test(
        holdout,
        ModelId.LAG_REGRESSION,
        ModelId.NAIVE,
        loss_type=LossType.SQUARED_ERROR,
    )

    assert automatic_hac_lag(100) == 4
    assert result.hac_lag == 4
    assert result.forecast_horizon == 1
    assert result.hln_correction_factor == pytest.approx(np.sqrt(99.0 / 100.0))


@pytest.mark.parametrize("loss_type", tuple(LossType))
def test_dm_detects_intentionally_large_performance_difference(loss_type) -> None:
    holdout, _ = aligned_holdout(varied_errors(120))

    result = diebold_mariano_test(
        holdout,
        ModelId.LAG_REGRESSION,
        ModelId.NAIVE,
        loss_type=loss_type,
    )

    assert result.available
    assert result.dm_statistic < 0.0
    assert result.raw_p_value < 0.001


def test_identical_errors_do_not_create_false_significance() -> None:
    errors = varied_errors(80)
    errors[ModelId.ARIMA] = errors[ModelId.LAG_REGRESSION].copy()
    holdout, _ = aligned_holdout(errors)

    result = diebold_mariano_test(
        holdout,
        ModelId.LAG_REGRESSION,
        ModelId.ARIMA,
        loss_type=LossType.SQUARED_ERROR,
    )

    assert not result.available
    assert result.dm_statistic is None
    assert result.raw_p_value == 1.0
    assert not result.reject


def test_zero_long_run_variance_is_explicitly_non_rejecting() -> None:
    errors = varied_errors(30)
    errors[ModelId.LAG_REGRESSION] = np.zeros(30)
    errors[ModelId.ARIMA] = np.ones(30)
    holdout, _ = aligned_holdout(errors)

    result = diebold_mariano_test(
        holdout,
        ModelId.LAG_REGRESSION,
        ModelId.ARIMA,
        loss_type=LossType.ABSOLUTE_ERROR,
    )

    assert not result.available
    assert result.long_run_variance == pytest.approx(0.0)
    assert result.unavailable_reason == "zero or degenerate HAC long-run variance"
    assert result.holm_adjusted_p_value == 1.0


def test_holm_adjustment_is_valid_and_separate_by_loss_family() -> None:
    holdout, _ = aligned_holdout(varied_errors(100))
    results = run_within_company_dm_tests(holdout)

    for family in (results.squared_error, results.absolute_error):
        assert len(family) == 6
        assert all(
            0.0 <= item.raw_p_value <= item.holm_adjusted_p_value <= 1.0
            for item in family
        )
        lir_vs_naive = next(
            item
            for item in family
            if (item.model_1, item.model_2)
            == (ModelId.LAG_REGRESSION, ModelId.NAIVE)
        )
        assert lir_vs_naive.reject
    encoded = json.dumps(results.as_dict(), allow_nan=False)
    assert "squared_error" in encoded and "absolute_error" in encoded


def test_significant_friedman_runs_six_holm_corrected_wilcoxon_tests() -> None:
    result = compare_methods_across_companies(cross_company_metrics())

    assert result.metric == "mase"
    assert result.friedman_reject
    assert result.posthoc_performed
    assert len(result.pairwise_wilcoxon) == 6
    assert all(
        0.0 <= item.raw_p_value <= item.holm_adjusted_p_value <= 1.0
        for item in result.pairwise_wilcoxon
    )
    assert len(result.paired_mase_evidence) == len(MODEL_PAIRS) == 6
    assert all(item.wilcoxon.performed for item in result.paired_mase_evidence)
    assert all(
        item.wilcoxon.holm_adjusted_p_value is not None
        for item in result.paired_mase_evidence
    )


def test_non_significant_friedman_does_not_run_wilcoxon() -> None:
    result = compare_methods_across_companies(cross_company_metrics(equal=True))

    assert result.friedman_p_value == 1.0
    assert not result.friedman_reject
    assert not result.posthoc_performed
    assert result.pairwise_wilcoxon == ()
    assert all(
        not item.wilcoxon.performed
        and item.wilcoxon.reason == "friedman_not_significant"
        and item.wilcoxon.raw_p_value is None
        for item in result.paired_mase_evidence
    )


def test_paired_mase_evidence_preserves_fifteen_companies_and_full_precision() -> None:
    metrics = cross_company_metrics(companies=15)
    result = compare_methods_across_companies(metrics)

    assert len(result.paired_mase_evidence) == 6
    expected_companies = tuple(sorted(metrics))
    for item, expected_pair in zip(
        result.paired_mase_evidence, MODEL_PAIRS, strict=True
    ):
        assert (item.model_1, item.model_2) == expected_pair
        assert item.company_order == expected_companies
        assert item.observation_count == 15
        expected = np.asarray(item.model_1_mase) - np.asarray(item.model_2_mase)
        assert np.array_equal(np.asarray(item.paired_differences), expected)
        assert item.mean_difference == pytest.approx(float(np.mean(expected)))
        assert item.median_difference == pytest.approx(float(np.median(expected)))
        assert item.standard_deviation == pytest.approx(float(np.std(expected, ddof=1)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            expected_skewness = float(skew(expected, bias=False))
        if np.isfinite(expected_skewness):
            assert item.skewness == pytest.approx(expected_skewness)
            assert item.skewness_status == "available"
        else:
            assert item.skewness is None
            assert item.skewness_status.startswith("undefined_")
        assert item.positive_count + item.negative_count + item.zero_count == 15
        assert item.sign_test.sample_size == item.positive_count + item.negative_count
        assert item.sign_test.zero_count == item.zero_count
    json.dumps(result.paired_evidence_as_dict(), allow_nan=False)


def test_sign_test_excludes_zeros_and_all_zero_pair_is_explicitly_unavailable() -> None:
    mixed = cross_company_metrics(companies=15)
    for index, symbol in enumerate(sorted(mixed)):
        arima = mixed[symbol][ModelId.ARIMA]
        mase = mixed[symbol][ModelId.LAG_REGRESSION].mase if index < 3 else arima.mase
        mixed[symbol][ModelId.LAG_REGRESSION] = metric(arima.rmse, mase)
    mixed_result = compare_methods_across_companies(mixed)
    mixed_pair = mixed_result.paired_mase_evidence[0]
    assert mixed_pair.zero_count == 12
    assert mixed_pair.sign_test.sample_size == 3
    assert mixed_pair.sign_test.performed

    equal_result = compare_methods_across_companies(
        cross_company_metrics(companies=15, equal=True)
    )
    all_zero = equal_result.paired_mase_evidence[0]
    assert all_zero.zero_count == 15
    assert not all_zero.sign_test.performed
    assert all_zero.sign_test.sample_size == 0
    assert all_zero.sign_test.raw_p_value is None
    assert all_zero.sign_test.reason == "no_nonzero_paired_differences"
    assert all_zero.skewness is None
    assert all_zero.skewness_status == "undefined_constant_differences"


def test_across_company_test_is_independent_of_raw_peso_rmse() -> None:
    ordinary = compare_methods_across_companies(cross_company_metrics())
    reversed_rmse = compare_methods_across_companies(
        cross_company_metrics(reverse_rmse=True)
    )

    assert ordinary.as_dict() == reversed_rmse.as_dict()
    assert ordinary.paired_evidence_as_dict() == reversed_rmse.paired_evidence_as_dict()


def test_paired_evidence_does_not_change_existing_dm_results() -> None:
    holdout, _ = aligned_holdout(varied_errors(80))
    before = run_within_company_dm_tests(holdout).as_dict()

    compare_methods_across_companies(cross_company_metrics(companies=15))

    after = run_within_company_dm_tests(holdout).as_dict()
    assert after == before
