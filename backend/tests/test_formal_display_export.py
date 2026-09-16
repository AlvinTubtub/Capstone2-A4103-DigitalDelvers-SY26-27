"""Frozen formal display evidence remains independent of live artifacts."""

from config.companies import COMPANIES
from src.export.formal_display import (
    DEFAULT_FORMAL_DISPLAY_PATH,
    FORMAL_COMPANY_FIELDS,
    OPERATIONAL_METRICS_FIELDS,
    load_formal_display_snapshot,
)


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
