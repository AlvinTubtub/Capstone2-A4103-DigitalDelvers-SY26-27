"""Focused tests for frozen OHLCV data-quality screening."""

from copy import deepcopy
from datetime import date, timedelta
import math

import pytest

from src.data.quality_screening import (
    DataQualityScreeningError,
    RULE_VERSION,
    screen_ohlcv_rows,
)
from src.data.validator import REQUIRED_OHLCV_COLUMNS


def _rows(count: int = 20) -> tuple[list[dict[str, object]], tuple[date, ...]]:
    start = date(2026, 1, 1)
    sessions = tuple(start + timedelta(days=index) for index in range(count))
    rows = [
        {
            "Date": session.isoformat(),
            "Open": 100.0 + index / 10,
            "High": 101.0 + index / 10,
            "Low": 99.0 + index / 10,
            "Close": 100.0 + index / 10,
            "Volume": 100.0 + index,
        }
        for index, session in enumerate(sessions)
    ]
    return rows, sessions


def _screen(
    rows: list[dict[str, object]], sessions: tuple[date, ...]
) -> dict[str, object]:
    return screen_ohlcv_rows(
        fieldnames=REQUIRED_OHLCV_COLUMNS,
        rows=rows,
        expected_sessions=sessions,
    )


def test_valid_screen_has_hard_passes_and_locked_rule_version() -> None:
    rows, sessions = _rows()
    result = _screen(rows, sessions)

    assert result["required_columns_status"] == "PASS"
    assert result["numeric_validity_status"] == "PASS"
    assert result["positive_price_status"] == "PASS"
    assert result["ohlc_relationship_status"] == "PASS"
    assert result["basic_validity_status"] == "PASS"
    assert result["continuity_status"] == "PASS"
    assert result["dataset_quality_status"] == "PASS"
    assert RULE_VERSION == "data-quality-v1"


@pytest.mark.parametrize(
    ("fieldnames", "mutate", "message"),
    [
        (("Date", "Open", "High", "Low", "Close"), None, "Missing required"),
        (REQUIRED_OHLCV_COLUMNS, ("Open", "not-a-number"), "must be numeric"),
        (REQUIRED_OHLCV_COLUMNS, ("High", math.inf), "must be finite"),
    ],
)
def test_required_columns_and_finite_numeric_values_fail_closed(
    fieldnames, mutate, message: str
) -> None:
    rows, sessions = _rows()
    if mutate is not None:
        rows[0][mutate[0]] = mutate[1]

    with pytest.raises(DataQualityScreeningError, match=message):
        screen_ohlcv_rows(
            fieldnames=fieldnames,
            rows=rows,
            expected_sessions=sessions,
        )


def test_positive_price_relationship_and_negative_volume_are_hard_failures() -> None:
    rows, sessions = _rows()
    rows[0]["Open"] = -1.0
    result = _screen(rows, sessions)
    assert result["positive_price_status"] == "FAIL"
    assert result["basic_validity_status"] == "FAIL"

    rows, sessions = _rows()
    rows[0]["High"] = 99.5
    result = _screen(rows, sessions)
    assert result["ohlc_relationship_status"] == "FAIL"
    assert result["basic_validity_status"] == "FAIL"

    rows, sessions = _rows()
    rows[0]["Volume"] = -1.0
    result = _screen(rows, sessions)
    assert result["negative_volume_count"] == 1
    assert result["basic_validity_status"] == "FAIL"
    assert result["dataset_quality_status"] == "FAIL"


def test_duplicate_missing_unexpected_and_order_checks_are_distinct() -> None:
    rows, sessions = _rows()
    rows[-1]["Date"] = rows[-2]["Date"]
    result = _screen(rows, sessions)
    assert result["duplicate_date_count"] == 1
    assert result["missing_session_count"] == 1
    assert result["continuity_status"] == "FAIL"
    assert result["basic_validity_status"] == "FAIL"

    rows, sessions = _rows()
    missing = _screen(rows[:-1], sessions)
    assert missing["missing_session_count"] == 1
    assert missing["continuity_status"] == "FAIL"

    rows, sessions = _rows()
    extra = deepcopy(rows[-1])
    extra["Date"] = (sessions[-1] + timedelta(days=1)).isoformat()
    unexpected = _screen([*rows, extra], sessions)
    assert unexpected["unexpected_session_count"] == 1
    assert unexpected["continuity_status"] == "FAIL"

    rows, sessions = _rows()
    rows[0], rows[1] = rows[1], rows[0]
    unordered = _screen(rows, sessions)
    assert unordered["basic_validity_status"] == "FAIL"
    assert unordered["continuity_status"] == "PASS"


