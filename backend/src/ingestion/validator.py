"""Validation for cleaned PSE quotation rows before raw-data merging."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from src.data.validator import OhlcvValidationError, parse_ohlcv_record
from src.ingestion.cleaner import QuotationRecord
from src.ingestion.config import configured_symbols


class ExtractedQuoteValidationError(ValueError):
    """Raised when extracted quotation content is incomplete or inconsistent."""


def _require_value(value: Decimal | None, *, field: str, record: QuotationRecord) -> Decimal:
    if value is None:
        raise ExtractedQuoteValidationError(
            f"{record.symbol} {record.report_date}: {field} is missing"
        )
    return value


def _require_report_coverage(
    rows: tuple[QuotationRecord, ...],
    report_dates: Iterable[date],
) -> None:
    targets = configured_symbols()
    symbols_by_date: dict[date, set[str]] = defaultdict(set)
    unusable_by_date: dict[date, set[str]] = defaultdict(set)
    for record in rows:
        symbols_by_date[record.report_date].add(record.symbol)
        if None in (record.open, record.high, record.low, record.close, record.volume) or (
            record.volume == 0
        ):
            unusable_by_date[record.report_date].add(record.symbol)

    coverage_errors = []
    for report_date in sorted(set(report_dates) | symbols_by_date.keys()):
        missing = targets - symbols_by_date[report_date]
        unusable = unusable_by_date[report_date]
        if missing:
            coverage_errors.append(f"{report_date}: missing symbols {', '.join(sorted(missing))}")
        if unusable:
            coverage_errors.append(
                f"{report_date}: no usable quote for {', '.join(sorted(unusable))} "
                "(missing OHLCV or zero volume)"
            )
    if coverage_errors:
        raise ExtractedQuoteValidationError(
            "Incomplete PSE report coverage; operator review required. "
            + " | ".join(coverage_errors)
        )


def validate_extracted_quotes(
    records: Iterable[QuotationRecord],
    *,
    report_dates: Iterable[date] | None = None,
) -> tuple[QuotationRecord, ...]:
    """Validate quotations and require full coverage when validating reports."""

    rows = tuple(records)
    if report_dates is not None:
        _require_report_coverage(rows, report_dates)
    if not rows:
        raise ExtractedQuoteValidationError("No configured-company quotation rows were extracted")
    targets = configured_symbols()
    keys = [(record.symbol, record.report_date) for record in rows]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        detail = ", ".join(f"{symbol}/{day}" for symbol, day in duplicates)
        raise ExtractedQuoteValidationError(f"Duplicate Symbol+Date quotation rows: {detail}")

    for record in rows:
        if record.symbol not in targets:
            raise ExtractedQuoteValidationError(
                f"Unconfigured quotation symbol: {record.symbol!r}"
            )
        if not record.issue_name:
            raise ExtractedQuoteValidationError(
                f"{record.symbol} {record.report_date}: Issue Name is blank"
            )
        mapping = record.ohlcv_mapping()
        try:
            parse_ohlcv_record(mapping, row_number=2)
        except OhlcvValidationError as exc:
            raise ExtractedQuoteValidationError(
                f"{record.symbol} {record.report_date}: {exc}"
            ) from exc
        traded_value = _require_value(record.value, field="Value", record=record)
        if traded_value < 0:
            raise ExtractedQuoteValidationError(
                f"{record.symbol} {record.report_date}: Value cannot be negative"
            )
    return tuple(sorted(rows, key=lambda item: (item.report_date, item.symbol)))
