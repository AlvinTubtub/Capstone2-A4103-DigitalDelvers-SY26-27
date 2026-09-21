"""Four-layer reporting semantics remain explicit and causally independent."""

from datetime import date, datetime, timedelta
import json
from zoneinfo import ZoneInfo

import pytest

from config.ledger_config import DEFAULT_DRIFT_POLICY, DriftPolicy
from config.model_config import ModelId
from src.evaluation.metrics import EvaluationMetrics
from src.evaluation.model_selection import (
    RMSE_TIE_POLICY,
    PrincipalsUnderperformNaiveWarning,
    select_company_models,
)
from src.evaluation.reporting_semantics import (
    ReportingSemanticsError,
    SignificanceStatus,
    build_company_evidence_conclusion,
    build_descriptive_holdout_conclusion,
    build_production_deployment_conclusion,
    build_prospective_validation_conclusion,
    build_significance_conclusion,
    classify_dm_significance,
)
from src.evaluation.statistical_tests import (
    DMTestResult,
    LossType,
    WithinCompanyDMTests,
)
from src.ledger.materializer import materialize_events
from src.ledger.schema import (
    NAIVE_MODEL_VERSION,
    ForecastIssued,
    ForecastOutcomeObserved,
)
from src.monitoring.deployment_policy import DeploymentReviewStatus
from src.monitoring.drift import (
    CompanyDriftReport,
    DriftStatus,
    MethodDriftReport,
    RollingPerformance,
    monitor_company_drift,
)


MANILA = ZoneInfo("Asia/Manila")


def metric(rmse: float) -> EvaluationMetrics:
    return EvaluationMetrics(
        rmse=rmse,
        mae=rmse,
        mase=rmse,
        r2=-1.0,
        observations=40,
    )


def selection_metrics(
    *,
    lir: float = 1.0,
    arima: float = 2.0,
    lstm: float = 3.0,
    naive: float = 1.5,
) -> dict[ModelId, EvaluationMetrics]:
    return {
        ModelId.LAG_REGRESSION: metric(lir),
        ModelId.ARIMA: metric(arima),
        ModelId.LSTM: metric(lstm),
        ModelId.NAIVE: metric(naive),
    }


def dm_result(
    model: ModelId,
    loss_type: LossType,
    *,
    adjusted_p: float = 0.5,
    raw_p: float = 0.5,
    differential: float = -1.0,
    available: bool = True,
) -> DMTestResult:
    return DMTestResult(
        model_1=model,
        model_2=ModelId.NAIVE,
        loss_type=loss_type,
        sample_size=40,
        dm_statistic=-1.25 if available else None,
        raw_p_value=raw_p,
        holm_adjusted_p_value=adjusted_p,
        reject=available and adjusted_p <= 0.05,
        hac_lag=3,
        forecast_horizon=1,
        hln_correction_factor=0.98,
        mean_loss_differential=differential,
        long_run_variance=1.0 if available else 0.0,
        available=available,
        unavailable_reason=None if available else "degenerate test fixture",
    )


def dm_suite(
    overrides: dict[tuple[ModelId, LossType], dict[str, object]] | None = None,
) -> WithinCompanyDMTests:
    configured = overrides or {}

    def family(loss_type: LossType) -> tuple[DMTestResult, ...]:
        return tuple(
            dm_result(
                model,
                loss_type,
                **configured.get((model, loss_type), {}),
            )
            for model in (
                ModelId.LAG_REGRESSION,
                ModelId.ARIMA,
                ModelId.LSTM,
            )
        )

    return WithinCompanyDMTests(
        company="ALI",
        alpha=0.05,
        squared_error=family(LossType.SQUARED_ERROR),
        absolute_error=family(LossType.ABSOLUTE_ERROR),
    )


def rolling(window: int, available: int) -> RollingPerformance:
    return RollingPerformance(
        window=window,
        available_sessions=available,
        start_target_date="2026-01-02" if available else None,
        end_target_date="2026-01-31" if available else None,
        rolling_mae=1.0 if available else None,
        rolling_bias=0.1 if available else None,
        naive_rolling_mae=1.2 if available else None,
        mae_ratio_to_naive=(1.0 / 1.2) if available else None,
        win_count_vs_naive=available,
        win_proportion_vs_naive=1.0 if available else None,
    )


