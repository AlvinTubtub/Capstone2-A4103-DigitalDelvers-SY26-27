"""Deterministic, read-only OHLCV quality screening for frozen research data."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
import math
from statistics import median
from typing import Final

from src.data.validator import (
    OhlcvRecord,
    OhlcvValidationError,
    REQUIRED_OHLCV_COLUMNS,
    validate_required_columns,
)


RULE_VERSION: Final[str] = "data-quality-v1"
STALE_RUN_REVIEW_THRESHOLD: Final[int] = 5
ACTIVE_SESSION_RATE_THRESHOLD: Final[float] = 0.95
MATERIAL_RETURN_THRESHOLD: Final[float] = 0.30


class DataQualityScreeningError(ValueError):
    """Raised when a required screening calculation cannot be completed safely."""


def _parse_date(value: object, *, row_number: int) -> date:
    raw = "" if value is None else str(value).strip()
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise DataQualityScreeningError(
            f"Row {row_number}: Date must be a valid YYYY-MM-DD value"
        ) from exc
    if parsed.isoformat() != raw:
        raise DataQualityScreeningError(
            f"Row {row_number}: Date must use canonical YYYY-MM-DD format"
        )
    return parsed


def _parse_number(value: object, *, column: str, row_number: int) -> float:
    raw = "" if value is None else str(value).strip()
    try:
        parsed = float(raw)
    except (TypeError, ValueError) as exc:
        raise DataQualityScreeningError(
            f"Row {row_number}: {column} must be numeric"
        ) from exc
    if not math.isfinite(parsed):
        raise DataQualityScreeningError(
            f"Row {row_number}: {column} must be finite"
        )
    return parsed


def _parse_records(
    fieldnames: Sequence[str] | None,
    rows: Sequence[Mapping[str, object]],
) -> tuple[OhlcvRecord, ...]:
    try:
        validate_required_columns(fieldnames)
    except OhlcvValidationError as exc:
        raise DataQualityScreeningError(str(exc)) from exc
    if not rows:
        raise DataQualityScreeningError("OHLCV screening requires at least one row")

    records: list[OhlcvRecord] = []
    for row_number, row in enumerate(rows, start=2):
        values = {
            column: _parse_number(row.get(column), column=column, row_number=row_number)
            for column in REQUIRED_OHLCV_COLUMNS
            if column != "Date"
        }
        records.append(
            OhlcvRecord(
                trading_date=_parse_date(row.get("Date"), row_number=row_number),
                open=values["Open"],
                high=values["High"],
                low=values["Low"],
                close=values["Close"],
                volume=values["Volume"],
            )
        )
    return tuple(records)


def _stale_price_fields(records: Sequence[OhlcvRecord]) -> dict[str, object]:
    unchanged_close_count = sum(
        current.close == previous.close
        for previous, current in zip(records, records[1:])
    )
    transition_count = 0
    current_length = 1
    current_start = records[0].trading_date
    max_length = 1
    max_start: date | None = None
    max_end: date | None = None
    for previous, current in zip(records, records[1:]):
        identical = (
            current.open == previous.open
            and current.high == previous.high
            and current.low == previous.low
            and current.close == previous.close
        )
        if identical:
            transition_count += 1
            if current_length == 1:
                current_start = previous.trading_date
            current_length += 1
            if current_length > max_length:
                max_length = current_length
                max_start = current_start
                max_end = current.trading_date
        else:
            current_length = 1
            current_start = current.trading_date

    # Convention: a non-empty series with no repeated full-OHLC transition has
    # maximum run length 1 and blank run dates because there is no stale run.
    return {
        "unchanged_close_count": unchanged_close_count,
        "identical_ohlc_transition_count": transition_count,
        "max_identical_ohlc_run": max_length,
        "max_identical_ohlc_run_start": "" if max_start is None else max_start.isoformat(),
        "max_identical_ohlc_run_end": "" if max_end is None else max_end.isoformat(),
        "stale_price_status": (
            "REVIEW" if max_length >= STALE_RUN_REVIEW_THRESHOLD else "PASS"
        ),
    }


def _material_discontinuity_fields(
    records: Sequence[OhlcvRecord],
) -> dict[str, object]:
    if any(record.close <= 0 for record in records):
        raise DataQualityScreeningError(
            "Close must be positive to calculate close-to-close returns"
        )
    returns = tuple(
        (current.trading_date, (current.close / previous.close) - 1.0)
        for previous, current in zip(records, records[1:])
    )
    if not returns:
        return {
            "material_discontinuity_count": 0,
            "max_absolute_return": 0.0,
            "max_absolute_return_date": "",
            "material_discontinuity_dates": "",
            "material_discontinuity_status": "PASS",
        }
    flagged = tuple(
        (trading_date, value)
        for trading_date, value in returns
        if abs(value) >= MATERIAL_RETURN_THRESHOLD
    )
    maximum = max(abs(value) for _, value in returns)
    maximum_date = (
        max(flagged, key=lambda item: abs(item[1]))[0].isoformat()
        if flagged
        else ""
    )
    return {
        "material_discontinuity_count": len(flagged),
        "max_absolute_return": maximum,
        "max_absolute_return_date": maximum_date,
        "material_discontinuity_dates": "|".join(
            trading_date.isoformat() for trading_date, _ in flagged
        ),
        "material_discontinuity_status": "REVIEW" if flagged else "PASS",
    }


def screen_ohlcv_rows(
    *,
    fieldnames: Sequence[str] | None,
    rows: Sequence[Mapping[str, object]],
    expected_sessions: Sequence[date],
) -> dict[str, object]:
    """Screen stored rows without sorting, filling, adjusting, or mutating them."""

    parsed = _parse_records(fieldnames, rows)
    expected = tuple(expected_sessions)
    if (
        not expected
        or tuple(sorted(set(expected))) != expected
    ):
        raise DataQualityScreeningError(
            "Expected trading sessions must be non-empty, unique, and chronological"
        )

    raw_dates = tuple(record.trading_date for record in parsed)
    counts = Counter(raw_dates)
    duplicate_date_count = sum(count > 1 for count in counts.values())
    chronological = all(
        current < following for current, following in zip(raw_dates, raw_dates[1:])
    )
    records = tuple(sorted(parsed, key=lambda record: record.trading_date))

    positive_prices = all(
        value > 0
        for record in records
        for value in (record.open, record.high, record.low, record.close)
    )
    relationships_valid = all(
        record.high >= max(record.open, record.low, record.close)
        and record.low <= min(record.open, record.high, record.close)
        for record in records
    )
    negative_volume_count = sum(record.volume < 0 for record in records)
    basic_valid = (
        positive_prices
        and relationships_valid
        and negative_volume_count == 0
        and duplicate_date_count == 0
        and chronological
    )

    observed = set(raw_dates)
    expected_set = set(expected)
    missing_count = len(expected_set - observed)
    unexpected_count = len(observed - expected_set)
    continuity_valid = (
        missing_count == 0
        and unexpected_count == 0
        and duplicate_date_count == 0
    )

    row_count = len(records)
    zero_volume_count = sum(record.volume == 0 for record in records)
    active_session_count = sum(record.volume > 0 for record in records)
    active_session_rate = active_session_count / row_count
    stale = _stale_price_fields(records)
    discontinuity = _material_discontinuity_fields(records)
    screening_review = (
        zero_volume_count > 0
        or stale["stale_price_status"] == "REVIEW"
        or active_session_rate < ACTIVE_SESSION_RATE_THRESHOLD
        or discontinuity["material_discontinuity_status"] == "REVIEW"
    )

    return {
        "start_date": min(raw_dates).isoformat(),
        "end_date": max(raw_dates).isoformat(),
        "row_count": row_count,
        "required_columns_status": "PASS",
        "numeric_validity_status": "PASS",
        "positive_price_status": "PASS" if positive_prices else "FAIL",
        "ohlc_relationship_status": "PASS" if relationships_valid else "FAIL",
        "negative_volume_count": negative_volume_count,
        "duplicate_date_count": duplicate_date_count,
        "basic_validity_status": "PASS" if basic_valid else "FAIL",
        "expected_session_count": len(expected),
        "observed_session_count": len(observed),
        "missing_session_count": missing_count,
        "unexpected_session_count": unexpected_count,
        "continuity_status": "PASS" if continuity_valid else "FAIL",
        "zero_volume_count": zero_volume_count,
        "zero_volume_rate": zero_volume_count / row_count,
        "zero_volume_status": "REVIEW" if zero_volume_count else "PASS",
        **stale,
        "active_session_count": active_session_count,
        "active_session_rate": active_session_rate,
        "median_volume": median(record.volume for record in records),
        "median_close_value_proxy": median(
            record.close * record.volume for record in records
        ),
        "liquidity_status": (
            "PASS" if active_session_rate >= ACTIVE_SESSION_RATE_THRESHOLD else "REVIEW"
        ),
        **discontinuity,
        "dataset_quality_status": (
            "PASS" if basic_valid and continuity_valid else "FAIL"
        ),
        "screening_review_required": screening_review,
    }
