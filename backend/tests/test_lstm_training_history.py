"""Complete, leakage-safe LSTM training-history instrumentation tests."""

from dataclasses import FrozenInstanceError
from datetime import date, timedelta
import gzip
import json
import math

import numpy as np
import pytest
import torch

from config.model_config import LstmConfig, ModelConfig
from src.data.split import build_company_evaluation_plan
from src.data.validator import OhlcvRecord
from src.features.targets import build_next_day_pairs
from src.models.lstm import build_delta_sequence_samples
from src.training import train_lstm as train_lstm_module
from src.training.train_lstm import (
    FINAL_EPOCH_SELECTION_STAGE,
    FIXED_EPOCH_REFIT_STAGE,
    LSTM_EVALUATION_SCHEMA_VERSION,
    LSTM_TRAINING_HISTORY_SCHEMA_ID,
    LSTM_TRAINING_HISTORY_SCHEMA_VERSION,
    TUNING_EARLY_STOPPING_STAGE,
    candidate_specifications,
    fit_fixed_epochs,
    lstm_configuration_id,
    persist_lstm_artifacts,
    train_lstm_for_evaluation,
    tune_lstm,
)


def _records(count: int = 52) -> tuple[OhlcvRecord, ...]:
    start = date(2024, 1, 2)
    return tuple(
        OhlcvRecord(
            trading_date=start + timedelta(days=index),
            open=(close := 100.0 + 0.12 * index + 1.4 * math.sin(index / 3.0))
            - 0.2,
            high=close + 0.7,
            low=close - 0.7,
            close=close,
            volume=10_000.0 + index,
        )
        for index in range(count)
    )


def _config(**overrides: object) -> LstmConfig:
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
def history_fixture():
    records = _records()
    plan = build_company_evaluation_plan(
        "ALI", records, model_config=ModelConfig(evaluation_proportion=0.2)
    )
    config = _config()
    tuning = tune_lstm(plan.development_pairs, config=config)
    return records, plan, config, tuning


def test_configuration_id_is_stable_and_specification_derived() -> None:
    specification = candidate_specifications(_config(lookback_lengths=(2,)))[0]

    assert lstm_configuration_id(specification) == (
        "lstm-v1-lb2-h3-lr0.01-bs8-"
        "6b7fa89ade43144c2d3011097f6877b43a94bd331e351422c35989d5472e9dd1"
    )


def test_every_candidate_fold_seed_has_exactly_one_early_stop_history(
    history_fixture,
) -> None:
    _, _, config, tuning = history_fixture
    total_early_stopping_histories = 0

    for candidate in tuning.candidates:
        configuration_id = lstm_configuration_id(candidate.specification)
        early_histories = tuple(
            history
            for history in candidate.training_histories
            if history.training_stage == TUNING_EARLY_STOPPING_STAGE
        )
        fixed_histories = tuple(
            history
            for history in candidate.training_histories
            if history.training_stage == FIXED_EPOCH_REFIT_STAGE
        )
        expected = {
            (fold_index, seed)
            for fold_index in range(config.cv_splits)
            for seed in config.tuning_seeds
        }
        assert {(history.fold_index, history.seed) for history in early_histories} == expected
        assert {(history.fold_index, history.seed) for history in fixed_histories} == expected
        assert len(early_histories) == len(expected)
        assert len(fixed_histories) == len(expected)
        assert {history.configuration_id for history in candidate.training_histories} == {
            configuration_id
        }
        total_early_stopping_histories += len(early_histories)

    assert total_early_stopping_histories == (
        len(tuning.candidates) * config.cv_splits * len(config.tuning_seeds)
    )
    assert total_early_stopping_histories == 12


def test_epoch_records_are_complete_and_running_best_is_consistent(
    history_fixture,
) -> None:
    _, _, _, tuning = history_fixture

    for candidate in tuning.candidates:
        for history in candidate.training_histories:
            assert len(history.epochs) == history.epochs_trained
            assert tuple(record.epoch for record in history.epochs) == tuple(
                range(1, history.epochs_trained + 1)
            )
            assert all(math.isfinite(record.training_loss) for record in history.epochs)
            assert all(record.learning_rate > 0 for record in history.epochs)
            if history.training_stage == TUNING_EARLY_STOPPING_STAGE:
                running_best = tuple(
                    record.best_stopping_loss_so_far for record in history.epochs
                )
                assert all(value is not None for value in running_best)
                assert all(
                    current <= previous
                    for previous, current in zip(running_best, running_best[1:])
                )
                assert history.best_epoch == history.epochs[-1].best_epoch_so_far
                chosen = history.epochs[history.best_epoch - 1]
                assert chosen.stopping_loss == history.epochs[-1].best_stopping_loss_so_far
            else:
                assert history.best_epoch is None
                assert not history.early_stopped
                assert history.stopping_target_dates == ()
                assert all(record.stopping_loss is None for record in history.epochs)
                assert all(
                    record.best_stopping_loss_so_far is None
                    and record.best_epoch_so_far is None
                    for record in history.epochs
                )


