"""Read-only composition of distinct ForecastPH evidence conclusions."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Final

from config.model_config import ModelId
from src.evaluation.model_selection import (
    PRINCIPAL_MODELS,
    RMSE_TIE_POLICY,
    CompanyModelSelection,
)
from src.evaluation.statistical_tests import (
    DMTestResult,
    LossType,
    WithinCompanyDMTests,
)
from src.monitoring.deployment_policy import (
    DeploymentReviewStatus,
    assess_deployment_candidate,
)
from src.monitoring.drift import CompanyDriftReport, DriftStatus


REPORTING_SEMANTICS_SCHEMA_ID: Final[str] = (
    "forecastph.company-evidence-conclusion"
)
REPORTING_SEMANTICS_SCHEMA_VERSION: Final[int] = 1
SIGNIFICANCE_DIRECTION_RULE: Final[str] = (
    "negative means principal lower loss than Naive"
)


class ReportingSemanticsError(ValueError):
    """Raised when evidence layers are incomplete, mismatched, or ambiguous."""


class SignificanceStatus(StrEnum):
    """Directional interpretation of one Holm-adjusted DM comparison."""

    SIGNIFICANTLY_BETTER = "SIGNIFICANTLY_BETTER"
    SIGNIFICANTLY_WORSE = "SIGNIFICANTLY_WORSE"
    NOT_SIGNIFICANT = "NOT_SIGNIFICANT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class DescriptiveHoldoutConclusion:
    """RMSE-only holdout reporting with no significance or deployment claim."""

    symbol: str
    best_principal_model: ModelId
    best_evaluated_method: ModelId
    best_principal_rmse: float
    best_evaluated_rmse: float
    naive_rmse: float
    best_principal_beats_naive_numerically: bool
    all_principals_worse_than_naive: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "scope": "frozen_chronological_holdout",
            "selection_metric": "rmse",
            "best_principal_model": self.best_principal_model.value,
            "best_evaluated_method": self.best_evaluated_method.value,
            "best_principal_rmse": self.best_principal_rmse,
            "best_evaluated_rmse": self.best_evaluated_rmse,
            "naive_rmse": self.naive_rmse,
            "best_principal_beats_naive_numerically": (
                self.best_principal_beats_naive_numerically
            ),
            # Preserve the existing name while making its numerical meaning explicit.
            "best_principal_beats_naive": (
                self.best_principal_beats_naive_numerically
            ),
            "all_principals_worse_than_naive": (
                self.all_principals_worse_than_naive
            ),
            "tie_policy": RMSE_TIE_POLICY,
            "interpretation": "descriptive_holdout_comparison_only",
        }


@dataclass(frozen=True, slots=True)
class DMSignificanceConclusion:
    """One principal-vs-Naive conclusion retaining its underlying DM evidence."""

    model: ModelId
    loss_type: LossType
    status: SignificanceStatus
    available: bool
    dm_statistic: float | None
    raw_p_value: float
    holm_adjusted_p_value: float
    alpha: float
    mean_loss_differential: float

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model.value,
            "benchmark": ModelId.NAIVE.value,
            "loss_type": self.loss_type.value,
            "status": self.status.value,
            "available": self.available,
            "dm_statistic": self.dm_statistic,
            "raw_p_value": self.raw_p_value,
            "holm_adjusted_p_value": self.holm_adjusted_p_value,
            "alpha": self.alpha,
            "mean_loss_differential": self.mean_loss_differential,
            "direction_rule": SIGNIFICANCE_DIRECTION_RULE,
            "multiple_testing_correction": "holm",
        }


@dataclass(frozen=True, slots=True)
class DescriptiveWinnerSignificance:
    """DM status of the descriptive winner without conflating the concepts."""

    descriptive_winner: ModelId
    squared_error_status: SignificanceStatus
    absolute_error_status: SignificanceStatus

    def as_dict(self) -> dict[str, object]:
        return {
            "descriptive_winner": self.descriptive_winner.value,
            "squared_error_status": self.squared_error_status.value,
            "absolute_error_status": self.absolute_error_status.value,
            "significantly_beats_naive_squared_loss": (
                self.squared_error_status
                is SignificanceStatus.SIGNIFICANTLY_BETTER
            ),
            "significantly_beats_naive_absolute_loss": (
                self.absolute_error_status
                is SignificanceStatus.SIGNIFICANTLY_BETTER
            ),
        }


@dataclass(frozen=True, slots=True)
class WithinCompanySignificanceConclusion:
    """Holm-adjusted within-company DM conclusions only."""

    symbol: str
    alpha: float
    comparisons: tuple[DMSignificanceConclusion, ...]
    descriptive_winner: DescriptiveWinnerSignificance

    def comparison_for(
        self,
        model: ModelId,
        loss_type: LossType,
    ) -> DMSignificanceConclusion:
        matches = tuple(
            item
            for item in self.comparisons
            if item.model is model and item.loss_type is loss_type
        )
        if len(matches) != 1:
            raise ReportingSemanticsError(
                f"Expected one significance conclusion for "
                f"{model.value}/{loss_type.value}"
            )
        return matches[0]

    def as_dict(self) -> dict[str, object]:
        by_model = {
            model.value: {
                loss_type.value: self.comparison_for(model, loss_type).as_dict()
                for loss_type in LossType
            }
            for model in PRINCIPAL_MODELS
        }
        return {
            "symbol": self.symbol,
            "evidence_source": "within_company_diebold_mariano_tests",
            "alpha": self.alpha,
            "classification_p_value": "holm_adjusted_p_value",
            "principal_vs_naive": by_model,
            "descriptive_winner": self.descriptive_winner.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ProductionDeploymentConclusion:
    """Truthful description of ForecastPH's three-model production architecture."""

    operational_model_families: tuple[ModelId, ...] = PRINCIPAL_MODELS

    def as_dict(self) -> dict[str, object]:
        return {
            "deployment_mode": "multi_model_principal_forecasting",
            "operational_model_families": [
                model.value for model in self.operational_model_families
            ],
            "single_approved_deployment_model": None,
            "approved_deployment_model": None,
            "approved_deployment_model_status": (
                "not_applicable_multi_model_production"
            ),
            "single_model_selection_applicable": False,
            "deployment_selection_basis": (
                "all three principal model families are independently refit and served"
            ),
            "historical_winner_auto_promotes": False,
            "statistical_significance_auto_promotes": False,
            "prospective_monitoring_auto_promotes": False,
            "automatic_promotion": False,
        }


