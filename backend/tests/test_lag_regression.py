"""Focused leakage, fitting, metadata, and determinism tests for LIR."""

from dataclasses import replace
from datetime import date, timedelta
import json
import math
import warnings

import numpy as np
import pytest

from config.model_config import LagRegressionConfig, ModelConfig, RegressionFeatureConfig
from config.settings import SETTINGS
from src.data.split import build_company_evaluation_plan
from src.data.validator import OhlcvRecord
from src.features.regression_features import (
    FeatureConstructionError,
    RegressionFeatureContract,
    RegressionFeatureGroup,
    build_regression_dataset,
    feature_names_for_pacf_lags,
    regression_feature_contract,
    regression_feature_names,
)
from src.models.base import reconstruct_close
from src.models.lag_regression import LagRegressionModel
from src.training.cross_validation import expanding_window_folds
from src.training.train_lir import (
    AlphaGridBoundaryWarning,
    LIR_EVALUATION_SCHEMA_ID,
    classify_alpha_grid_position,
    persist_lir_metadata,
    refit_lir_for_production,
    train_lir_for_evaluation,
    tune_lir_alpha,
)


def synthetic_records(count: int = 140) -> tuple[OhlcvRecord, ...]:
    start = date(2023, 1, 2)
    result = []
    for index in range(count):
        close = 100.0 + 0.08 * index + 1.7 * math.sin(index / 4.0)
        open_price = close - 0.25 * math.cos(index / 3.0)
        result.append(
            OhlcvRecord(
                trading_date=start + timedelta(days=index),
                open=open_price,
                high=max(open_price, close) + 0.6,
                low=min(open_price, close) - 0.6,
                close=close,
                volume=10_000.0 + 35.0 * index + 140.0 * (index % 5),
            )
        )
    return tuple(result)


def quick_config() -> LagRegressionConfig:
    return LagRegressionConfig(
        alpha_grid=(0.001, 0.01, 0.1),
        cv_splits=3,
        pacf_max_lag=5,
    )


def test_default_lasso_alpha_grid_includes_expanded_upper_range() -> None:
    assert LagRegressionConfig().alpha_grid == (
        0.0001,
        0.0003,
        0.001,
        0.003,
        0.01,
        0.03,
        0.1,
        0.3,
        1.0,
        3.0,
        10.0,
        30.0,
    )


@pytest.mark.parametrize(
    ("chosen_alpha", "classification", "lower", "upper", "interior"),
    [
        (0.001, "lower", True, False, False),
        (0.01, "interior", False, False, True),
        (0.1, "upper", False, True, False),
    ],
)
def test_alpha_grid_position_distinguishes_boundaries_and_interior(
    chosen_alpha: float,
    classification: str,
    lower: bool,
    upper: bool,
    interior: bool,
) -> None:
    position = classify_alpha_grid_position(chosen_alpha, quick_config().alpha_grid)

    assert position.classification == classification
    assert position.lower is lower
    assert position.upper is upper
    assert position.interior is interior


def development_samples(dataset, plan):
    dates = set(plan.development_target_dates)
    return tuple(sample for sample in dataset.samples if sample.target_date in dates)


def test_features_never_read_target_day_values() -> None:
    original = synthetic_records()
    target_index = 75
    changed_target = replace(
        original[target_index],
        open=900.0,
        high=920.0,
        low=880.0,
        close=910.0,
        volume=9_000_000.0,
    )
    perturbed = original[:target_index] + (changed_target,) + original[target_index + 1 :]

    original_dataset = build_regression_dataset(original)
    perturbed_dataset = build_regression_dataset(perturbed)
    target_date = original[target_index].trading_date
    original_sample = original_dataset.samples_for_target_dates([target_date])[0]
    perturbed_sample = perturbed_dataset.samples_for_target_dates([target_date])[0]

    assert original_sample.origin_date == original[target_index - 1].trading_date
    assert original_sample.feature_values == perturbed_sample.feature_values
    assert original_sample.actual_close != perturbed_sample.actual_close
    assert original_sample.target_delta != perturbed_sample.target_delta


