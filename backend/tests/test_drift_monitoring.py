"""Prospective-only rolling drift and non-automating deployment policy tests."""

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from config.ledger_config import DriftPolicy
from config.model_config import ModelId
from src.ledger.schema import ForecastIssued, ForecastOutcomeObserved, NAIVE_MODEL_VERSION
from src.ledger.store import ForecastLedger
from src.monitoring.deployment_policy import (
    DeploymentReviewStatus,
    assess_deployment_candidate,
)
from src.monitoring.drift import DriftStatus, monitor_company_drift


MANILA = ZoneInfo("Asia/Manila")


def resolved_snapshot(
    tmp_path: Path,
    count: int,
    *,
    principal_error: float,
    naive_error: float,
):
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    events = []
    outcomes = []
    first_target = date(2026, 1, 2)
    for index in range(count):
        target = first_target + timedelta(days=index)
        origin = target - timedelta(days=1)
        created = datetime.combine(origin, datetime.min.time(), tzinfo=MANILA)
        observed = datetime.combine(target, datetime.min.time(), tzinfo=MANILA)
        actual = 100.0
        predictions = {
            ModelId.LAG_REGRESSION: actual + principal_error,
            ModelId.ARIMA: actual + principal_error / 2.0,
            ModelId.LSTM: actual - principal_error / 4.0,
            ModelId.NAIVE: actual + naive_error,
        }
        for method, prediction in predictions.items():
            event = ForecastIssued.create(
                created_at=created,
                symbol="ALI",
                origin_date=origin,
                target_date=target,
                method=method,
                model_version=(
                    NAIVE_MODEL_VERSION if method is ModelId.NAIVE else f"version-{method.value}"
                ),
                prediction=prediction,
            )
            events.append(event)
            outcomes.append(
                ForecastOutcomeObserved.create(
                    event,
                    observed_at=observed,
                    actual_close=actual,
                )
            )
    ledger.append_issuances(events)
    ledger.append_outcomes(outcomes)
    return ledger.read()


def test_rolling_mae_bias_and_principal_vs_naive(tmp_path: Path) -> None:
    snapshot = resolved_snapshot(
        tmp_path,
        20,
        principal_error=2.0,
        naive_error=3.0,
    )
    report = monitor_company_drift(snapshot, "ALI")
    lir = report.report_for(ModelId.LAG_REGRESSION)

    assert lir.review_window.rolling_mae == pytest.approx(2.0)
    assert lir.review_window.rolling_bias == pytest.approx(2.0)
    assert lir.review_window.naive_rolling_mae == pytest.approx(3.0)
    assert lir.review_window.mae_ratio_to_naive == pytest.approx(2.0 / 3.0)
    assert lir.review_window.win_count_vs_naive == 20
    assert lir.review_window.win_proportion_vs_naive == pytest.approx(1.0)
    assert lir.status is DriftStatus.WATCH  # bias threshold is intentionally crossed.


def test_pending_forecasts_are_excluded_from_prospective_metrics(tmp_path: Path) -> None:
    snapshot = resolved_snapshot(
        tmp_path,
        20,
        principal_error=0.2,
        naive_error=1.0,
    )
    ledger = ForecastLedger(tmp_path / "events.jsonl")
    pending = ForecastIssued.create(
        created_at=datetime(2026, 3, 1, tzinfo=MANILA),
        symbol="ALI",
        origin_date=date(2026, 3, 1),
        target_date=date(2026, 3, 2),
        method=ModelId.LAG_REGRESSION,
        model_version="version-lag_reg",
        prediction=500.0,
    )
    ledger.append_issued(pending)

    report = monitor_company_drift(ledger.read(), "ALI")

    assert snapshot.resolved
    assert report.report_for(ModelId.LAG_REGRESSION).resolved_session_count == 20
    assert report.report_for(ModelId.LAG_REGRESSION).review_window.rolling_mae == pytest.approx(0.2)


def test_insufficient_data_and_deployment_policy_do_not_approve(tmp_path: Path) -> None:
    snapshot = resolved_snapshot(
        tmp_path,
        19,
        principal_error=0.2,
        naive_error=1.0,
    )
    report = monitor_company_drift(snapshot, "ALI")
    lir = report.report_for(ModelId.LAG_REGRESSION)
    deployment = assess_deployment_candidate(report, ModelId.LAG_REGRESSION)

    assert lir.status is DriftStatus.INSUFFICIENT_DATA
    assert deployment.status is DeploymentReviewStatus.INSUFFICIENT_PROSPECTIVE_EVIDENCE
    assert deployment.approved is False


def test_sustained_prospective_underperformance_emits_drift_signal(
    tmp_path: Path,
) -> None:
    snapshot = resolved_snapshot(
        tmp_path,
        60,
        principal_error=2.0,
        naive_error=0.5,
    )
    report = monitor_company_drift(snapshot, "ALI")
    lir = report.report_for(ModelId.LAG_REGRESSION)

    assert lir.status is DriftStatus.DRIFT_SIGNAL
    assert lir.consideration_window.available_sessions == 60
    assert lir.consideration_window.mae_ratio_to_naive == pytest.approx(4.0)
    assert lir.consideration_window.win_count_vs_naive == 0
    assert lir.consideration_window.win_proportion_vs_naive == 0.0


def test_configurable_windows_and_drift_monitor_never_train_or_refit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot = resolved_snapshot(
        tmp_path,
        4,
        principal_error=0.1,
        naive_error=1.0,
    )
    policy = DriftPolicy(review_window=3, consideration_window=4)

    def forbidden(*args, **kwargs):
        raise AssertionError("Drift monitoring attempted model training or refit")

    monkeypatch.setattr(
        "src.training.production_refit.refit_all_principal_models",
        forbidden,
    )
    monkeypatch.setattr(
        "src.training.train_lir.train_lir_for_evaluation",
        forbidden,
    )

    report = monitor_company_drift(snapshot, "ALI", policy=policy)

    assert report.report_for(ModelId.LAG_REGRESSION).status in {
        DriftStatus.OK,
        DriftStatus.WATCH,
        DriftStatus.DRIFT_SIGNAL,
    }
    assert report.as_dict()["automatic_training"] is False
    assert report.as_dict()["automatic_refit"] is False