@dataclass(frozen=True, slots=True)
class ProspectiveMethodConclusion:
    """Reporting-only deployment evidence for one principal model."""

    symbol: str
    model: ModelId
    resolved_session_count: int
    drift_status: DriftStatus
    review_window_required: int
    review_window_available: int
    consideration_window_required: int
    consideration_window_available: int
    prospective_validation_status: DeploymentReviewStatus
    deployment_approved: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "model": self.model.value,
            "evidence_source": "resolved_prospective_forecast_ledger_only",
            "resolved_session_count": self.resolved_session_count,
            "drift_status": self.drift_status.value,
            "review_window_required": self.review_window_required,
            "review_window_available": self.review_window_available,
            "consideration_window_required": self.consideration_window_required,
            "consideration_window_available": self.consideration_window_available,
            "prospective_validation_status": (
                self.prospective_validation_status.value
            ),
            "deployment_approved": self.deployment_approved,
            "automatic_action": None,
        }


@dataclass(frozen=True, slots=True)
class ProspectiveValidationConclusion:
    """Dynamic prospective conclusions sourced only from an existing drift report."""

    symbol: str
    methods: tuple[ProspectiveMethodConclusion, ...]

    def report_for(self, model: ModelId) -> ProspectiveMethodConclusion:
        matches = tuple(item for item in self.methods if item.model is model)
        if len(matches) != 1:
            raise ReportingSemanticsError(
                f"Expected one prospective conclusion for {model.value}"
            )
        return matches[0]

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "evidence_source": "resolved_prospective_forecast_ledger_only",
            "methods": {
                model.value: self.report_for(model).as_dict()
                for model in PRINCIPAL_MODELS
            },
        }


