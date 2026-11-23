"""Configuration for official PSE EDGE End-of-Day report ingestion."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from config.companies import COMPANIES
from config.settings import SETTINGS


PSE_EDGE_REPORT_BASE_URL: Final[str] = "https://documents.pse.com.ph/market_report"
PSE_ARCHIVE_BASE_URL: Final[str] = "https://documents.pse.com.ph/wp-content/uploads/sites/15"
PDF_SUFFIX: Final[str] = "-EOD.pdf"
MAX_QUOTATION_PAGES: Final[int] = 11
EARLIEST_SUPPORTED_REPORT_DATE: Final[date] = date(2026, 7, 1)
EXTRACTED_COLUMNS: Final[tuple[str, ...]] = (
    "Date",
    "Issue Name",
    "Symbol",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Value",
)


@dataclass(frozen=True, slots=True)
class IngestionSettings:
    """Runtime settings that can be replaced in tests without global mutation."""

    reports_dir: Path = SETTINGS.backend_root / "data" / "pdf_reports"
    raw_dir: Path = SETTINGS.raw_data_dir
    base_url: str = PSE_EDGE_REPORT_BASE_URL
    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    max_quotation_pages: int = MAX_QUOTATION_PAGES
    archive_base_url: str = PSE_ARCHIVE_BASE_URL


DEFAULT_INGESTION_SETTINGS: Final[IngestionSettings] = IngestionSettings()


def configured_symbols() -> frozenset[str]:
    """Return the target universe from the authoritative company configuration."""

    return frozenset(company.symbol for company in COMPANIES)