def test_stopping_history_is_inside_training_and_excludes_outer_validation(
    history_fixture,
) -> None:
    _, _, _, tuning = history_fixture

    for candidate in tuning.candidates:
        early_by_key = {
            (history.fold_index, history.seed): history
            for history in candidate.training_histories
            if history.training_stage == TUNING_EARLY_STOPPING_STAGE
        }
        for score in candidate.fold_seed_scores:
            history = early_by_key[(score.fold_index, score.seed)]
            assert set(history.stopping_target_dates) < set(
                score.outer_training_target_dates
            )
            assert max(history.stopping_target_dates) < min(
                score.validation_target_dates
            )
            assert not set(history.stopping_target_dates) & set(
                score.validation_target_dates
            )
            assert history.stopping_target_dates == score.stopping_target_dates


def test_outer_validation_rmse_is_not_recorded_as_stopping_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = _records(36)
    plan = build_company_evaluation_plan(
        "ALI", records, model_config=ModelConfig(evaluation_proportion=0.2)
    )
    config = _config(lookback_lengths=(2,), max_epochs=1)
    monkeypatch.setattr(train_lstm_module, "_rmse", lambda *_: 999.0)

    tuning = tune_lstm(plan.development_pairs, config=config)

    assert all(score.rmse == 999.0 for score in tuning.candidates[0].fold_seed_scores)
    assert all(
        record.stopping_loss != 999.0
        for history in tuning.candidates[0].training_histories
        if history.training_stage == TUNING_EARLY_STOPPING_STAGE
        for record in history.epochs
    )


def test_final_two_stage_histories_preserve_locked_epoch_and_seed(
    monkeypatch: pytest.MonkeyPatch,
    history_fixture,
) -> None:
    records, plan, config, tuning = history_fixture
    monkeypatch.setattr(train_lstm_module, "tune_lstm", lambda *args, **kwargs: tuning)

    result = train_lstm_for_evaluation(records, plan, config=config)
    histories = result.training_histories()
    selection_history = result.epoch_selection.training_history
    fixed_history = result.fitted.training_history

    assert len(histories) == 26
    assert selection_history.training_stage == FINAL_EPOCH_SELECTION_STAGE
    assert selection_history.seed == 42
    assert selection_history.fold_index is None
    assert fixed_history is not None
    assert fixed_history.training_stage == FIXED_EPOCH_REFIT_STAGE
    assert fixed_history.seed == 42
    assert fixed_history.epochs_trained == result.epoch_selection.selected_epoch_count
    assert result.fitted.epoch_count == result.epoch_selection.selected_epoch_count
    with pytest.raises(FrozenInstanceError):
        selection_history.seed = 7  # type: ignore[misc]


def test_history_capture_preserves_deterministic_predictions_and_weights() -> None:
    config = _config(lookback_lengths=(2,))
    specification = candidate_specifications(config)[0]
    samples = build_delta_sequence_samples(
        build_next_day_pairs(_records(24)), lookback=specification.lookback
    )

    first = fit_fixed_epochs(samples, specification, epoch_count=2, seed=42)
    second = fit_fixed_epochs(samples, specification, epoch_count=2, seed=42)

    assert first.training_history == second.training_history
    np.testing.assert_allclose(first.predict_delta(samples), second.predict_delta(samples))
    for name, tensor in first.cpu_state_dict().items():
        torch.testing.assert_close(tensor, second.cpu_state_dict()[name])


def test_separate_history_artifact_round_trips_strictly_and_preserves_unrelated_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    history_fixture,
) -> None:
    records, plan, config, tuning = history_fixture
    monkeypatch.setattr(train_lstm_module, "tune_lstm", lambda *args, **kwargs: tuning)
    result = train_lstm_for_evaluation(records, plan, config=config)
    output_dir = tmp_path / "artifacts" / "evaluations" / "lstm"
    output_dir.mkdir(parents=True)
    unrelated = output_dir / "unrelated.json"
    unrelated.write_bytes(b'{"preserve":true}\n')
    before = unrelated.read_bytes()

    paths = persist_lstm_artifacts(
        result,
        artifact_name="ALI-history-test",
        artifacts_root=tmp_path / "artifacts",
    )

    assert paths.training_history is not None
    with gzip.open(paths.training_history, "rt", encoding="utf-8") as source:
        encoded = source.read()
    payload = json.loads(encoded)
    assert payload["schema_id"] == LSTM_TRAINING_HISTORY_SCHEMA_ID
    assert payload["schema_version"] == LSTM_TRAINING_HISTORY_SCHEMA_VERSION
    assert payload["histories"] == [
        history.as_dict() for history in result.training_histories()
    ]
    assert len(payload["histories"]) == 26
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert unrelated.read_bytes() == before
    compressed_before = paths.training_history.read_bytes()
    repeated_paths = persist_lstm_artifacts(
        result,
        artifact_name="ALI-history-test",
        artifacts_root=tmp_path / "artifacts",
    )
    assert repeated_paths.training_history is not None
    assert repeated_paths.training_history.read_bytes() == compressed_before
    assert unrelated.read_bytes() == before
    primary = json.loads(paths.metadata.read_text(encoding="utf-8"))
    assert primary["schema_version"] == LSTM_EVALUATION_SCHEMA_VERSION == 1
    assert "training_histories" not in primary