@dataclass(frozen=True, slots=True)
class CompanyEvidenceConclusion:
    """Four independent evidence layers for one company."""

    symbol: str
    descriptive_holdout: DescriptiveHoldoutConclusion
    statistical_significance: WithinCompanySignificanceConclusion
    production_deployment: ProductionDeploymentConclusion
    prospective_validation: ProspectiveValidationConclusion

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_id": REPORTING_SEMANTICS_SCHEMA_ID,
            "schema_version": REPORTING_SEMANTICS_SCHEMA_VERSION,
            "symbol": self.symbol,
            "descriptive_holdout": self.descriptive_holdout.as_dict(),
            "statistical_significance": self.statistical_significance.as_dict(),
            "production_deployment": self.production_deployment.as_dict(),
            "prospective_validation": self.prospective_validation.as_dict(),
        }


def _ranked_value(selection: CompanyModelSelection, model: ModelId) -> float:
    matches = tuple(
        item.value
        for item in selection.evaluated_ranking.ranked_models
        if item.model is model
    )
    if len(matches) != 1:
        raise ReportingSemanticsError(
            f"Evaluated ranking does not contain exactly one {model.value} result"
        )
    return float(matches[0])


def build_descriptive_holdout_conclusion(
    symbol: str,
    selection: CompanyModelSelection,
) -> DescriptiveHoldoutConclusion:
    """Reuse the authoritative selection object without reranking metrics."""

    if (
        selection.principal_ranking.criterion != "rmse"
        or selection.evaluated_ranking.criterion != "rmse"
    ):
        raise ReportingSemanticsError("Descriptive selection must be RMSE-based")
    principal = selection.principal_ranking.ranked_models[0]
    evaluated = selection.evaluated_ranking.ranked_models[0]
    return DescriptiveHoldoutConclusion(
        symbol=symbol,
        best_principal_model=selection.best_principal_model,
        best_evaluated_method=selection.best_evaluated_method,
        best_principal_rmse=float(principal.value),
        best_evaluated_rmse=float(evaluated.value),
        naive_rmse=_ranked_value(selection, ModelId.NAIVE),
        best_principal_beats_naive_numerically=(
            selection.best_principal_beats_naive
        ),
        all_principals_worse_than_naive=(
            selection.all_principals_worse_than_naive
        ),
    )


def classify_dm_significance(
    result: DMTestResult,
    *,
    alpha: float,
) -> SignificanceStatus:
    """Classify direction only from availability, adjusted p, and loss difference."""

    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise ReportingSemanticsError("DM alpha must be finite and between zero and one")
    if not result.available:
        return SignificanceStatus.UNAVAILABLE
    adjusted = float(result.holm_adjusted_p_value)
    if not math.isfinite(adjusted) or not 0.0 <= adjusted <= 1.0:
        raise ReportingSemanticsError("Holm-adjusted DM p-value is invalid")
    if adjusted > alpha:
        return SignificanceStatus.NOT_SIGNIFICANT
    differential = float(result.mean_loss_differential)
    if not math.isfinite(differential):
        raise ReportingSemanticsError("DM mean loss differential is invalid")
    if differential < 0.0:
        return SignificanceStatus.SIGNIFICANTLY_BETTER
    if differential > 0.0:
        return SignificanceStatus.SIGNIFICANTLY_WORSE
    return SignificanceStatus.NOT_SIGNIFICANT


def _principal_naive_dm_result(
    results: Sequence[DMTestResult],
    model: ModelId,
    loss_type: LossType,
) -> DMTestResult:
    matches = tuple(
        result
        for result in results
        if result.model_1 is model
        and result.model_2 is ModelId.NAIVE
        and result.loss_type is loss_type
    )
    if len(matches) != 1:
        raise ReportingSemanticsError(
            f"Expected one {loss_type.value} DM result for "
            f"{model.value} vs naive"
        )
    return matches[0]


