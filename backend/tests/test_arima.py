"""Focused unit and integration tests for the fresh ARIMA pipeline."""

from datetime import date, timedelta
import json
from types import SimpleNamespace

import numpy as np
import pytest

from config.model_config import ArimaConfig, ModelConfig
from config.settings import SETTINGS
from src.data.split import build_company_evaluation_plan
from src.data.validator import OhlcvRecord
from src.models import arima as arima_model_module
from src.models.arima import (
    ArimaConvergenceError,
    ArimaFitAttempt,
    ArimaSpecification,
    ConvergenceStatus,
    FittedArimaModel,
    candidate_specifications,
    convergence_status,
    fit_arima,
)
from src.training import train_arima as train_arima_module
from src.training.train_arima import (
    ARIMA_EVALUATION_SCHEMA_ID,
    ArimaCandidateResult,
    ArimaFoldScore,
    ArimaTuningResult,
    compute_adf_diagnostic,
    persist_arima_metadata,
    refit_arima_for_production,
    score_arima_candidate,
    train_arima_for_evaluation,
    tune_arima,
)


def arima_config(**overrides: object) -> ArimaConfig:
    values: dict[str, object] = {
        "p_values": (0,),
        "d_values": (1,),
        "q_values": (0,),
        "trend_options_by_d": ((1, ("t",)),),
        "cv_splits": 2,
        "retry_max_iterations": (200,),
    }
    values.update(overrides)
    return ArimaConfig(**values)


def synthetic_records(count: int = 72) -> tuple[OhlcvRecord, ...]:
    random = np.random.default_rng(812)
    closes = 100.0 + np.cumsum(0.15 + random.normal(0.0, 0.7, count))
    start = date(2024, 1, 2)
    return tuple(
        OhlcvRecord(
            trading_date=start + timedelta(days=index),
            open=float(close - 0.1),
            high=float(close + 0.8),
            low=float(close - 0.8),
            close=float(close),
            volume=10_000.0 + index,
        )
        for index, close in enumerate(closes)
    )


def test_default_grid_includes_all_bounded_orders_and_random_walks() -> None:
    specifications = candidate_specifications(ArimaConfig())
    orders = {specification.order for specification in specifications}

    assert len(specifications) == 80
    assert len(set(specifications)) == 80
    assert orders == {
        (p, d, q)
        for p in range(4)
        for d in range(3)
        for q in range(4)
    }
    assert {(0, d, 0) for d in range(3)} <= orders
    assert ArimaSpecification((0, 1, 0), "n") in specifications


def test_trend_and_drift_policy_is_explicit_and_configurable() -> None:
    config = ArimaConfig()

    assert config.trends_for_d(0) == ("n", "c")
    assert config.trends_for_d(1) == ("n", "t")
    assert config.trends_for_d(2) == ("n",)
    assert ArimaSpecification((0, 1, 0), "t").drift_enabled
    assert not ArimaSpecification((0, 1, 0), "n").drift_enabled


@pytest.mark.parametrize(
    ("retvals", "expected"),
    [
        ({"converged": True}, ConvergenceStatus.CONFIRMED_CONVERGED),
        ({"converged": False}, ConvergenceStatus.CONFIRMED_NON_CONVERGED),
        ({"iterations": 3}, ConvergenceStatus.UNAVAILABLE),
        (None, ConvergenceStatus.UNAVAILABLE),
    ],
)
def test_convergence_evidence_keeps_unavailable_distinct(
    retvals: object,
    expected: ConvergenceStatus,
) -> None:
    result = SimpleNamespace(mle_retvals=retvals)

    status, _ = convergence_status(result)

    assert status is expected


def test_fit_retries_and_rejects_confirmed_non_convergence(monkeypatch) -> None:
    statuses = iter((False, False))

    class FakeArima:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def fit(self, *, method_kwargs):
            return SimpleNamespace(mle_retvals={"converged": next(statuses)})

    monkeypatch.setattr(arima_model_module, "ARIMA", FakeArima)
    config = arima_config(retry_max_iterations=(10, 20))

    with pytest.raises(ArimaConvergenceError, match="2 attempt"):
        fit_arima([10.0, 10.2, 10.1, 10.3], ArimaSpecification((0, 1, 0), "t"), config=config)


def test_fit_retries_until_confirmed_convergence(monkeypatch) -> None:
    statuses = iter((False, True))
    limits: list[int] = []

    class FakeArima:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def fit(self, *, method_kwargs):
            limits.append(method_kwargs["maxiter"])
            return SimpleNamespace(mle_retvals={"converged": next(statuses)})

    monkeypatch.setattr(arima_model_module, "ARIMA", FakeArima)
    config = arima_config(retry_max_iterations=(10, 20))

    fitted = fit_arima(
        [10.0, 10.2, 10.1, 10.3],
        ArimaSpecification((0, 1, 0), "t"),
        config=config,
    )

    assert limits == [10, 20]
    assert [attempt.status for attempt in fitted.attempts] == [
        ConvergenceStatus.CONFIRMED_NON_CONVERGED,
        ConvergenceStatus.CONFIRMED_CONVERGED,
    ]


