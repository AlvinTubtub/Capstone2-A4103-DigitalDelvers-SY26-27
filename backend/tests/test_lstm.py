"""Sequence, leakage, refit, persistence, and determinism tests for LSTM."""

from dataclasses import replace
from datetime import date, timedelta
import gzip
import json
import math

import numpy as np
import pytest
import torch

from config.model_config import LstmConfig, ModelConfig
from config.settings import SETTINGS
from src.data.split import build_company_evaluation_plan
from src.data.validator import OhlcvRecord
from src.features.targets import build_next_day_pairs
from src.models.lstm import (
    LstmSpecification,
    UnivariateDeltaLSTM,
    build_delta_sequence_samples,
    fit_delta_scaler,
)
from src.training import train_lstm as train_lstm_module
from src.training.cross_validation import expanding_window_folds
from src.training.train_lstm import (
    LSTM_EVALUATION_SCHEMA_ID,
    LSTM_TRAINING_HISTORY_SCHEMA_ID,
    candidate_specifications,
    fit_fixed_epochs,
    persist_lstm_artifacts,
    refit_lstm_for_production,
    select_epoch_count,
    train_lstm_for_evaluation,
    tune_lstm,
)


def synthetic_records(count: int = 52) -> tuple[OhlcvRecord, ...]:
    start = date(2024, 1, 2)
    records = []
    for index in range(count):
        close = 100.0 + 0.12 * index + 1.4 * math.sin(index / 3.0)
        records.append(
            OhlcvRecord(
                trading_date=start + timedelta(days=index),
                open=close - 0.2,
                high=close + 0.7,
                low=close - 0.7,
                close=close,
                volume=10_000.0 + index,
            )
        )
    return tuple(records)


def quick_config(**overrides: object) -> LstmConfig:
    values: dict[str, object] = {
        "lookback_lengths": (2, 4),
        "hidden_sizes": (3,),
        "learning_rates": (0.01,),
        "batch_sizes": (8,),
        "tuning_seeds": (3, 5, 7),
        "cv_splits": 2,
        "max_epochs": 2,
        "early_stopping_patience": 1,
        "stopping_tail_proportion": 0.2,
        "minimum_stopping_samples": 2,
        "final_seed": 42,
    }
    values.update(overrides)
    return LstmConfig(**values)


@pytest.fixture(scope="module")
def tuning_fixture():
    records = synthetic_records()
    plan = build_company_evaluation_plan(
        "ALI",
        records,
        model_config=ModelConfig(evaluation_proportion=0.2),
    )
    config = quick_config()
    tuning = tune_lstm(plan.development_pairs, config=config)
    return records, plan, config, tuning


def test_sequence_construction_uses_only_prior_deltas() -> None:
    pairs = build_next_day_pairs(synthetic_records(9))
    samples = build_delta_sequence_samples(pairs, lookback=3)
    first = samples[0]
    changed_pairs = pairs[:3] + (
        replace(
            pairs[3],
            actual_close=pairs[3].actual_close + 500.0,
            target_delta=pairs[3].target_delta + 500.0,
        ),
    ) + pairs[4:]
    changed_first = build_delta_sequence_samples(changed_pairs, lookback=3)[0]

    assert first.source_pair_index == 3
    assert first.origin_date == pairs[3].origin_date
    assert first.target_date == pairs[3].target_date
    assert first.input_deltas == tuple(pair.target_delta for pair in pairs[:3])
    assert first.target_delta == pairs[3].target_delta
    assert changed_first.input_deltas == first.input_deltas
    assert changed_first.target_delta != first.target_delta


def test_active_lstm_is_strictly_univariate() -> None:
    network = UnivariateDeltaLSTM(hidden_size=4)

    assert network.lstm.input_size == 1
    assert network.output.out_features == 1


def test_default_search_has_five_folds_three_seeds_and_fixed_final_seed() -> None:
    config = LstmConfig()

    assert config.cv_splits == 5
    assert len(config.tuning_seeds) == 3
    assert config.final_seed == 42
    assert {candidate.lookback for candidate in candidate_specifications(config)} == set(
        config.lookback_lengths
    )


def test_all_lookbacks_use_identical_outer_validation_dates(tuning_fixture) -> None:
    _, _, config, tuning = tuning_fixture

    assert {candidate.specification.lookback for candidate in tuning.candidates} == set(
        config.lookback_lengths
    )
    for candidate in tuning.candidates:
        for fold_index, expected_dates in enumerate(
            tuning.common_validation_target_dates_by_fold
        ):
            observed = {
                score.validation_target_dates
                for score in candidate.fold_seed_scores
                if score.fold_index == fold_index
            }
            assert observed == {expected_dates}