def build_significance_conclusion(
    selection: CompanyModelSelection,
    dm_tests: WithinCompanyDMTests,
) -> WithinCompanySignificanceConclusion:
    """Interpret existing DM evidence without recalculating any statistic."""

    if not isinstance(dm_tests, WithinCompanyDMTests):
        raise ReportingSemanticsError(
            "Within-company significance requires WithinCompanyDMTests evidence"
        )
    comparisons: list[DMSignificanceConclusion] = []
    by_loss = {
        LossType.SQUARED_ERROR: dm_tests.squared_error,
        LossType.ABSOLUTE_ERROR: dm_tests.absolute_error,
    }
    for model in PRINCIPAL_MODELS:
        for loss_type in LossType:
            result = _principal_naive_dm_result(
                by_loss[loss_type],
                model,
                loss_type,
            )
            comparisons.append(
                DMSignificanceConclusion(
                    model=model,
                    loss_type=loss_type,
                    status=classify_dm_significance(result, alpha=dm_tests.alpha),
                    available=result.available,
                    dm_statistic=result.dm_statistic,
                    raw_p_value=float(result.raw_p_value),
                    holm_adjusted_p_value=float(result.holm_adjusted_p_value),
                    alpha=float(dm_tests.alpha),
                    mean_loss_differential=float(
                        result.mean_loss_differential
                    ),
                )
            )
    frozen = tuple(comparisons)
    winner = selection.best_principal_model
    statuses = {
        item.loss_type: item.status
        for item in frozen
        if item.model is winner
    }
    return WithinCompanySignificanceConclusion(
        symbol=dm_tests.company,
        alpha=float(dm_tests.alpha),
        comparisons=frozen,
        descriptive_winner=DescriptiveWinnerSignificance(
            descriptive_winner=winner,
            squared_error_status=statuses[LossType.SQUARED_ERROR],
            absolute_error_status=statuses[LossType.ABSOLUTE_ERROR],
        ),
    )


def build_production_deployment_conclusion() -> ProductionDeploymentConclusion:
    """Report the existing multi-model policy without selecting or promoting."""

    return ProductionDeploymentConclusion()


def build_prospective_validation_conclusion(
    drift_report: CompanyDriftReport,
) -> ProspectiveValidationConclusion:
    """Compose existing prospective drift and review outputs without side effects."""

    if not isinstance(drift_report, CompanyDriftReport):
        raise ReportingSemanticsError(
            "Prospective reporting requires an existing CompanyDriftReport"
        )
    methods: list[ProspectiveMethodConclusion] = []
    for model in PRINCIPAL_MODELS:
        method = drift_report.report_for(model)
        review = assess_deployment_candidate(drift_report, model)
        if review.approved:
            raise ReportingSemanticsError(
                "Current deployment policy must not automatically approve models"
            )
        methods.append(
            ProspectiveMethodConclusion(
                symbol=drift_report.symbol,
                model=model,
                resolved_session_count=method.resolved_session_count,
                drift_status=method.status,
                review_window_required=drift_report.policy.review_window,
                review_window_available=method.review_window.available_sessions,
                consideration_window_required=(
                    drift_report.policy.consideration_window
                ),
                consideration_window_available=(
                    method.consideration_window.available_sessions
                ),
                prospective_validation_status=review.status,
                deployment_approved=False,
            )
        )
    return ProspectiveValidationConclusion(
        symbol=drift_report.symbol,
        methods=tuple(methods),
    )


def build_company_evidence_conclusion(
    symbol: str,
    selection: CompanyModelSelection,
    dm_tests: WithinCompanyDMTests,
    drift_report: CompanyDriftReport,
) -> CompanyEvidenceConclusion:
    """Build four independent read-only sections from existing evidence objects."""

    if dm_tests.company != symbol or drift_report.symbol != symbol:
        raise ReportingSemanticsError("Evidence symbols do not match")
    return CompanyEvidenceConclusion(
        symbol=symbol,
        descriptive_holdout=build_descriptive_holdout_conclusion(
            symbol,
            selection,
        ),
        statistical_significance=build_significance_conclusion(
            selection,
            dm_tests,
        ),
        production_deployment=build_production_deployment_conclusion(),
        prospective_validation=build_prospective_validation_conclusion(
            drift_report
        ),
    )