def test_all_approved_causal_feature_families_are_available() -> None:
    config = RegressionFeatureConfig(raw_price_lags=(1, 5))
    dataset = build_regression_dataset(synthetic_records(), config)
    names = set(dataset.feature_names)

    assert "return_lag_1" in names
    assert "return_mean_5" in names and "return_std_20" in names
    assert "volume_change_1" in names and "volume_z_20" in names
    assert "range_pct" in names and "open_close_spread_pct" in names
    assert "rsi_14" in names
    assert "ema_relative_12" in names and "ema_relative_26" in names
    assert "macd_relative" in names and "macd_histogram_relative" in names
    assert "bollinger_z_20" in names and "bollinger_position_20" in names
    assert "raw_close_lag_1" in names and "raw_close_lag_5" in names
    assert np.isfinite(dataset.matrix()).all()


def test_feature_contract_exactly_classifies_unchanged_candidate_tuple() -> None:
    config = RegressionFeatureConfig(raw_price_lags=(1, 5))
    names_before_contract = regression_feature_names(config)
    contract = regression_feature_contract(config)

    assert contract.candidate_feature_names == names_before_contract
    assert regression_feature_names(config) == names_before_contract
    groups = dict(contract.feature_groups)
    flattened = tuple(name for names in groups.values() for name in names)
    assert len(flattened) == len(set(flattened)) == len(names_before_contract)
    assert set(flattened) == set(names_before_contract)
    assert groups[RegressionFeatureGroup.RAW_PRICE_LEVEL_FEATURES] == (
        "raw_close_lag_1",
        "raw_close_lag_5",
    )
    assert "return_lag_1" in groups[RegressionFeatureGroup.RETURN_FEATURES]
    assert "return_std_20" in groups[RegressionFeatureGroup.RETURN_FEATURES]
    assert "range_pct" in groups[RegressionFeatureGroup.NORMALIZED_PRICE_FEATURES]
    assert "rsi_14" in groups[RegressionFeatureGroup.NORMALIZED_PRICE_FEATURES]
    assert "volume_change_1" in groups[
        RegressionFeatureGroup.NORMALIZED_VOLUME_FEATURES
    ]
    assert "volume_z_20" in groups[
        RegressionFeatureGroup.NORMALIZED_VOLUME_FEATURES
    ]
    assert groups[RegressionFeatureGroup.TRANSFORMED_VOLUME_LEVEL_FEATURES] == (
        "volume_log",
    )
    assert "volume_log" not in groups[
        RegressionFeatureGroup.RAW_VOLUME_LEVEL_FEATURES
    ]
    assert groups[RegressionFeatureGroup.RAW_VOLUME_LEVEL_FEATURES] == ()
    payload = contract.as_dict()
    assert payload["ordered_candidate_feature_names"] == list(names_before_contract)
    json.dumps(payload, allow_nan=False)


def test_feature_contract_rejects_target_fields_and_duplicate_membership() -> None:
    with pytest.raises(FeatureConstructionError, match="Target fields"):
        RegressionFeatureContract(
            candidate_feature_names=("target_delta",),
            feature_groups=(
                (RegressionFeatureGroup.RETURN_FEATURES, ("target_delta",)),
            ),
        )
    with pytest.raises(FeatureConstructionError, match="exactly one group"):
        RegressionFeatureContract(
            candidate_feature_names=("return_lag_1",),
            feature_groups=(
                (RegressionFeatureGroup.RETURN_FEATURES, ("return_lag_1",)),
                (
                    RegressionFeatureGroup.NORMALIZED_PRICE_FEATURES,
                    ("return_lag_1",),
                ),
            ),
        )


