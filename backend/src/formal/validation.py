"""Read-only formal readiness and PSE session-completeness validation."""

from collections import Counter
from collections.abc import Sequence
import csv
from datetime import date, timedelta
import json
from pathlib import Path

from config.companies import COMPANIES, Company
from config.model_config import DEFAULT_MODEL_CONFIG, ModelConfig
from config.settings import BACKEND_ROOT, SETTINGS, manila_now
from src.data.calendar import PSETradingCalendar
from src.data.validator import (
    OhlcvRecord,
    validate_and_sort_records,
    validate_required_columns,
)
from src.formal.provenance import (
    build_raw_provenance,
    capture_environment,
    capture_git_state,
    load_corporate_action_registry,
    load_provenance_registry,
)
from src.formal.schema import (
    FormalReadinessReport,
    FormalRunState,
    IssueSeverity,
    ReadinessIssue,
    SessionCompleteness,
    validate_run_id,
)
from src.models.arima import ArimaSpecification, candidate_specifications


DEFAULT_PROVENANCE_PATH = BACKEND_ROOT / "config" / "formal_provenance.json"
DEFAULT_CORPORATE_ACTIONS_PATH = BACKEND_ROOT / "config" / "corporate_actions.json"
DEFAULT_FORMAL_RUNS_ROOT = SETTINGS.artifacts_dir / "evaluations" / "formal-runs"


def analyze_session_completeness(
    symbol: str,
    raw_dates: Sequence[date],
    *,
    cutoff_date: date,
    calendar: PSETradingCalendar,
) -> SessionCompleteness:
    """Compare observed dates with the configured calendar without altering either."""

    if not raw_dates:
        raise ValueError("Session completeness requires at least one raw date")
    scoped_dates = tuple(value for value in raw_dates if value <= cutoff_date)
    if not scoped_dates:
        raise ValueError("No raw dates exist on or before the cutoff")
    start_date = min(scoped_dates)
    expected: list[date] = []
    candidate = start_date
    while candidate <= cutoff_date:
        if calendar.is_trading_day(candidate):
            expected.append(candidate)
        candidate += timedelta(days=1)
    counts = Counter(scoped_dates)
    actual_unique = set(scoped_dates)
    expected_set = set(expected)
    return SessionCompleteness(
        symbol=symbol,
        start_date=start_date,
        cutoff_date=cutoff_date,
        expected_session_count=len(expected),
        actual_session_count=len(actual_unique),
        missing_dates=tuple(sorted(expected_set - actual_unique)),
        duplicate_dates=tuple(
            sorted(value for value, count in counts.items() if count > 1)
        ),
        unexpected_dates=tuple(sorted(actual_unique - expected_set)),
    )