def test_state_update_uses_append_without_refit() -> None:
    calls: list[tuple[list[float], bool]] = []

    class FakeResult:
        def append(self, values, *, refit):
            calls.append((values, refit))
            return self

    model = FittedArimaModel(
        result=FakeResult(),
        specification=ArimaSpecification((0, 1, 0), "n"),
        attempts=(
            ArimaFitAttempt(
                max_iterations=100,
                status=ConvergenceStatus.CONFIRMED_CONVERGED,
                optimizer_details={"converged": True},
            ),
        ),
    )

    updated = model.append_actual(101.25)

    assert calls == [([101.25], False)]
    assert updated.result is model.result


def test_candidate_must_complete_every_required_fold(monkeypatch) -> None:
    calls = 0

    def failing_fit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ArimaConvergenceError("confirmed non-convergence")
        return _fake_walk_model(float(args[0][-1]))

    monkeypatch.setattr(train_arima_module, "fit_arima", failing_fit)
    records = synthetic_records(30)
    candidate = score_arima_candidate(
        [record.close for record in records],
        [record.trading_date for record in records],
        ArimaSpecification((0, 1, 0), "t"),
        config=arima_config(),
    )

    assert not candidate.completed_all_folds
    assert candidate.mean_validation_rmse is None
    assert len(candidate.fold_scores) == 1
    assert "confirmed non-convergence" in candidate.failure


def test_tuning_selects_lowest_mean_rmse_from_complete_candidates(monkeypatch) -> None:
    better = ArimaSpecification((0, 1, 0), "t")
    worse = ArimaSpecification((1, 1, 0), "t")
    config = arima_config(p_values=(0, 1))

    def fake_score(close_values, close_dates, specification, *, config):
        score = 0.5 if specification == better else 1.5
        return ArimaCandidateResult(specification, True, score, ())

    monkeypatch.setattr(train_arima_module, "score_arima_candidate", fake_score)
    records = synthetic_records(12)
    result = tune_arima(
        [record.close for record in records],
        [record.trading_date for record in records],
        config=config,
    )

    assert result.selected_specification == better
    assert result.selected_mean_validation_rmse == 0.5


class _FakeWalkModel:
    def __init__(self, current: float, appended: list[float] | None = None) -> None:
        self.current = current
        self.appended = appended if appended is not None else []
        self.attempts = (
            ArimaFitAttempt(
                max_iterations=20,
                status=ConvergenceStatus.CONFIRMED_CONVERGED,
                optimizer_details={"converged": True},
            ),
        )

    def forecast_one(self) -> float:
        return self.current + 0.25

    def append_actual(self, actual: float):
        self.appended.append(actual)
        self.current = actual
        return self

    def fit_metadata(self) -> dict[str, object]:
        return {"convergence_status": "confirmed_converged", "nobs": 1}


def _fake_walk_model(current: float) -> _FakeWalkModel:
    return _FakeWalkModel(current)


def test_evaluation_fits_once_then_walks_exact_common_dates(monkeypatch) -> None:
    records = synthetic_records(40)
    plan = build_company_evaluation_plan(
        "ALI",
        records,
        model_config=ModelConfig(evaluation_proportion=0.2),
    )
    specification = ArimaSpecification((0, 1, 0), "t")
    tuning = ArimaTuningResult(
        selected_specification=specification,
        selected_mean_validation_rmse=1.0,
        candidates=(ArimaCandidateResult(specification, True, 1.0, ()),),
    )
    fit_calls: list[tuple[float, ...]] = []
    fitted_models: list[_FakeWalkModel] = []

    monkeypatch.setattr(train_arima_module, "tune_arima", lambda *args, **kwargs: tuning)

    def fake_fit(values, specification, *, config):
        fit_calls.append(tuple(values))
        model = _fake_walk_model(float(values[-1]))
        fitted_models.append(model)
        return model

    monkeypatch.setattr(train_arima_module, "fit_arima", fake_fit)
    result = train_arima_for_evaluation(records, plan, config=arima_config())

    assert len(fit_calls) == 1
    assert result.target_dates == plan.evaluation_target_dates
    assert len(result.predicted_closes) == len(plan.evaluation_pairs)
    assert fitted_models[0].appended == [
        pair.actual_close for pair in plan.evaluation_pairs
    ]


