"""Load the frozen formal frontend evidence independently of live model artifacts."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path
from typing import Final

from config.companies import COMPANIES
from config.settings import BACKEND_ROOT


FORMAL_DISPLAY_SCHEMA_ID: Final[str] = "forecastph.formal-frontend-evidence"
FORMAL_DISPLAY_SCHEMA_VERSION: Final[int] = 1
DEFAULT_FORMAL_DISPLAY_PATH: Final[Path] = (
    BACKEND_ROOT / "data" / "formal_display" / "frozen_2026-09-11.json"
)
FORMAL_COMPANY_FIELDS: Final[tuple[str, ...]] = (
    "model",
    "metrics",
    "backtestDates",
    "backtestActual",
    "backtestByModel",
    "backtestMethodology",
    "evaluationMetadata",
    "bestPrincipalModel",
    "bestEvaluatedMethod",
    "bestPrincipalBeatsNaive",
    "allPrincipalsWorseThanNaive",
)
OPERATIONAL_METRICS_FIELDS: Final[frozenset[str]] = frozenset(
    {"generatedAt", "forecastDate", "lastRunAt", "status"}
)


class FormalDisplayError(ValueError):
    """Raised when frozen formal frontend evidence is incomplete or malformed."""


@dataclass(frozen=True, slots=True)
class FormalDisplaySnapshot:
    source_commit: str
    formal_end_date: date
    companies: dict[str, dict[str, object]]
    metrics_static: dict[str, object]

    def company(self, symbol: str) -> dict[str, object]:
        try:
            return deepcopy(self.companies[symbol])
        except KeyError as exc:
            raise FormalDisplayError(f"Missing frozen formal company: {symbol}") from exc

    def static_metrics(self) -> dict[str, object]:
        return deepcopy(self.metrics_static)


def load_formal_display_snapshot(
    path: Path = DEFAULT_FORMAL_DISPLAY_PATH,
) -> FormalDisplaySnapshot:
    """Load and fail-closed validate the immutable formal presentation snapshot."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalDisplayError(f"Cannot read frozen formal display evidence: {path}") from exc
    if not isinstance(payload, dict) or (
        payload.get("schema_id") != FORMAL_DISPLAY_SCHEMA_ID
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != FORMAL_DISPLAY_SCHEMA_VERSION
    ):
        raise FormalDisplayError("Frozen formal display identity is incompatible")
    source_commit = payload.get("source_commit")
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise FormalDisplayError("Frozen formal source commit is invalid")
    try:
        formal_end = date.fromisoformat(payload["formal_end_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FormalDisplayError("Frozen formal end date is invalid") from exc
    if payload.get("full_session_count") != 246 or payload.get("displayed_session_count") != 60:
        raise FormalDisplayError("Frozen formal session counts are invalid")
    companies = payload.get("companies")
    expected_symbols = {company.symbol for company in COMPANIES}
    if not isinstance(companies, dict) or set(companies) != expected_symbols:
        raise FormalDisplayError("Frozen formal company universe is incomplete")
    for symbol, evidence in companies.items():
        if not isinstance(evidence, dict) or set(evidence) != set(FORMAL_COMPANY_FIELDS):
            raise FormalDisplayError(f"Frozen formal fields are invalid for {symbol}")
        metadata = evidence.get("evaluationMetadata")
        dates = evidence.get("backtestDates")
        actual = evidence.get("backtestActual")
        by_model = evidence.get("backtestByModel")
        metrics = evidence.get("metrics")
        if (
            not isinstance(metadata, dict)
            or metadata.get("fullSessionCount") != 246
            or metadata.get("displayedSessionCount") != 60
            or metadata.get("fullEndDate") != formal_end.isoformat()
            or not isinstance(dates, list)
            or len(dates) != 60
            or dates != sorted(dates)
            or len(set(dates)) != 60
            or dates[-1] != formal_end.isoformat()
            or not isinstance(actual, list)
            or len(actual) != 60
            or not isinstance(by_model, dict)
            or set(by_model)
            != {"Lag-Informed Regression", "ARIMA", "LSTM", "Naive baseline"}
            or any(not isinstance(values, list) or len(values) != 60 for values in by_model.values())
            or not isinstance(metrics, dict)
        ):
            raise FormalDisplayError(f"Frozen formal evidence is incomplete for {symbol}")
        numeric_values = [*actual, *(value for values in by_model.values() for value in values)]
        if any(type(value) not in {int, float} or not math.isfinite(value) for value in numeric_values):
            raise FormalDisplayError(f"Frozen formal chart values are invalid for {symbol}")
    metrics_static = payload.get("metrics_static")
    if not isinstance(metrics_static, dict) or set(metrics_static) & OPERATIONAL_METRICS_FIELDS:
        raise FormalDisplayError("Frozen metrics must exclude operational timestamps/status")
    per_company = metrics_static.get("perCompany")
    if not isinstance(per_company, dict) or set(per_company) != expected_symbols:
        raise FormalDisplayError("Frozen metrics company universe is incomplete")
    for symbol, evidence in companies.items():
        company_metrics = per_company[symbol]
        if not isinstance(company_metrics, dict) or (
            company_metrics.get("metrics") != evidence["metrics"]
            or company_metrics.get("evaluationMetadata") != evidence["evaluationMetadata"]
            or company_metrics.get("bestPrincipalModel") != evidence["bestPrincipalModel"]
            or company_metrics.get("bestEvaluatedMethod") != evidence["bestEvaluatedMethod"]
            or company_metrics.get("bestPrincipalBeatsNaive")
            != evidence["bestPrincipalBeatsNaive"]
            or company_metrics.get("allPrincipalsWorseThanNaive")
            != evidence["allPrincipalsWorseThanNaive"]
        ):
            raise FormalDisplayError(f"Frozen metrics disagree for {symbol}")
    return FormalDisplaySnapshot(
        source_commit=source_commit,
        formal_end_date=formal_end,
        companies=deepcopy(companies),
        metrics_static=deepcopy(metrics_static),
    )