def test_fold_scaler_is_fitted_only_on_outer_training_history(tuning_fixture) -> None:
    _, plan, config, tuning = tuning_fixture
    candidate = next(
        value for value in tuning.candidates if value.specification.lookback == 2
    )
    first_score = next(
        score
        for score in candidate.fold_seed_scores
        if score.fold_index == 0 and score.seed == config.tuning_seeds[0]
    )
    all_candidate_samples = build_delta_sequence_samples(
        plan.development_pairs,
        lookback=2,
    )
    common_dates = tuple(
        sample.target_date
        for sample in build_delta_sequence_samples(
            plan.development_pairs,
            lookback=max(config.lookback_lengths),
        )
    )
    by_date = {sample.target_date: sample for sample in all_candidate_samples}
    aligned = tuple(by_date[value] for value in common_dates)
    first_fold = expanding_window_folds(
        len(aligned), n_splits=config.cv_splits
    )[0]
    training = tuple(aligned[index] for index in first_fold.train_indices)
    expected = fit_delta_scaler(training)
    full = fit_delta_scaler(aligned)

    assert first_score.scaler_mean == pytest.approx(expected.mean)
    assert first_score.scaler_scale == pytest.approx(expected.scale)
    assert first_score.scaler_observations == expected.observations
    assert first_score.scaler_mean != pytest.approx(full.mean)


def test_stopping_tail_is_inside_training_and_before_outer_validation(
    tuning_fixture,
) -> None:
    _, _, _, tuning = tuning_fixture

    for candidate in tuning.candidates:
        for score in candidate.fold_seed_scores:
            assert set(score.stopping_target_dates) < set(
                score.outer_training_target_dates
            )
            assert max(score.stopping_target_dates) < min(
                score.validation_target_dates
            )


def test_stage_a_scaler_excludes_its_stopping_tail() -> None:
    pairs = build_next_day_pairs(synthetic_records(20))
    samples = list(build_delta_sequence_samples(pairs, lookback=2))
    altered = tuple(
        replace(sample, target_delta=500.0)
        if index >= len(samples) - 3
        else sample
        for index, sample in enumerate(samples)
    )
    config = quick_config(
        lookback_lengths=(2,),
        stopping_tail_proportion=0.15,
        minimum_stopping_samples=3,
    )
    specification = candidate_specifications(config)[0]
    expected_core = altered[:-3]

    selection = select_epoch_count(altered, specification, seed=3, config=config)
    expected_scaler = fit_delta_scaler(expected_core)

    assert selection.scaler_mean == pytest.approx(expected_scaler.mean)
    assert selection.stopping_target_dates == tuple(
        sample.target_date for sample in altered[-3:]
    )


def test_tuning_uses_all_three_seeds_and_averages_them(tuning_fixture) -> None:
    _, _, config, tuning = tuning_fixture

    for candidate in tuning.candidates:
        assert {summary.seed for summary in candidate.seed_summaries} == set(
            config.tuning_seeds
        )
        assert len(candidate.fold_seed_scores) == (
            config.cv_splits * len(config.tuning_seeds)
        )
        assert candidate.mean_validation_rmse == pytest.approx(
            np.mean([score.rmse for score in candidate.fold_seed_scores])
        )
        assert candidate.validation_rmse_standard_deviation == pytest.approx(
            np.std([score.rmse for score in candidate.fold_seed_scores])
        )


def test_final_refit_uses_every_development_sequence(
    monkeypatch: pytest.MonkeyPatch,
    tuning_fixture,
) -> None:
    records, plan, config, tuning = tuning_fixture
    monkeypatch.setattr(train_lstm_module, "tune_lstm", lambda *args, **kwargs: tuning)

    result = train_lstm_for_evaluation(records, plan, config=config)
    all_samples = build_delta_sequence_samples(
        build_next_day_pairs(records),
        lookback=tuning.selected_specification.lookback,
    )
    expected_development = tuple(
        sample
        for sample in all_samples
        if sample.target_date in set(plan.development_target_dates)
    )

    assert result.fitted.training_size == len(expected_development)
    assert result.fitted.seed == 42
    assert len(result.epoch_selection.core_target_dates) + len(
        result.epoch_selection.stopping_target_dates
    ) == len(expected_development)
    assert result.fitted.scaler is not None


