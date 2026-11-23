"""Ingestion-only orchestration from PSE EDGE reports to canonical raw CSVs."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import logging
from pathlib import Path

from config.settings import as_manila_time, manila_now
from src.data.calendar import PSETradingCalendar
from src.ingestion.config import (
    DEFAULT_INGESTION_SETTINGS,
    EARLIEST_SUPPORTED_REPORT_DATE,
    IngestionSettings,
    configured_symbols,
)
from src.ingestion.downloader import DownloadResult, download_reports, report_sources
from src.ingestion.merger import MergeSummary, merge_into_raw, validate_raw_file
from src.ingestion.parser import ParseBatchResult, parse_reports, report_date_from_filename
from src.ingestion.validator import validate_extracted_quotes


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionResult:
    requested_start_date: date
    requested_end_date: date
    downloaded_reports: list[Path] = field(default_factory=list)
    already_present_reports: list[Path] = field(default_factory=list)
    unpublished_dates: list[date] = field(default_factory=list)
    failed_downloads: list[tuple[date, str]] = field(default_factory=list)
    parsed_reports: list[Path] = field(default_factory=list)
    parse_errors: list[tuple[Path, str]] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    merge_summaries: list[MergeSummary] = field(default_factory=list)
    validation_status: str = "not_run"
    errors: list[str] = field(default_factory=list)

    @property
    def rows_added(self) -> int:
        return sum(item.rows_added for item in self.merge_summaries)

    @property
    def companies_updated(self) -> tuple[str, ...]:
        return tuple(item.symbol for item in self.merge_summaries if item.rows_added > 0)

    @property
    def successful(self) -> bool:
        return not self.failed_downloads and not self.parse_errors and not self.errors


DownloadFunction = Callable[..., DownloadResult]
ParseFunction = Callable[..., ParseBatchResult]


def latest_raw_date(raw_dir: Path) -> date | None:
    """Find the newest valid date across configured canonical raw files."""

    latest: date | None = None
    for symbol in sorted(configured_symbols()):
        path = raw_dir / f"{symbol}.csv"
        if not path.exists():
            continue
        records = validate_raw_file(path)
        candidate = records[-1].trading_date
        latest = candidate if latest is None or candidate > latest else latest
    return latest


def resolve_date_range(
    *,
    raw_dir: Path,
    start_date: date | None,
    end_date: date | None,
    now: datetime | None = None,
) -> tuple[date, date]:
    """Resolve missing bounds using raw history and the current Philippine date."""

    current_date = (as_manila_time(now) if now is not None else manila_now()).date()
    effective_end = end_date or current_date
    if start_date is not None:
        effective_start = start_date
    else:
        latest = latest_raw_date(raw_dir)
        effective_start = (
            latest + timedelta(days=1) if latest is not None else EARLIEST_SUPPORTED_REPORT_DATE
        )
    return effective_start, effective_end


def run_ingestion(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    settings: IngestionSettings = DEFAULT_INGESTION_SETTINGS,
    now: datetime | None = None,
    download_function: DownloadFunction = download_reports,
    parse_function: ParseFunction = parse_reports,
) -> IngestionResult:
    """Run only EOD ingestion. No forecasting package is imported or invoked."""

    effective_start, effective_end = resolve_date_range(
        raw_dir=settings.raw_dir,
        start_date=start_date,
        end_date=end_date,
        now=now,
    )
    result = IngestionResult(effective_start, effective_end)
    LOGGER.info(
        "EOD ingestion started start_date=%s end_date=%s",
        effective_start,
        effective_end,
    )
    if effective_start > effective_end:
        result.validation_status = "not_required_up_to_date"
        LOGGER.info("EOD ingestion is already current; no dates requested")
        return result

    try:
        downloads = download_function(
            effective_start,
            effective_end,
            settings=settings,
        )
        result.downloaded_reports.extend(downloads.downloaded)
        result.already_present_reports.extend(downloads.already_present)
        result.unpublished_dates.extend(downloads.unpublished)
        result.failed_downloads.extend(downloads.failed)

        available = downloads.available_reports
        if not available:
            if result.failed_downloads:
                result.validation_status = "failed"
                result.errors.append("One or more requested reports failed to download")
            else:
                result.validation_status = "not_required_no_published_reports"
            return result

        parsed = parse_function(available, settings=settings)
        result.parsed_reports.extend(parsed.parsed_reports)
        result.parse_errors.extend(parsed.errors)
        result.parse_warnings.extend(parsed.warnings)
        if result.failed_downloads:
            result.errors.append("One or more requested reports failed to download")
        if result.parse_errors:
            result.errors.append("One or more available reports failed to parse")

        available_dates = tuple(
            day for path in available if (day := report_date_from_filename(path)) is not None
        )
        if available_dates:
            latest_available = max(available_dates)
            calendar = PSETradingCalendar()
            for missing in sorted(downloads.unpublished):
                if (
                    effective_start <= missing < latest_available <= effective_end
                    and calendar.is_trading_day(missing)
                ):
                    sources = ", ".join(
                        f"{source} ({url})" for source, url in report_sources(missing, settings=settings)
                    )
                    message = (
                        f"Missing expected PSE trading session {missing} before available "
                        f"session {latest_available}; HTTP 404 from {sources}"
                    )
                    LOGGER.error(message)
                    result.errors.append(message)
        if not result.successful:
            result.validation_status = "failed"
            return result

        validated = validate_extracted_quotes(parsed.records, report_dates=available_dates)
        result.errors.extend(parsed.warnings)
        if not result.successful:
            result.validation_status = "failed"
            return result
        LOGGER.info("Validated EOD report coverage reports=%d quotes=%d", len(available), len(validated))
        result.merge_summaries.extend(
            merge_into_raw(validated, raw_dir=settings.raw_dir)
        )
        for summary in result.merge_summaries:
            validate_raw_file(summary.path)
        result.validation_status = "passed"
    except Exception as exc:
        LOGGER.exception("EOD ingestion failed")
        result.validation_status = "failed"
        result.errors.append(f"{type(exc).__name__}: {exc}")

    LOGGER.info(
        "EOD ingestion finished success=%s parsed_reports=%d rows_added=%d validation=%s",
        result.successful,
        len(result.parsed_reports),
        result.rows_added,
        result.validation_status,
    )
    return result