def drift_report(
    status: DriftStatus,
    *,
    count: int,
    policy: DriftPolicy = DEFAULT_DRIFT_POLICY,
) -> CompanyDriftReport:
    methods = tuple(
        MethodDriftReport(
            symbol="ALI",
            method=model,
            status=status,
            resolved_session_count=count,
            review_window=rolling(policy.review_window, min(count, policy.review_window)),
            consideration_window=rolling(
                policy.consideration_window,
                min(count, policy.consideration_window),
            ),
            reasons=("test reporting evidence",),
        )
        for model in (
            ModelId.LAG_REGRESSION,
            ModelId.ARIMA,
            ModelId.LSTM,
        )
    )
    return CompanyDriftReport("ALI", status, policy, methods)


def test_descriptive_conclusion_reuses_existing_winners_and_tie_policy() -> None:
    with pytest.warns(PrincipalsUnderperformNaiveWarning):
        naive_best = select_company_models(
            selection_metrics(lir=2.0, arima=1.0, lstm=3.0, naive=0.5)
        )
    conclusion = build_descriptive_holdout_conclusion("ALI", naive_best)

    assert conclusion.best_principal_model is naive_best.best_principal_model
    assert conclusion.best_evaluated_method is ModelId.NAIVE
    assert conclusion.best_principal_beats_naive_numerically is (
        naive_best.best_principal_beats_naive
    )
    assert conclusion.as_dict()["tie_policy"] == RMSE_TIE_POLICY
    assert not any("signific" in key for key in conclusion.as_dict())

    tied = select_company_models(
        selection_metrics(lir=1.0, arima=1.0, lstm=1.0, naive=1.0)
    )
    tied_conclusion = build_descriptive_holdout_conclusion("ALI", tied)
    assert tied_conclusion.best_principal_model is ModelId.LAG_REGRESSION
    assert tied_conclusion.best_evaluated_method is ModelId.LAG_REGRESSION


def test_dm_classification_uses_adjusted_p_and_direction() -> None:
    assert classify_dm_significance(
        dm_result(
            ModelId.LAG_REGRESSION,
            LossType.SQUARED_ERROR,
            adjusted_p=0.01,
            differential=-0.5,
        ),
        alpha=0.05,
    ) is SignificanceStatus.SIGNIFICANTLY_BETTER
    assert classify_dm_significance(
        dm_result(
            ModelId.ARIMA,
            LossType.SQUARED_ERROR,
            adjusted_p=0.01,
            differential=0.5,
        ),
        alpha=0.05,
    ) is SignificanceStatus.SIGNIFICANTLY_WORSE
    assert classify_dm_significance(
        dm_result(
            ModelId.LSTM,
            LossType.SQUARED_ERROR,
            raw_p=0.001,
            adjusted_p=0.20,
            differential=-0.5,
        ),
        alpha=0.05,
    ) is SignificanceStatus.NOT_SIGNIFICANT
    assert classify_dm_significance(
        dm_result(
            ModelId.LSTM,
            LossType.ABSOLUTE_ERROR,
            available=False,
        ),
        alpha=0.05,
    ) is SignificanceStatus.UNAVAILABLE