def test_zero_volume_review_is_separate_from_hard_quality() -> None:
    rows, sessions = _rows()
    rows[0]["Volume"] = 0.0
    result = _screen(rows, sessions)

    assert result["zero_volume_count"] == 1
    assert result["zero_volume_rate"] == 1 / 20
    assert result["zero_volume_status"] == "REVIEW"
    assert result["active_session_count"] == 19
    assert result["active_session_rate"] == 0.95
    assert result["liquidity_status"] == "PASS"
    assert result["dataset_quality_status"] == "PASS"
    assert result["screening_review_required"] is True

    rows[1]["Volume"] = 0.0
    result = _screen(rows, sessions)
    assert result["active_session_rate"] == 0.9
    assert result["liquidity_status"] == "REVIEW"


def test_unchanged_close_alone_is_not_an_identical_ohlc_transition() -> None:
    rows, sessions = _rows()
    rows[1]["Close"] = rows[0]["Close"]
    rows[1]["Open"] = 100.1
    rows[1]["High"] = 101.1
    rows[1]["Low"] = 99.1
    result = _screen(rows, sessions)

    assert result["unchanged_close_count"] == 1
    assert result["identical_ohlc_transition_count"] == 0
    assert result["max_identical_ohlc_run"] == 1
    assert result["max_identical_ohlc_run_start"] == ""
    assert result["max_identical_ohlc_run_end"] == ""
    assert result["stale_price_status"] == "PASS"


@pytest.mark.parametrize(
    ("run_length", "expected_status"),
    [(4, "PASS"), (5, "REVIEW")],
)
def test_stale_run_counts_sessions_not_transitions(
    run_length: int, expected_status: str
) -> None:
    rows, sessions = _rows()
    for index in range(run_length):
        rows[index].update({"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0})
    result = _screen(rows, sessions)

    assert result["identical_ohlc_transition_count"] == run_length - 1
    assert result["max_identical_ohlc_run"] == run_length
    assert result["max_identical_ohlc_run_start"] == sessions[0].isoformat()
    assert result["max_identical_ohlc_run_end"] == sessions[run_length - 1].isoformat()
    assert result["stale_price_status"] == expected_status


def test_activity_medians_and_close_value_proxy_are_deterministic() -> None:
    rows, sessions = _rows(4)
    result = _screen(rows, sessions)

    assert result["median_volume"] == 101.5
    expected_proxy = (
        float(rows[1]["Close"]) * float(rows[1]["Volume"])
        + float(rows[2]["Close"]) * float(rows[2]["Volume"])
    ) / 2
    assert result["median_close_value_proxy"] == expected_proxy


def test_material_return_threshold_and_date_serialization() -> None:
    sessions = (date(2026, 1, 1), date(2026, 1, 2))
    rows = [
        {"Date": sessions[0].isoformat(), "Open": 100, "High": 101, "Low": 99, "Close": 100, "Volume": 10},
        {"Date": sessions[1].isoformat(), "Open": 129, "High": 131, "Low": 128, "Close": 130, "Volume": 10},
    ]
    positive = _screen(rows, sessions)
    assert positive["material_discontinuity_count"] == 1
    assert positive["material_discontinuity_dates"] == "2026-01-02"
    assert positive["material_discontinuity_status"] == "REVIEW"

    rows[1].update({"Open": 70, "High": 71, "Low": 69, "Close": 70})
    negative = _screen(rows, sessions)
    assert negative["material_discontinuity_count"] == 1
    assert negative["material_discontinuity_dates"] == "2026-01-02"

    rows[1].update({"Open": 129, "High": 130, "Low": 128, "Close": 129.99})
    below = _screen(rows, sessions)
    assert below["max_absolute_return"] < 0.30
    assert below["material_discontinuity_count"] == 0
    assert below["max_absolute_return_date"] == ""
    assert below["material_discontinuity_status"] == "PASS"


def test_positive_and_negative_material_dates_are_chronological() -> None:
    sessions = tuple(date(2026, 1, 1) + timedelta(days=index) for index in range(3))
    closes = (100.0, 130.0, 90.0)
    rows = [
        {
            "Date": session.isoformat(),
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 10,
        }
        for session, close in zip(sessions, closes)
    ]
    result = _screen(rows, sessions)

    assert result["material_discontinuity_count"] == 2
    assert result["material_discontinuity_dates"] == "2026-01-02|2026-01-03"
    assert result["dataset_quality_status"] == "PASS"
    assert result["screening_review_required"] is True
