"""Download and stage official PSE EOD PDFs with bounded transient retries."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.data.calendar import PSETradingCalendar
from src.ingestion.config import DEFAULT_INGESTION_SETTINGS, IngestionSettings, PDF_SUFFIX
from src.ingestion.parser import PdfParseError, parse_pdf
from src.ingestion.validator import ExtractedQuoteValidationError, validate_extracted_quotes


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FetchResponse:
    status_code: int
    content: bytes


@dataclass(slots=True)
class DownloadResult:
    downloaded: list[Path] = field(default_factory=list)
    already_present: list[Path] = field(default_factory=list)
    unpublished: list[date] = field(default_factory=list)
    failed: list[tuple[date, str]] = field(default_factory=list)

    @property
    def available_reports(self) -> tuple[Path, ...]:
        return tuple(sorted((*self.downloaded, *self.already_present)))


Fetcher = Callable[[str, float], FetchResponse]


def report_url(report_date: date, *, base_url: str = DEFAULT_INGESTION_SETTINGS.base_url) -> str:
    """Build the PSE EDGE URL used by the main-branch ingestion pipeline."""

    month = report_date.strftime("%B")
    day = report_date.strftime("%d")
    year = report_date.strftime("%Y")
    remote_name = f"{month}%20{day},%20{year}{PDF_SUFFIX}"
    return f"{base_url.rstrip('/')}/{remote_name}"


def report_sources(
    report_date: date, *, settings: IngestionSettings
) -> tuple[tuple[str, str], ...]:
    """Return the primary report and the official archive copy in lookup order."""

    archive_path = report_date.strftime("%Y/%m/stockQuotes_%m%d%Y.pdf")
    return (
        ("primary", report_url(report_date, base_url=settings.base_url)),
        ("archive", f"{settings.archive_base_url.rstrip('/')}/{archive_path}"),
    )


def report_filename(report_date: date) -> str:
    return f"{report_date.isoformat()}{PDF_SUFFIX}"


def _fetch(url: str, timeout_seconds: float) -> FetchResponse:
    request = Request(url, headers={"User-Agent": "ForecastPH-EOD-Ingestion/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed HTTPS host
        return FetchResponse(status_code=int(response.status), content=response.read())


def _retry_delay(settings: IngestionSettings, attempt: int) -> float:
    return settings.backoff_base_seconds**attempt


def _stage_validated_report(
    destination: Path, content: bytes, *, report_date: date, settings: IngestionSettings
) -> None:
    # Keep the canonical filename during validation so the parser checks the
    # embedded date, then publish to the local cache only after validation.
    with TemporaryDirectory(dir=destination.parent) as directory:
        staged = Path(directory) / destination.name
        staged.write_bytes(content)
        validate_extracted_quotes(parse_pdf(staged, settings=settings), report_dates=(report_date,))
        os.replace(staged, destination)


def _fetch_report(
    url: str,
    *,
    settings: IngestionSettings,
    fetcher: Fetcher,
    sleep_fn: Callable[[float], None],
) -> FetchResponse:
    last_error = "unknown download failure"
    for attempt in range(1, settings.max_retries + 1):
        try:
            response = fetcher(url, settings.request_timeout_seconds)
        except HTTPError as exc:
            response = FetchResponse(exc.code, b"")
        except (URLError, TimeoutError, OSError) as exc:
            response = None
            last_error = f"{type(exc).__name__}: {exc}"

        if response is not None:
            status = response.status_code
            if status in (200, 404):
                return response
            last_error = f"HTTP {status}"
            if status != 429 and status < 500:
                break

        LOGGER.warning(
            "Transient EOD download failure url=%s attempt=%d/%d error=%s",
            url,
            attempt,
            settings.max_retries,
            last_error,
        )
        if attempt < settings.max_retries:
            sleep_fn(_retry_delay(settings, attempt))
    raise OSError(last_error)


def download_one(
    report_date: date,
    *,
    settings: IngestionSettings = DEFAULT_INGESTION_SETTINGS,
    fetcher: Fetcher = _fetch,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[str, Path | None, str | None]:
    """Download one report and return downloaded/already_present/unpublished/failed."""

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.reports_dir / report_filename(report_date)
    if destination.is_file():
        LOGGER.info("EOD report already present date=%s path=%s", report_date, destination)
        return "already_present", destination, None

    for source, url in report_sources(report_date, settings=settings):
        try:
            response = _fetch_report(url, settings=settings, fetcher=fetcher, sleep_fn=sleep_fn)
            if response.status_code == 404:
                LOGGER.info("EOD report HTTP 404 date=%s source=%s url=%s", report_date, source, url)
                continue
            _stage_validated_report(
                destination, response.content, report_date=report_date, settings=settings
            )
        except (OSError, PdfParseError, ExtractedQuoteValidationError) as exc:
            message = f"{source} ({url}): {exc}"
            LOGGER.error("EOD report rejected date=%s %s", report_date, message)
            return "failed", None, message

        LOGGER.info(
            "Downloaded EOD report date=%s source=%s url=%s bytes=%d",
            report_date, source, url, len(response.content),
        )
        return "downloaded", destination, None

    return "unpublished", None, None


def download_reports(
    start_date: date,
    end_date: date,
    *,
    settings: IngestionSettings = DEFAULT_INGESTION_SETTINGS,
    fetcher: Fetcher = _fetch,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> DownloadResult:
    """Download expected PSE sessions within the inclusive date range."""

    result = DownloadResult()
    calendar = PSETradingCalendar()
    for offset in range((end_date - start_date).days + 1):
        current = start_date + timedelta(days=offset)
        if not calendar.is_trading_day(current):
            continue
        status, path, message = download_one(
            current,
            settings=settings,
            fetcher=fetcher,
            sleep_fn=sleep_fn,
        )
        if status == "downloaded" and path is not None:
            result.downloaded.append(path)
        elif status == "already_present" and path is not None:
            result.already_present.append(path)
        elif status == "unpublished":
            result.unpublished.append(current)
        else:
            result.failed.append((current, message or "unknown download failure"))
    return result