def test_significance_keeps_loss_families_and_all_principals_separate() -> None:
    selection = select_company_models(selection_metrics())
    evidence = dm_suite(
        {
            (ModelId.LAG_REGRESSION, LossType.SQUARED_ERROR): {
                "raw_p": 0.001,
                "adjusted_p": 0.20,
                "differential": -1.0,
            },
            (ModelId.LAG_REGRESSION, LossType.ABSOLUTE_ERROR): {
                "adjusted_p": 0.01,
                "differential": -1.0,
            },
            (ModelId.ARIMA, LossType.SQUARED_ERROR): {
                "adjusted_p": 0.01,
                "differential": 1.0,
            },
            (ModelId.ARIMA, LossType.ABSOLUTE_ERROR): {
                "available": False,
            },
        }
    )

    conclusion = build_significance_conclusion(selection, evidence)

    assert len(conclusion.comparisons) == 6
    assert {
        comparison.model for comparison in conclusion.comparisons
    } == {
        ModelId.LAG_REGRESSION,
        ModelId.ARIMA,
        ModelId.LSTM,
    }
    assert conclusion.comparison_for(
        ModelId.LAG_REGRESSION,
        LossType.SQUARED_ERROR,
    ).status is SignificanceStatus.NOT_SIGNIFICANT
    assert conclusion.comparison_for(
        ModelId.LAG_REGRESSION,
        LossType.ABSOLUTE_ERROR,
    ).status is SignificanceStatus.SIGNIFICANTLY_BETTER
    assert conclusion.comparison_for(
        ModelId.ARIMA,
        LossType.SQUARED_ERROR,
    ).status is SignificanceStatus.SIGNIFICANTLY_WORSE
    assert conclusion.comparison_for(
        ModelId.ARIMA,
        LossType.ABSOLUTE_ERROR,
    ).status is SignificanceStatus.UNAVAILABLE
    assert selection.best_principal_model is ModelId.LAG_REGRESSION
    json.dumps(conclusion.as_dict(), allow_nan=False)


def test_lower_rmse_does_not_create_statistical_superiority() -> None:
    selection = select_company_models(selection_metrics(lir=1.0, naive=2.0))
    conclusion = build_significance_conclusion(selection, dm_suite())
    winner = conclusion.descriptive_winner

    assert selection.best_principal_beats_naive
    assert winner.descriptive_winner is ModelId.LAG_REGRESSION
    assert winner.squared_error_status is SignificanceStatus.NOT_SIGNIFICANT
    assert winner.absolute_error_status is SignificanceStatus.NOT_SIGNIFICANT
    assert not winner.as_dict()["significantly_beats_naive_squared_loss"]
    assert not winner.as_dict()["significantly_beats_naive_absolute_loss"]


def test_sign_test_style_evidence_cannot_create_dm_significance() -> None:
    selection = select_company_models(selection_metrics())

    with pytest.raises(ReportingSemanticsError, match="WithinCompanyDMTests"):
        build_significance_conclusion(  # type: ignore[arg-type]
            selection,
            {
                "sign_test": {
                    "raw_p_value": 0.001,
                    "role": "supplementary_robustness_only",
                }
            },
        )


def test_production_conclusion_truthfully_reports_multi_model_operation() -> None:
    payload = build_production_deployment_conclusion().as_dict()

    assert payload["operational_model_families"] == ["lag_reg", "arima", "lstm"]
    assert "naive" not in payload["operational_model_families"]
    assert payload["single_approved_deployment_model"] is None
    assert payload["approved_deployment_model"] is None
    assert payload["approved_deployment_model_status"] == (
        "not_applicable_multi_model_production"
    )
    assert payload["historical_winner_auto_promotes"] is False
    assert payload["statistical_significance_auto_promotes"] is False
    assert payload["prospective_monitoring_auto_promotes"] is False
    assert payload["automatic_promotion"] is False


@pytest.mark.parametrize(
    ("status", "count", "expected_review"),
    [
        (
            DriftStatus.INSUFFICIENT_DATA,
            19,
            DeploymentReviewStatus.INSUFFICIENT_PROSPECTIVE_EVIDENCE,
        ),
        (DriftStatus.OK, 20, DeploymentReviewStatus.MANUAL_REVIEW_REQUIRED),
        (DriftStatus.WATCH, 20, DeploymentReviewStatus.MANUAL_REVIEW_REQUIRED),
        (
            DriftStatus.DRIFT_SIGNAL,
            60,
            DeploymentReviewStatus.MANUAL_REVIEW_REQUIRED,
        ),
    ],
)
def test_prospective_status_reuses_existing_policy_without_approval(
    status: DriftStatus,
    count: int,
    expected_review: DeploymentReviewStatus,
) -> None:
    policy = DriftPolicy(review_window=20, consideration_window=60)
    conclusion = build_prospective_validation_conclusion(
        drift_report(status, count=count, policy=policy)
    )

    for model in (ModelId.LAG_REGRESSION, ModelId.ARIMA, ModelId.LSTM):
        method = conclusion.report_for(model)
        assert method.drift_status is status
        assert method.prospective_validation_status is expected_review
        assert method.review_window_required == policy.review_window
        assert method.consideration_window_required == policy.consideration_window
        assert method.deployment_approved is False
        assert method.as_dict()["automatic_action"] is None


