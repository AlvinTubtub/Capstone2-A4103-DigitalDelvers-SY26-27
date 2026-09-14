"""Non-automating deployment-policy responses backed by prospective evidence."""

from dataclasses import dataclass
from enum import StrEnum

from config.model_config import ModelId
from src.monitoring.drift import CompanyDriftReport, DriftStatus


class DeploymentReviewStatus(StrEnum):
    INSUFFICIENT_PROSPECTIVE_EVIDENCE = "INSUFFICIENT_PROSPECTIVE_EVIDENCE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class DeploymentReview:
    symbol: str
    candidate: ModelId
    status: DeploymentReviewStatus
    approved: bool
    reason: str


def assess_deployment_candidate(
    report: CompanyDriftReport,
    candidate: ModelId,
) -> DeploymentReview:
    """Never promote automatically, including after favorable historical results."""

    method_report = report.report_for(candidate)
    if method_report.status is DriftStatus.INSUFFICIENT_DATA:
        return DeploymentReview(
            report.symbol,
            candidate,
            DeploymentReviewStatus.INSUFFICIENT_PROSPECTIVE_EVIDENCE,
            False,
            "Configured prospective review window has not been completed",
        )
    return DeploymentReview(
        report.symbol,
        candidate,
        DeploymentReviewStatus.MANUAL_REVIEW_REQUIRED,
        False,
        "Prospective evidence is reporting-only and cannot approve deployment",
    )