def test_contract_creation_does_not_change_feature_matrix_values() -> None:
    config = RegressionFeatureConfig(raw_price_lags=(1, 5))
    before = build_regression_dataset(synthetic_records(), config)

    regression_feature_contract(config)
    after = build_regression_dataset(synthetic_records(), config)

    assert after.feature_names == before.feature_names
    np.testing.assert_array_equal(after.matrix(), before.matrix())


def test_feature_contract_validation_does_not_change_lir_predictions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = synthetic_records()
    dataset = build_regression_dataset(source)
    plan = build_company_evaluation_plan("ALI", source)
    monkeypatch.setattr(
        "src.training.train_lir.select_pacf_lags",
        lambda training_returns, *, max_lag, significance_z: (1, 2),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        validated = train_lir_for_evaluation(dataset, plan, config=quick_config())

    monkeypatch.setattr(
        "src.training.train_lir._validate_candidate_contract",
        lambda dataset, config: None,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        without_contract_check = train_lir_for_evaluation(
            dataset,
            plan,
            config=quick_config(),
        )

    np.testing.assert_array_equal(
        validated.predicted_deltas,
        without_contract_check.predicted_deltas,
    )
    np.testing.assert_array_equal(
        validated.predicted_closes,
        without_contract_check.predicted_closes,
    )


def test_pacf_receives_fold_training_returns_only(monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = build_regression_dataset(synthetic_records())
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    samples = development_samples(dataset, plan)
    observed_return_counts: list[int] = []

    def spy(training_returns, *, max_lag, significance_z):
        observed_return_counts.append(len(training_returns))
        return (1,)

    monkeypatch.setattr("src.training.train_lir.select_pacf_lags", spy)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        tune_lir_alpha(dataset, samples, config=quick_config())

    assert len(observed_return_counts) == quick_config().cv_splits
    assert observed_return_counts == sorted(observed_return_counts)
    assert len(set(observed_return_counts)) == quick_config().cv_splits
    assert max(observed_return_counts) < len(dataset.daily_returns)


def test_each_fold_scaler_is_fitted_on_its_training_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = build_regression_dataset(synthetic_records())
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    samples = development_samples(dataset, plan)
    monkeypatch.setattr(
        "src.training.train_lir.select_pacf_lags",
        lambda training_returns, *, max_lag, significance_z: (1,),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        tuning = tune_lir_alpha(dataset, samples, config=quick_config())
    first_score = next(
        score
        for score in tuning.fold_scores
        if score.fold_index == 0 and score.alpha == quick_config().alpha_grid[0]
    )
    first_fold = expanding_window_folds(
        len(samples), n_splits=quick_config().cv_splits
    )[0]
    training = tuple(samples[index] for index in first_fold.train_indices)
    feature_names = feature_names_for_pacf_lags(dataset.feature_names, (1,))
    expected_training_mean = np.mean(
        dataset.matrix(training, feature_names=feature_names), axis=0
    )
    full_development_mean = np.mean(
        dataset.matrix(samples, feature_names=feature_names), axis=0
    )

    np.testing.assert_allclose(first_score.scaler_mean, expected_training_mean)
    assert not np.allclose(first_score.scaler_mean, full_development_mean)
    assert first_score.train_end < first_score.validation_start


def test_delta_target_reconstructs_the_predicted_close() -> None:
    assert reconstruct_close(101.25, -1.5) == pytest.approx(99.75)
    np.testing.assert_allclose(
        reconstruct_close(np.array([100.0, 120.0]), np.array([1.0, -2.0])),
        np.array([101.0, 118.0]),
    )


def test_prediction_shape_is_one_value_per_row() -> None:
    features = np.asarray([[0.0, 1.0], [1.0, 2.0], [2.0, 4.0], [3.0, 8.0]])
    targets = np.asarray([0.0, 0.5, 1.0, 1.5])
    model = LagRegressionModel(alpha=0.001).fit(features, targets, ("a", "b"))

    assert model.predict_delta(features).shape == (4,)
    assert model.predict_delta(features[0]).shape == (1,)
    assert model.predict_close(features, np.full(4, 100.0)).shape == (4,)


def test_selected_feature_and_reproduction_metadata_are_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = synthetic_records()
    dataset = build_regression_dataset(source)
    plan = build_company_evaluation_plan(
        "ALI", source, model_config=ModelConfig(evaluation_proportion=0.2)
    )
    monkeypatch.setattr(
        "src.training.train_lir.select_pacf_lags",
        lambda training_returns, *, max_lag, significance_z: (1, 2),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        result = train_lir_for_evaluation(dataset, plan, config=quick_config())
    metadata = result.as_metadata_dict()
    fit_metadata = result.fitted.fit_metadata

    assert result.target_dates == plan.evaluation_target_dates
    assert len(result.predicted_deltas) == len(plan.evaluation_pairs)
    assert len(result.predicted_closes) == len(plan.evaluation_pairs)
    assert fit_metadata.feature_names
    assert set(fit_metadata.selected_features) <= set(fit_metadata.feature_names)
    assert len(fit_metadata.coefficients) == len(fit_metadata.feature_names)
    assert len(fit_metadata.scaler_mean) == len(fit_metadata.feature_names)
    assert len(fit_metadata.scaler_scale) == len(fit_metadata.feature_names)
    assert metadata["development_fit"]["pacf_selected_lags"] == [1, 2]
    assert metadata["tuning"]["fold_scores"]
    contract = metadata["candidate_feature_contract"]
    assert contract["ordered_candidate_feature_names"] == list(dataset.feature_names)
    assert contract["target_name"] == "next_day_close_delta"
    json.dumps(metadata, allow_nan=False)


def test_fold_and_development_metadata_match_names_passed_to_lasso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = synthetic_records()
    dataset = build_regression_dataset(source)
    plan = build_company_evaluation_plan(
        "ALI", source, model_config=ModelConfig(evaluation_proportion=0.2)
    )
    monkeypatch.setattr(
        "src.training.train_lir.select_pacf_lags",
        lambda training_returns, *, max_lag, significance_z: (1, 2),
    )
    observed_names: list[tuple[str, ...]] = []
    original_fit = LagRegressionModel.fit

    def recording_fit(self, features, targets, feature_names):
        observed_names.append(tuple(feature_names))
        return original_fit(self, features, targets, feature_names)

    monkeypatch.setattr(LagRegressionModel, "fit", recording_fit)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        result = train_lir_for_evaluation(dataset, plan, config=quick_config())

    fold_count = len(result.tuning.fold_scores)
    assert tuple(score.feature_names for score in result.tuning.fold_scores) == tuple(
        observed_names[:fold_count]
    )
    assert result.fitted.fit_metadata.feature_names == observed_names[-1]
    for score in result.tuning.fold_scores:
        assert len(score.scaler_mean) == len(score.feature_names)
        assert len(score.scaler_scale) == len(score.feature_names)
        payload = score.as_dict()
        assert tuple(payload["scaler_mean"]) == score.feature_names
        assert tuple(payload["scaler_scale"]) == score.feature_names


def test_training_and_production_refits_are_deterministic() -> None:
    source = synthetic_records()
    dataset = build_regression_dataset(source)
    plan = build_company_evaluation_plan("ALI", source)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        first = train_lir_for_evaluation(dataset, plan, config=quick_config())
        second = train_lir_for_evaluation(dataset, plan, config=quick_config())
    np.testing.assert_allclose(first.predicted_deltas, second.predicted_deltas)
    assert first.tuning.chosen_alpha == second.tuning.chosen_alpha
    assert first.fitted.fit_metadata == second.fitted.fit_metadata

    first_production = refit_lir_for_production(
        dataset, chosen_alpha=first.tuning.chosen_alpha, config=quick_config()
    )
    second_production = refit_lir_for_production(
        dataset, chosen_alpha=first.tuning.chosen_alpha, config=quick_config()
    )
    assert first_production.fit_metadata == second_production.fit_metadata


@pytest.mark.parametrize(
    ("fold_scores", "chosen_alpha", "classification", "lower", "upper"),
    [
        ((1.0, 2.0, 3.0), 0.001, "lower", True, False),
        ((3.0, 2.0, 1.0), 0.1, "upper", False, True),
    ],
)
def test_boundary_alpha_emits_warning_and_structured_metadata(
    monkeypatch: pytest.MonkeyPatch,
    fold_scores: tuple[float, ...],
    chosen_alpha: float,
    classification: str,
    lower: bool,
    upper: bool,
) -> None:
    dataset = build_regression_dataset(synthetic_records())
    plan = build_company_evaluation_plan("ALI", synthetic_records())
    samples = development_samples(dataset, plan)
    monkeypatch.setattr(
        "src.training.train_lir.select_pacf_lags",
        lambda training_returns, *, max_lag, significance_z: (1,),
    )
    scores = iter(fold_scores * quick_config().cv_splits)
    monkeypatch.setattr(
        "src.training.train_lir._rmse",
        lambda actual, predicted: next(scores),
    )

    with pytest.warns(
        AlphaGridBoundaryWarning,
        match=f"{classification} grid boundary",
    ):
        result = tune_lir_alpha(dataset, samples, config=quick_config())

    assert result.alpha_at_grid_boundary is True
    assert result.chosen_alpha == chosen_alpha
    assert result.alpha_grid_position.as_dict() == {
        "classification": classification,
        "lower": lower,
        "upper": upper,
        "interior": False,
    }
    assert result.as_dict()["alpha_grid_position"] == (
        result.alpha_grid_position.as_dict()
    )


def test_reproducibility_metadata_persists_only_under_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    production_path = SETTINGS.artifacts_dir / "evaluations" / "lir" / "BPI.json"
    production_before = (
        production_path.read_bytes() if production_path.is_file() else None
    )
    source = synthetic_records()
    dataset = build_regression_dataset(source)
    plan = build_company_evaluation_plan("ALI", source)
    monkeypatch.setattr(
        "src.training.train_lir.select_pacf_lags",
        lambda training_returns, *, max_lag, significance_z: (1,),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AlphaGridBoundaryWarning)
        result = train_lir_for_evaluation(dataset, plan, config=quick_config())

    artifacts_root = tmp_path / "artifacts"
    destination = persist_lir_metadata(
        result,
        artifact_name="phase4_test_metadata",
        artifacts_root=artifacts_root,
    )
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert destination == (
        artifacts_root / "evaluations" / "lir" / "phase4_test_metadata.json"
    )
    assert payload["schema_id"] == LIR_EVALUATION_SCHEMA_ID
    assert payload["schema_version"] == 1
    assert payload["candidate_feature_contract"][
        "ordered_candidate_feature_names"
    ] == list(dataset.feature_names)
    assert payload["tuning"]["chosen_alpha"] == result.tuning.chosen_alpha
    assert payload["development_fit"]["selected_features"] == list(
        result.fitted.fit_metadata.selected_features
    )
    assert payload["development_fit"]["coefficients"]
    assert payload["development_fit"]["scaler"]["mean"]
    assert payload["development_fit"]["pacf_selected_lags"] == [1]
    assert len(payload["tuning"]["mean_validation_rmse"]) == len(
        result.configuration.alpha_grid
    )
    assert len(payload["tuning"]["fold_scores"]) == (
        len(result.configuration.alpha_grid) * result.configuration.cv_splits
    )
    assert all(
        fold["pacf_selected_lags"]
        and fold["feature_names"]
        and fold["scaler_mean"]
        and fold["scaler_scale"]
        for fold in payload["tuning"]["fold_scores"]
    )
    expected = json.loads(json.dumps(result.as_metadata_dict(), allow_nan=False))
    assert {key: payload[key] for key in expected} == expected
    assert (
        production_path.read_bytes() if production_path.is_file() else None
    ) == production_before