def test_statsmodels_candidate_and_production_refit_integration() -> None:
    records = synthetic_records()
    config = arima_config()
    specification = ArimaSpecification((0, 1, 0), "t")

    candidate = score_arima_candidate(
        [record.close for record in records],
        [record.trading_date for record in records],
        specification,
        config=config,
    )
    production = refit_arima_for_production(
        records,
        selected_specification=specification,
        config=config,
    )

    assert candidate.completed_all_folds
    assert len(candidate.fold_scores) == config.cv_splits
    assert candidate.mean_validation_rmse is not None
    assert production.model.convergence is ConvergenceStatus.CONFIRMED_CONVERGED
    assert np.isfinite(production.model.forecast_one())


def test_statsmodels_evaluation_pipeline_integration() -> None:
    records = synthetic_records()
    plan = build_company_evaluation_plan(
        "ALI",
        records,
        model_config=ModelConfig(evaluation_proportion=0.15),
    )

    result = train_arima_for_evaluation(records, plan, config=arima_config())

    assert result.target_dates == plan.evaluation_target_dates
    assert result.actual_closes == tuple(
        pair.actual_close for pair in plan.evaluation_pairs
    )
    assert len(result.predicted_closes) == len(plan.evaluation_pairs)
    assert np.isfinite(result.predicted_closes).all()
    assert (
        result.development_fit_metadata["convergence_status"]
        == "confirmed_converged"
    )
    diagnostics = result.as_metadata_dict()["diagnostics"]
    assert set(diagnostics) == {
        "selected_fitted_model",
        "holdout_forecast_errors",
    }
    assert diagnostics["holdout_forecast_errors"]["observations"] == len(
        plan.evaluation_pairs
    )
    assert diagnostics["holdout_forecast_errors"]["source"] == (
        "complete_aligned_holdout_forecast_errors"
    )


def test_adf_records_result_or_explicit_unavailability() -> None:
    records = synthetic_records()
    available = compute_adf_diagnostic([record.close for record in records])
    unavailable = compute_adf_diagnostic([10.0] * 20)

    assert available.available
    assert 0.0 <= available.p_value <= 1.0
    assert not unavailable.available
    assert unavailable.unavailable_reason


def test_metadata_is_written_only_below_arima_artifacts(monkeypatch, tmp_path) -> None:
    production_path = SETTINGS.artifacts_dir / "evaluations" / "arima" / "BPI.json"
    production_before = (
        production_path.read_bytes() if production_path.is_file() else None
    )
    records = synthetic_records(40)
    plan = build_company_evaluation_plan(
        "ALI",
        records,
        model_config=ModelConfig(evaluation_proportion=0.2),
    )
    specification = ArimaSpecification((0, 1, 0), "t")
    attempt = ArimaFitAttempt(
        max_iterations=200,
        status=ConvergenceStatus.CONFIRMED_CONVERGED,
        optimizer_details={"converged": True},
    )
    fold_scores = tuple(
        ArimaFoldScore(
            fold_index=index,
            train_start=records[0].trading_date,
            train_end=records[19 + index].trading_date,
            validation_start=records[20 + index].trading_date,
            validation_end=records[24 + index].trading_date,
            train_size=20 + index,
            validation_size=5,
            rmse=1.0 + index / 10,
            fit_attempts=(attempt,),
        )
        for index in range(2)
    )
    tuning = ArimaTuningResult(
        selected_specification=specification,
        selected_mean_validation_rmse=1.0,
        candidates=(ArimaCandidateResult(specification, True, 1.0, fold_scores),),
    )
    monkeypatch.setattr(train_arima_module, "tune_arima", lambda *args, **kwargs: tuning)
    monkeypatch.setattr(
        train_arima_module,
        "fit_arima",
        lambda values, specification, *, config: _fake_walk_model(values[-1]),
    )
    result = train_arima_for_evaluation(records, plan, config=arima_config())

    destination = persist_arima_metadata(
        result,
        artifact_name="ALI-test",
        artifacts_root=tmp_path / "artifacts",
    )
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert destination == (
        tmp_path / "artifacts" / "evaluations" / "arima" / "ALI-test.json"
    )
    assert destination.is_file()
    assert payload["schema_id"] == ARIMA_EVALUATION_SCHEMA_ID
    assert payload["schema_version"] == 1
    assert payload["tuning"]["selected_specification"] == specification.as_dict()
    assert len(payload["tuning"]["candidates"]) == 1
    assert len(payload["tuning"]["candidates"][0]["fold_scores"]) == 2
    assert payload["tuning"]["candidates"][0]["fold_scores"][0][
        "convergence_evidence"
    ]
    expected = json.loads(json.dumps(result.as_metadata_dict(), allow_nan=False))
    assert {key: payload[key] for key in expected} == expected
    assert (
        production_path.read_bytes() if production_path.is_file() else None
    ) == production_before