def test_pending_and_nonledger_backfill_cannot_enter_prospective_conclusion() -> None:
    target = date(2026, 9, 15)
    origin = target - timedelta(days=1)
    created = datetime(2026, 9, 14, 16, 0, tzinfo=MANILA)
    observed = datetime(2026, 9, 15, 16, 0, tzinfo=MANILA)
    issuances = tuple(
        ForecastIssued.create(
            created_at=created,
            symbol="ALI",
            origin_date=origin,
            target_date=target,
            method=model,
            model_version=(
                NAIVE_MODEL_VERSION if model is ModelId.NAIVE else f"version-{model.value}"
            ),
            prediction=101.0,
        )
        for model in ModelId
    )
    outcomes = tuple(
        ForecastOutcomeObserved.create(
            issuance,
            observed_at=observed,
            actual_close=100.0,
        )
        for issuance in issuances
    )
    pending = ForecastIssued.create(
        created_at=observed,
        symbol="ALI",
        origin_date=target,
        target_date=target + timedelta(days=1),
        method=ModelId.LAG_REGRESSION,
        model_version="version-lag_reg",
        prediction=999.0,
    )
    snapshot = materialize_events(issuances + outcomes + (pending,))
    report = monitor_company_drift(snapshot, "ALI")
    conclusion = build_prospective_validation_conclusion(report)

    assert conclusion.report_for(
        ModelId.LAG_REGRESSION
    ).resolved_session_count == 1
    assert len(snapshot.pending) == 1
    with pytest.raises(ReportingSemanticsError, match="CompanyDriftReport"):
        build_prospective_validation_conclusion(  # type: ignore[arg-type]
            {"source": "post_formal_backfill", "target_date": "2026-09-14"}
        )


def test_critical_cross_layer_case_preserves_four_independent_truths() -> None:
    selection = select_company_models(selection_metrics(lir=1.0, naive=1.5))
    combined = build_company_evidence_conclusion(
        "ALI",
        selection,
        dm_suite(),
        drift_report(DriftStatus.WATCH, count=20),
    )
    payload = combined.as_dict()

    assert payload["descriptive_holdout"]["best_principal_model"] == "lag_reg"
    assert payload["statistical_significance"]["descriptive_winner"][
        "squared_error_status"
    ] == "NOT_SIGNIFICANT"
    assert payload["production_deployment"]["operational_model_families"] == [
        "lag_reg",
        "arima",
        "lstm",
    ]
    assert payload["production_deployment"][
        "single_approved_deployment_model"
    ] is None
    prospective = payload["prospective_validation"]["methods"]["lag_reg"]
    assert prospective["drift_status"] == "WATCH"
    assert prospective["deployment_approved"] is False
    json.dumps(payload, allow_nan=False)


def test_report_composition_cannot_train_refit_or_deploy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Reporting attempted an operational action")

    monkeypatch.setattr(
        "src.training.production_refit.refit_all_principal_models",
        forbidden,
    )
    monkeypatch.setattr(
        "src.training.train_lir.train_lir_for_evaluation",
        forbidden,
    )
    combined = build_company_evidence_conclusion(
        "ALI",
        select_company_models(selection_metrics()),
        dm_suite(),
        drift_report(DriftStatus.OK, count=20),
    )

    assert combined.production_deployment.as_dict()["automatic_promotion"] is False
    assert all(
        not item.deployment_approved
        for item in combined.prospective_validation.methods
    )