def _read_raw_rows(path: Path) -> list[dict[str, str | None]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        validate_required_columns(reader.fieldnames)
        return list(reader)


def _parse_raw_dates(rows: Sequence[dict[str, str | None]]) -> tuple[date, ...]:
    try:
        return tuple(date.fromisoformat(str(row.get("Date", ""))) for row in rows)
    except ValueError as exc:
        raise ValueError("Raw Date values must use valid YYYY-MM-DD dates") from exc


def read_raw_dates(path: Path) -> tuple[date, ...]:
    """Read source dates as stored, retaining duplicates for completeness checks."""

    return _parse_raw_dates(_read_raw_rows(path))


def read_raw_file(path: Path) -> tuple[tuple[OhlcvRecord, ...], tuple[date, ...]]:
    rows = _read_raw_rows(path)
    raw_dates = _parse_raw_dates(rows)
    return validate_and_sort_records(rows), raw_dates


def _existing_run_issue(run_id: str, formal_runs_root: Path) -> ReadinessIssue | None:
    directory = Path(formal_runs_root) / run_id
    if not directory.exists():
        return None
    state_path = directory / "state.json"
    state: object = "UNKNOWN"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")).get("state")
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    code = (
        "finalized_run_id_exists"
        if state == FormalRunState.FINALIZED.value
        else "run_id_exists"
    )
    return ReadinessIssue(
        code=code,
        message=f"Formal run ID already exists with state {state}",
        severity=IssueSeverity.ERROR,
    )


def _arima_grid_issue(model_config: ModelConfig) -> ReadinessIssue | None:
    specifications = candidate_specifications(model_config.arima)
    required_random_walk = ArimaSpecification((0, 1, 0), "n")
    if (
        len(specifications) != 80
        or len(set(specifications)) != 80
        or required_random_walk not in specifications
    ):
        return ReadinessIssue(
            code="invalid_arima_grid",
            message=(
                "ARIMA grid must contain 80 unique specifications including "
                "ARIMA(0,1,0), trend=n"
            ),
            severity=IssueSeverity.ERROR,
        )
    return None


def _lasso_boundary_issues(
    companies: Sequence[Company],
    artifacts_root: Path,
) -> tuple[ReadinessIssue, ...]:
    issues: list[ReadinessIssue] = []
    evidence_found = False
    for company in companies:
        path = Path(artifacts_root) / "evaluations" / "lir" / f"{company.symbol}.json"
        if not path.is_file():
            continue
        evidence_found = True
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            position = payload["tuning"]["alpha_grid_position"]
            upper = position["upper"]
            resolution = position.get("resolution")
        except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
            issues.append(
                ReadinessIssue(
                    code="invalid_lasso_boundary_evidence",
                    message="Existing LASSO boundary evidence is unreadable",
                    severity=IssueSeverity.WARNING,
                    symbol=company.symbol,
                )
            )
            continue
        if upper is True and not resolution:
            issues.append(
                ReadinessIssue(
                    code="unresolved_lasso_upper_boundary",
                    message=(
                        "Existing evaluation selected the largest configured LASSO alpha; "
                        "fresh formal tuning must resolve this before finalization"
                    ),
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
    if not evidence_found:
        issues.append(
            ReadinessIssue(
                code="lasso_boundary_pending_fresh_tuning",
                message=(
                    "No reusable LASSO selection is assumed; upper-bound status will be "
                    "checked from fresh formal tuning before finalization"
                ),
                severity=IssueSeverity.WARNING,
            )
        )
    return tuple(issues)


def assess_formal_readiness(
    run_id: str,
    cutoff_date: date,
    *,
    companies: Sequence[Company] = COMPANIES,
    raw_data_dir: Path = SETTINGS.raw_data_dir,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    provenance_path: Path = DEFAULT_PROVENANCE_PATH,
    corporate_actions_path: Path = DEFAULT_CORPORATE_ACTIONS_PATH,
    repository_root: Path = BACKEND_ROOT.parent,
    calendar: PSETradingCalendar | None = None,
    model_config: ModelConfig = DEFAULT_MODEL_CONFIG,
    artifacts_root: Path = SETTINGS.artifacts_dir,
    require_all_companies: bool = True,
) -> FormalReadinessReport:
    """Perform a read-only, fail-closed preflight for an explicit formal run."""

    validate_run_id(run_id)
    if not isinstance(cutoff_date, date):
        raise ValueError("cutoff_date must be an explicit date")
    selected_companies = tuple(companies)
    issues: list[ReadinessIssue] = []
    if require_all_companies and (
        len(selected_companies) != 15
        or {item.symbol for item in selected_companies}
        != {item.symbol for item in COMPANIES}
    ):
        issues.append(
            ReadinessIssue(
                code="configured_company_set_incomplete",
                message="Formal readiness requires all 15 configured companies",
                severity=IssueSeverity.ERROR,
            )
        )
    existing = _existing_run_issue(run_id, formal_runs_root)
    if existing is not None:
        issues.append(existing)
    arima_issue = _arima_grid_issue(model_config)
    if arima_issue is not None:
        issues.append(arima_issue)
    try:
        declared_sources = load_provenance_registry(provenance_path)
    except Exception as exc:
        declared_sources = {}
        issues.append(
            ReadinessIssue(
                code="invalid_provenance_registry",
                message=str(exc),
                severity=IssueSeverity.ERROR,
            )
        )
    try:
        load_corporate_action_registry(corporate_actions_path)
    except Exception as exc:
        issues.append(
            ReadinessIssue(
                code="invalid_corporate_action_registry",
                message=str(exc),
                severity=IssueSeverity.ERROR,
            )
        )

    session_calendar = calendar or PSETradingCalendar()
    raw_provenance: list[dict[str, object]] = []
    completeness: list[SessionCompleteness] = []
    for company in selected_companies:
        raw_path = Path(raw_data_dir) / company.raw_filename
        if not raw_path.is_file():
            issues.append(
                ReadinessIssue(
                    code="missing_raw_csv",
                    message=f"Raw CSV is missing: {raw_path}",
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
            continue
        try:
            raw_dates = read_raw_dates(raw_path)
        except Exception as exc:
            issues.append(
                ReadinessIssue(
                    code="invalid_raw_csv",
                    message=f"{type(exc).__name__}: {exc}",
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
            continue
        if cutoff_date not in set(raw_dates):
            issues.append(
                ReadinessIssue(
                    code="cutoff_not_in_raw_data",
                    message=f"Cutoff {cutoff_date} is not an observed raw date",
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
        try:
            session_result = analyze_session_completeness(
                company.symbol,
                raw_dates,
                cutoff_date=cutoff_date,
                calendar=session_calendar,
            )
        except ValueError as exc:
            issues.append(
                ReadinessIssue(
                    code="session_completeness_unavailable",
                    message=str(exc),
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
            continue
        completeness.append(session_result)
        if not session_result.complete:
            issues.append(
                ReadinessIssue(
                    code="trading_session_incomplete",
                    message=(
                        f"missing={len(session_result.missing_dates)} "
                        f"duplicates={len(session_result.duplicate_dates)} "
                        f"unexpected={len(session_result.unexpected_dates)}"
                    ),
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
        try:
            records, _ = read_raw_file(raw_path)
        except Exception as exc:
            issues.append(
                ReadinessIssue(
                    code="invalid_raw_csv",
                    message=f"{type(exc).__name__}: {exc}",
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
            continue
        try:
            provenance = build_raw_provenance(
                company,
                raw_path,
                records,
                declared_sources.get(company.symbol),
            )
        except Exception as exc:
            issues.append(
                ReadinessIssue(
                    code="invalid_provenance_entry",
                    message=f"{type(exc).__name__}: {exc}",
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
            continue
        raw_provenance.append(provenance.as_dict())
        for field in provenance.missing_required_fields:
            issues.append(
                ReadinessIssue(
                    code="missing_required_provenance",
                    message=f"Required provenance field is missing: {field}",
                    severity=IssueSeverity.ERROR,
                    symbol=company.symbol,
                )
            )
    issues.extend(_lasso_boundary_issues(selected_companies, artifacts_root))
    git_state = capture_git_state(repository_root)
    if git_state.dirty is True:
        issues.append(
            ReadinessIssue(
                code="dirty_git_worktree",
                message="Formal execution requires a clean Git worktree",
                severity=IssueSeverity.ERROR,
            )
        )
    if git_state.commit is None or git_state.dirty is None:
        issues.append(
            ReadinessIssue(
                code="git_state_unavailable",
                message=git_state.unavailable_reason or "Git state is unavailable",
                severity=IssueSeverity.ERROR,
            )
        )
    return FormalReadinessReport(
        run_id=run_id,
        cutoff_date=cutoff_date,
        checked_at=manila_now(),
        issues=tuple(issues),
        raw_provenance=tuple(raw_provenance),
        session_completeness=tuple(completeness),
        git_state=git_state.as_dict(),
        environment=capture_environment(),
    )