def test_predictions_reconstruct_close_from_origin_plus_delta(
    monkeypatch: pytest.MonkeyPatch,
    tuning_fixture,
) -> None:
    records, plan, config, tuning = tuning_fixture
    monkeypatch.setattr(train_lstm_module, "tune_lstm", lambda *args, **kwargs: tuning)
    result = train_lstm_for_evaluation(records, plan, config=config)

    np.testing.assert_allclose(
        result.predicted_closes,
        np.asarray([pair.origin_close for pair in plan.evaluation_pairs])
        + np.asarray(result.predicted_deltas),
    )


def test_fixed_seed_training_is_deterministic() -> None:
    config = quick_config(lookback_lengths=(2,))
    specification = candidate_specifications(config)[0]
    samples = build_delta_sequence_samples(
        build_next_day_pairs(synthetic_records(24)),
        lookback=2,
    )

    first = fit_fixed_epochs(samples, specification, epoch_count=2, seed=42)
    second = fit_fixed_epochs(samples, specification, epoch_count=2, seed=42)

    np.testing.assert_allclose(first.predict_delta(samples), second.predict_delta(samples))
    for name, first_tensor in first.cpu_state_dict().items():
        torch.testing.assert_close(first_tensor, second.cpu_state_dict()[name])
    with pytest.raises(ValueError, match="must remain 42"):
        quick_config(final_seed=41)


def test_production_refit_repeats_two_stages_with_seed_42() -> None:
    records = synthetic_records(30)
    config = quick_config(lookback_lengths=(2,))
    specification = candidate_specifications(config)[0]

    result = refit_lstm_for_production(
        records,
        selected_specification=specification,
        config=config,
    )
    expected_count = len(
        build_delta_sequence_samples(
            build_next_day_pairs(records),
            lookback=specification.lookback,
        )
    )

    assert result.fitted.training_size == expected_count
    assert result.fitted.seed == 42
    assert result.fitted.epoch_count == result.epoch_selection.selected_epoch_count


def test_model_and_scaler_state_are_persisted_under_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    tuning_fixture,
) -> None:
    production_paths = (
        SETTINGS.artifacts_dir / "evaluations" / "lstm" / "BPI.json",
        SETTINGS.artifacts_dir / "evaluations" / "lstm" / "BPI.pt",
    )
    production_before = tuple(
        path.read_bytes() if path.is_file() else None for path in production_paths
    )
    records, plan, config, tuning = tuning_fixture
    monkeypatch.setattr(train_lstm_module, "tune_lstm", lambda *args, **kwargs: tuning)
    result = train_lstm_for_evaluation(records, plan, config=config)

    paths = persist_lstm_artifacts(
        result,
        artifact_name="ALI-test",
        artifacts_root=tmp_path / "artifacts",
    )
    metadata = json.loads(paths.metadata.read_text(encoding="utf-8"))
    checkpoint = torch.load(paths.model_state, map_location="cpu", weights_only=True)

    assert paths.metadata.parent == (
        tmp_path / "artifacts" / "evaluations" / "lstm"
    )
    assert paths.model_state.parent == paths.metadata.parent
    assert paths.training_history is not None
    assert paths.training_history.parent == paths.metadata.parent
    assert metadata["schema_id"] == LSTM_EVALUATION_SCHEMA_ID
    assert metadata["schema_version"] == 1
    assert metadata["model_state_file"] == "ALI-test.pt"
    assert metadata["final_development_stage_b"]["scaler"]
    assert checkpoint["scaler"] == result.fitted.scaler.state_dict()
    assert checkpoint["model_state_dict"]
    assert checkpoint["schema_id"] == LSTM_EVALUATION_SCHEMA_ID
    with gzip.open(paths.training_history, "rt", encoding="utf-8") as source:
        history_payload = json.load(source)
    assert history_payload["schema_id"] == LSTM_TRAINING_HISTORY_SCHEMA_ID
    assert history_payload["schema_version"] == 1
    assert len(metadata["tuning"]["candidates"]) == len(tuning.candidates)
    for persisted, in_memory in zip(
        metadata["tuning"]["candidates"], tuning.candidates
    ):
        assert {summary["seed"] for summary in persisted["seed_summaries"]} == set(
            config.tuning_seeds
        )
        assert len(persisted["fold_seed_scores"]) == len(
            in_memory.fold_seed_scores
        )
    expected = json.loads(
        json.dumps(
            result.as_metadata_dict(model_state_file="ALI-test.pt"),
            allow_nan=False,
        )
    )
    assert {key: metadata[key] for key in expected} == expected
    assert tuple(
        path.read_bytes() if path.is_file() else None for path in production_paths
    ) == production_before
