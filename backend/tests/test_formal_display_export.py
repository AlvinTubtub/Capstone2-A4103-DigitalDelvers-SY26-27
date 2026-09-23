"""Frozen formal display evidence remains independent of live artifacts."""

import csv
from decimal import Decimal
import json
from pathlib import Path

from config.companies import COMPANIES
from src.export.formal_display import (
    DEFAULT_FORMAL_DISPLAY_PATH,
    FORMAL_COMPANY_FIELDS,
    OPERATIONAL_METRICS_FIELDS,
    load_formal_display_snapshot,
)


BACKEND_ROOT = DEFAULT_FORMAL_DISPLAY_PATH.parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent
AUTHORITATIVE_RESULTS_PATH = (
    BACKEND_ROOT / "research-result" / "across_company_tests.csv"
)
FRONTEND_METRICS_PATH = (
    REPOSITORY_ROOT / "frontend" / "public" / "forecasts" / "metrics.json"
)
STALE_FRIEDMAN_VALUES = (
    "2.041666666666" + "675",
    "0.563803824821" + "747",
)


def _authoritative_friedman_row() -> dict[str, str]:
    with AUTHORITATIVE_RESULTS_PATH.open(encoding="utf-8", newline="") as handle:
        matches = [
            row
            for row in csv.DictReader(handle)
            if row["test_level"] == "across_company"
            and row["test_name"] == "friedman"
            and row["metric"] == "mase"
        ]

    assert len(matches) == 1
    row = matches[0]
    assert row["company_count"] == "15"
    assert row["statistic"] == "1.7412587412587377"
    assert row["raw_p_value"] == "0.6278003229833597"
    assert row["alpha"] == "0.05"
    assert row["reject"] == "false"
    assert row["performed"] == "true"
    assert row["formal_run_id"] == "FORECASTPH_FORMAL_20260911_01"
    assert row["formal_cutoff"] == "2026-09-11"
    assert row["formal_git_sha"] == "8359270bffcd43dd41830a01bb2f4e2d4c527b56"
    return row


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _assert_friedman_matches_authoritative(
    across_company: dict[str, object], row: dict[str, str]
) -> None:
    friedman = across_company["friedman"]
    assert isinstance(friedman, dict)
    assert Decimal(str(friedman["statistic"])) == Decimal(row["statistic"])
    assert Decimal(str(friedman["raw_p_value"])) == Decimal(row["raw_p_value"])
    assert friedman["reject"] is (row["reject"] == "true")
    assert across_company["posthoc_performed"] is False
    assert across_company["pairwise_wilcoxon"] == []


def test_repository_formal_display_snapshot_is_complete_and_frozen() -> None:
    snapshot = load_formal_display_snapshot(DEFAULT_FORMAL_DISPLAY_PATH)

    assert snapshot.formal_end_date.isoformat() == "2026-09-11"
    assert set(snapshot.companies) == {company.symbol for company in COMPANIES}
    assert not set(snapshot.metrics_static) & OPERATIONAL_METRICS_FIELDS
    for company in COMPANIES:
        evidence = snapshot.company(company.symbol)
        assert set(evidence) == set(FORMAL_COMPANY_FIELDS)
        assert evidence["evaluationMetadata"]["fullSessionCount"] == 246
        assert evidence["evaluationMetadata"]["fullEndDate"] == "2026-09-11"
        assert len(evidence["backtestDates"]) == 60
        assert evidence["backtestDates"][-1] == "2026-09-11"


def test_snapshot_access_returns_defensive_copies() -> None:
    snapshot = load_formal_display_snapshot(DEFAULT_FORMAL_DISPLAY_PATH)
    first = snapshot.company("BPI")
    first["backtestDates"].append("2099-01-01")
    first_metrics = snapshot.static_metrics()
    first_metrics["bestModel"] = "changed"

    assert len(snapshot.company("BPI")["backtestDates"]) == 60
    assert snapshot.static_metrics()["bestModel"] != "changed"


def test_active_friedman_display_matches_unique_authoritative_csv_row() -> None:
    row = _authoritative_friedman_row()
    formal_payload = _load_json(DEFAULT_FORMAL_DISPLAY_PATH)
    frontend_payload = _load_json(FRONTEND_METRICS_PATH)
    formal_across_company = formal_payload["metrics_static"]["statisticalTests"][
        "across_company"
    ]
    frontend_across_company = frontend_payload["statisticalTests"]["across_company"]

    assert isinstance(formal_across_company, dict)
    assert isinstance(frontend_across_company, dict)
    _assert_friedman_matches_authoritative(formal_across_company, row)
    _assert_friedman_matches_authoritative(frontend_across_company, row)
    assert formal_across_company == frontend_across_company

    for path in (DEFAULT_FORMAL_DISPLAY_PATH, FRONTEND_METRICS_PATH):
        text = path.read_text(encoding="utf-8")
        assert all(stale_value not in text for stale_value in STALE_FRIEDMAN_VALUES)


def test_future_export_source_preserves_authoritative_friedman_evidence() -> None:
    row = _authoritative_friedman_row()
    snapshot = load_formal_display_snapshot(DEFAULT_FORMAL_DISPLAY_PATH)
    across_company = snapshot.static_metrics()["statisticalTests"]["across_company"]

    assert isinstance(across_company, dict)
    _assert_friedman_matches_authoritative(across_company, row)
