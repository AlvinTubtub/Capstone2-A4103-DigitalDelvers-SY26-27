"""Read-only validation of the complete generated frontend forecast tree."""

import json
import logging
from pathlib import Path

from config.companies import COMPANIES
from src.export.frontend_exporter import FRONTEND_FORECASTS_DIR
from src.export.schemas import FrontendSchemaError, validate_document


LOGGER = logging.getLogger(__name__)


class FrontendForecastValidationError(RuntimeError):
    """Raised when generated frontend forecast JSON is missing or invalid."""


def operational_forecast_paths() -> tuple[str, ...]:
    return (
        "manifest.json",
        "companies.json",
        "dashboard.json",
        "latest.json",
        "metrics.json",
        *(f"company/{company.symbol}.json" for company in COMPANIES),
        *(f"history/{company.symbol}.json" for company in COMPANIES),
    )


def _reject_nonstandard_number(value: str) -> None:
    raise FrontendForecastValidationError(
        f"Non-standard JSON number is forbidden: {value}"
    )


def load_strict_json(path: Path) -> object:
    """Load RFC-compatible JSON while rejecting Python's NaN/Infinity extension."""

    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source, parse_constant=_reject_nonstandard_number)
    except FrontendForecastValidationError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise FrontendForecastValidationError(f"Invalid JSON file: {path}") from exc


def validate_frontend_forecasts(
    output_root: Path = FRONTEND_FORECASTS_DIR,
) -> tuple[Path, ...]:
    """Validate every JSON file and every required operational document."""

    root = Path(output_root).resolve()
    expected = operational_forecast_paths()
    missing = [relative for relative in expected if not (root / relative).is_file()]
    if missing:
        raise FrontendForecastValidationError(
            f"Frontend forecast export is incomplete; missing={missing}"
        )
    json_files = tuple(sorted(root.glob("**/*.json")))
    if not json_files:
        raise FrontendForecastValidationError("No frontend forecast JSON files found")
    decoded = {path: load_strict_json(path) for path in json_files}
    try:
        for relative in expected:
            validate_document(relative, decoded[root / relative])
    except (FrontendSchemaError, KeyError, TypeError) as exc:
        raise FrontendForecastValidationError(
            "Frontend forecast export violates the compatibility contract"
        ) from exc

    configured = {company.symbol for company in COMPANIES}
    manifest = decoded[root / "manifest.json"]
    companies = decoded[root / "companies.json"]
    dashboard = decoded[root / "dashboard.json"]
    latest = decoded[root / "latest.json"]
    metrics = decoded[root / "metrics.json"]
    if (
        not isinstance(manifest, dict)
        or manifest.get("expectedCompanyCount") != len(COMPANIES)
        or not isinstance(companies, list)
        or {item.get("symbol") for item in companies if isinstance(item, dict)}
        != configured
        or not isinstance(metrics, dict)
        or set(metrics.get("perCompany", {})) != configured
    ):
        raise FrontendForecastValidationError(
            "Frontend summary documents do not contain the configured company universe"
        )
    if not (
        manifest.get("forecastDate")
        == dashboard.get("forecastDate")
        == latest.get("forecastDate")
        == metrics.get("forecastDate")
    ):
        raise FrontendForecastValidationError(
            "Frontend operational documents disagree on forecastDate"
        )
    if not (
        manifest.get("generatedAt")
        == dashboard.get("generatedAt")
        == latest.get("generatedAt")
        == metrics.get("generatedAt")
    ):
        raise FrontendForecastValidationError(
            "Frontend operational documents disagree on generatedAt"
        )
    for symbol in configured:
        company = decoded[root / "company" / f"{symbol}.json"]
        history = decoded[root / "history" / f"{symbol}.json"]
        if history.get("ohlcv") != company.get("ohlcv"):
            raise FrontendForecastValidationError(
                f"Company and history OHLCV disagree for {symbol}"
            )
    LOGGER.info(
        "Validated frontend forecast JSON files=%d operational_documents=%d",
        len(json_files),
        len(expected),
    )
    return json_files
