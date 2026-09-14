"""Versioned schemas for immutable formal-run evidence."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
import math
import re

from config.companies import get_company
from config.model_config import ModelId


FORMAL_SCHEMA_ID = "forecastph.formal-run"
FORMAL_SCHEMA_VERSION = 1
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")


class FormalSchemaError(ValueError):
    """Raised when formal evidence is incomplete or malformed."""


class FormalRunState(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    FINALIZED = "FINALIZED"


class ReadinessStatus(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise FormalSchemaError(
            "run_id must be 3-64 characters using letters, numbers, dot, hyphen, or underscore"
        )
    return run_id


@dataclass(frozen=True, slots=True)
class ReadinessIssue:
    code: str
    message: str
    severity: IssueSeverity
    symbol: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "symbol": self.symbol,
        }


@dataclass(frozen=True, slots=True)
class CorporateActionRecord:
    symbol: str
    action_date: date
    action_type: str
    source: str | None
    verified: bool
    notes: str | None = None

    def __post_init__(self) -> None:
        get_company(self.symbol)
        if not isinstance(self.verified, bool):
            raise FormalSchemaError("Corporate action verified status must be boolean")
        if not self.action_type.strip():
            raise FormalSchemaError("Corporate action type cannot be blank")
        if self.source is not None and not self.source.strip():
            raise FormalSchemaError("Corporate action source cannot be blank")
        if self.verified and self.source is None:
            raise FormalSchemaError(
                "A verified corporate action requires an external source"
            )
        if self.notes is not None and not self.notes.strip():
            raise FormalSchemaError("Corporate action notes cannot be blank")

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "date": self.action_date.isoformat(),
            "action_type": self.action_type,
            "source": self.source,
            "verified": self.verified,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class SessionCompleteness:
    symbol: str
    start_date: date
    cutoff_date: date
    expected_session_count: int
    actual_session_count: int
    missing_dates: tuple[date, ...]
    duplicate_dates: tuple[date, ...]
    unexpected_dates: tuple[date, ...]

    @property
    def complete(self) -> bool:
        return not (self.missing_dates or self.duplicate_dates or self.unexpected_dates)

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat(),
            "cutoff_date": self.cutoff_date.isoformat(),
            "expected_session_count": self.expected_session_count,
            "actual_session_count": self.actual_session_count,
            "missing_dates": [value.isoformat() for value in self.missing_dates],
            "duplicate_dates": [value.isoformat() for value in self.duplicate_dates],
            "unexpected_dates": [value.isoformat() for value in self.unexpected_dates],
            "complete": self.complete,
        }


@dataclass(frozen=True, slots=True)
class FormalReadinessReport:
    run_id: str
    cutoff_date: date
    checked_at: datetime
    issues: tuple[ReadinessIssue, ...]
    raw_provenance: tuple[Mapping[str, object], ...]
    session_completeness: tuple[SessionCompleteness, ...]
    git_state: Mapping[str, object]
    environment: Mapping[str, object]

    @property
    def status(self) -> ReadinessStatus:
        return (
            ReadinessStatus.NOT_READY
            if any(issue.severity is IssueSeverity.ERROR for issue in self.issues)
            else ReadinessStatus.READY
        )

    @property
    def ready(self) -> bool:
        return self.status is ReadinessStatus.READY

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_id": "forecastph.formal-readiness",
            "schema_version": FORMAL_SCHEMA_VERSION,
            "run_id": self.run_id,
            "cutoff_date": self.cutoff_date.isoformat(),
            "checked_at": self.checked_at.isoformat(),
            "status": self.status.value,
            "ready": self.ready,
            "issues": [issue.as_dict() for issue in self.issues],
            "git_state": dict(self.git_state),
            "environment": dict(self.environment),
            "raw_provenance": [dict(item) for item in self.raw_provenance],
            "session_completeness": [
                item.as_dict() for item in self.session_completeness
            ],
        }


def _validate_dates(values: Sequence[date], name: str, *, allow_empty: bool = False) -> None:
    dates = tuple(values)
    if not allow_empty and not dates:
        raise FormalSchemaError(f"{name} cannot be empty")
    if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
        raise FormalSchemaError(f"{name} must be unique and chronological")


@dataclass(frozen=True, slots=True)
class FormalCompanyEvidence:
    """Complete reproducibility payload for one company formal evaluation."""

    symbol: str
    development_target_dates: tuple[date, ...]
    holdout_target_dates: tuple[date, ...]
    cv_fold_target_date_manifests: Mapping[str, object]
    model_grids_and_seeds: Mapping[str, object]
    tuning_and_fold_scores: Mapping[str, object]
    selected_configurations: Mapping[str, object]
    lasso_boundary_metadata: Mapping[str, object]
    arima_diagnostics: Mapping[str, object]
    lstm_seed_epoch_metadata: Mapping[str, object]
    canonical_holdout_records: tuple[Mapping[str, object], ...]
    metrics: Mapping[str, Mapping[str, object]]
    statistical_tests: Mapping[str, object]

    def validate(self, *, allow_unresolved_lasso_boundary: bool = False) -> None:
        get_company(self.symbol)
        _validate_dates(self.development_target_dates, "development target dates")
        _validate_dates(self.holdout_target_dates, "holdout target dates")
        if self.development_target_dates[-1] >= self.holdout_target_dates[0]:
            raise FormalSchemaError("Development targets must precede holdout targets")
        required_models = {model.value for model in ModelId}
        if set(self.metrics) != required_models:
            raise FormalSchemaError("Formal metrics must contain all four methods")
        for model, values in self.metrics.items():
            required_metrics = {"rmse", "mae", "mase", "r2"}
            if not required_metrics <= set(values):
                raise FormalSchemaError(f"Formal metrics are incomplete for {model}")
            if any(
                isinstance(values[name], bool)
                or not isinstance(values[name], (int, float))
                or not math.isfinite(float(values[name]))
                for name in required_metrics
            ):
                raise FormalSchemaError(f"Formal metrics are invalid for {model}")
        record_dates: list[date] = []
        for record in self.canonical_holdout_records:
            try:
                if record["company"] != self.symbol:
                    raise FormalSchemaError(
                        "Canonical holdout record company is inconsistent"
                    )
                record_dates.append(date.fromisoformat(str(record["target_date"])))
                values = (
                    record["actual_close"],
                    record["lir_prediction"],
                    record["arima_prediction"],
                    record["lstm_prediction"],
                    record["naive_prediction"],
                )
                if any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    for value in values
                ):
                    raise FormalSchemaError(
                        "Canonical holdout prices must be finite numbers"
                    )
            except (KeyError, ValueError) as exc:
                raise FormalSchemaError(
                    "Canonical holdout record is incomplete or invalid"
                ) from exc
        if tuple(record_dates) != self.holdout_target_dates:
            raise FormalSchemaError(
                "Canonical holdout records must exactly match holdout target dates"
            )
        required_sections = {
            "cv_fold_target_date_manifests": self.cv_fold_target_date_manifests,
            "model_grids_and_seeds": self.model_grids_and_seeds,
            "tuning_and_fold_scores": self.tuning_and_fold_scores,
            "selected_configurations": self.selected_configurations,
            "arima_diagnostics": self.arima_diagnostics,
            "lstm_seed_epoch_metadata": self.lstm_seed_epoch_metadata,
            "statistical_tests": self.statistical_tests,
        }
        for name, section in required_sections.items():
            if not section:
                raise FormalSchemaError(f"{name} cannot be empty")
        boundary_flags = tuple(
            self.lasso_boundary_metadata.get(name)
            for name in ("lower", "upper", "interior")
        )
        if any(not isinstance(value, bool) for value in boundary_flags):
            raise FormalSchemaError("LASSO boundary flags must be boolean")
        if sum(boundary_flags) != 1:
            raise FormalSchemaError(
                "Exactly one LASSO boundary classification must be true"
            )
        if (
            not allow_unresolved_lasso_boundary
            and self.lasso_boundary_metadata.get("upper") is True
            and not self.lasso_boundary_metadata.get("resolution")
        ):
            raise FormalSchemaError(
                "Unresolved LASSO upper-bound winner prevents formal finalization"
            )

    def as_dict(self) -> dict[str, object]:
        self.validate(allow_unresolved_lasso_boundary=True)
        return {
            "symbol": self.symbol,
            "development_target_dates": [
                value.isoformat() for value in self.development_target_dates
            ],
            "holdout_target_dates": [
                value.isoformat() for value in self.holdout_target_dates
            ],
            "cv_fold_target_date_manifests": dict(self.cv_fold_target_date_manifests),
            "model_grids_and_seeds": dict(self.model_grids_and_seeds),
            "tuning_and_fold_scores": dict(self.tuning_and_fold_scores),
            "selected_configurations": dict(self.selected_configurations),
            "lasso_boundary_metadata": dict(self.lasso_boundary_metadata),
            "arima_diagnostics": dict(self.arima_diagnostics),
            "lstm_seed_epoch_metadata": dict(self.lstm_seed_epoch_metadata),
            "canonical_holdout_records": [
                dict(record) for record in self.canonical_holdout_records
            ],
            "metrics": {
                model: dict(values) for model, values in self.metrics.items()
            },
            "statistical_tests": dict(self.statistical_tests),
        }


def validate_company_evidence_payload(payload: Mapping[str, object]) -> None:
    """Validate archive JSON by reconstructing its typed company evidence."""

    try:
        evidence = FormalCompanyEvidence(
            symbol=str(payload["symbol"]),
            development_target_dates=tuple(
                date.fromisoformat(value)
                for value in payload["development_target_dates"]
            ),
            holdout_target_dates=tuple(
                date.fromisoformat(value) for value in payload["holdout_target_dates"]
            ),
            cv_fold_target_date_manifests=payload["cv_fold_target_date_manifests"],
            model_grids_and_seeds=payload["model_grids_and_seeds"],
            tuning_and_fold_scores=payload["tuning_and_fold_scores"],
            selected_configurations=payload["selected_configurations"],
            lasso_boundary_metadata=payload["lasso_boundary_metadata"],
            arima_diagnostics=payload["arima_diagnostics"],
            lstm_seed_epoch_metadata=payload["lstm_seed_epoch_metadata"],
            canonical_holdout_records=tuple(payload["canonical_holdout_records"]),
            metrics=payload["metrics"],
            statistical_tests=payload["statistical_tests"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FormalSchemaError("Malformed formal company evidence") from exc
    evidence.validate()
