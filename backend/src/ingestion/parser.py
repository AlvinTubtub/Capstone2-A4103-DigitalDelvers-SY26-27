"""Parse configured-company quotation rows from PSE EDGE EOD PDFs."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
import logging
from pathlib import Path
import re
from typing import Any

from config.companies import COMPANIES
from src.ingestion.cleaner import NumericCleaningError, QuotationRecord, clean_quotation
from src.ingestion.config import (
    DEFAULT_INGESTION_SETTINGS,
    IngestionSettings,
    configured_symbols,
)


LOGGER = logging.getLogger(__name__)
DATE_PATTERN = re.compile(r"([A-Za-z]+ \d{1,2}, \d{4})")
LOCAL_FILENAME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-EOD\.pdf$")
QUOTATION_VALUE_COUNT = 9


class PdfParseError(ValueError):
    """Raised when a staged file is unreadable or not a compatible EOD report."""


@dataclass(slots=True)
class ParseBatchResult:
    records: list[QuotationRecord] = field(default_factory=list)
    parsed_reports: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def extract_report_date(text: str) -> date | None:
    match = DATE_PATTERN.search(text)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def parse_quotation_line(
    line: str,
    report_date: date,
    *,
    target_symbols: frozenset[str] | None = None,
) -> QuotationRecord | None:
    """Parse the PSE text extraction layout used by actual quotation pages."""

    symbols = target_symbols if target_symbols is not None else configured_symbols()
    tokens = line.split()
    identified = None
    for company in COMPANIES:
        if company.symbol not in symbols:
            continue
        expected_prefix = (*company.pse_issue_name.split(), company.symbol)
        if tuple(tokens[: len(expected_prefix)]) == expected_prefix:
            identified = (company, len(expected_prefix) - 1)
            break
    if identified is None:
        return None
    company, symbol_index = identified
    remaining = tokens[symbol_index + 1 :]
    # Actual PSE layout after Symbol: Bid, Ask, Open, High, Low, Close,
    # Volume, Value, and Net Foreign Buying/(Selling). Only OHLCV and Value
    # are retained; Net Foreign is outside the canonical ingestion contract.
    if len(remaining) != QUOTATION_VALUE_COUNT:
        raise PdfParseError(
            f"Malformed quotation row for {company.symbol} on {report_date}; "
            f"operator review required: {line!r}"
        )
    try:
        return clean_quotation(
            report_date=report_date,
            issue_name=company.pse_issue_name,
            symbol=company.symbol,
            open_value=remaining[2],
            high_value=remaining[3],
            low_value=remaining[4],
            close_value=remaining[5],
            volume_value=remaining[6],
            traded_value=remaining[7],
        )
    except NumericCleaningError as exc:
        raise PdfParseError(
            f"Malformed quotation row for {company.symbol} on {report_date}; "
            f"operator review required: {exc}"
        ) from exc


def _open_pdf(path: Path) -> Any:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - exercised only in misconfigured installs
        raise PdfParseError(
            "pdfplumber is required for EOD ingestion; install backend/requirements.txt"
        ) from exc
    return pdfplumber.open(path)


def report_date_from_filename(path: Path) -> date | None:
    match = LOCAL_FILENAME_PATTERN.match(path.name)
    if match is None:
        return None
    return date.fromisoformat(match.group(1))


def parse_pdf(
    pdf_path: Path,
    *,
    settings: IngestionSettings = DEFAULT_INGESTION_SETTINGS,
    pdf_opener: Callable[[Path], Any] = _open_pdf,
) -> list[QuotationRecord]:
    """Parse one report, rejecting unreadable, misdated, or conflicting content."""

    path = Path(pdf_path)
    if not path.is_file():
        raise PdfParseError(f"File not found: {path}")
    try:
        with pdf_opener(path) as pdf:
            page_texts = [
                text
                for page in pdf.pages[: settings.max_quotation_pages]
                if (text := page.extract_text())
            ]
    except PdfParseError:
        raise
    except Exception as exc:
        raise PdfParseError(f"Could not read {path.name}: {exc}") from exc

    report_date = next(
        (parsed for text in page_texts if (parsed := extract_report_date(text)) is not None),
        None,
    )
    if report_date is None:
        raise PdfParseError(f"Could not find a report date in {path.name}")
    filename_date = report_date_from_filename(path)
    if filename_date is not None and filename_date != report_date:
        raise PdfParseError(
            f"Report date {report_date} does not match staged filename date {filename_date}"
        )

    records_by_symbol: dict[str, QuotationRecord] = {}
    for text in page_texts:
        for line in text.splitlines():
            record = parse_quotation_line(line, report_date)
            if record is None:
                continue
            prior = records_by_symbol.get(record.symbol)
            if prior is None:
                records_by_symbol[record.symbol] = record
            elif prior != record:
                raise PdfParseError(
                    f"Conflicting duplicate quotation rows for {record.symbol} on {report_date}"
                )
    return list(records_by_symbol.values())


def parse_reports(
    pdf_paths: Iterable[Path],
    *,
    settings: IngestionSettings = DEFAULT_INGESTION_SETTINGS,
    pdf_opener: Callable[[Path], Any] = _open_pdf,
) -> ParseBatchResult:
    result = ParseBatchResult()
    for path in sorted(Path(item) for item in pdf_paths):
        try:
            records = parse_pdf(path, settings=settings, pdf_opener=pdf_opener)
        except PdfParseError as exc:
            result.errors.append((path, str(exc)))
            LOGGER.error("Failed to parse EOD report path=%s error=%s", path, exc)
            continue
        result.parsed_reports.append(path)
        result.records.extend(records)
        if not records:
            warning = f"{path.name}: report parsed but contained no configured-company rows"
            result.warnings.append(warning)
            LOGGER.warning(warning)
        else:
            LOGGER.info("Parsed EOD report path=%s rows=%d", path, len(records))
    return result
