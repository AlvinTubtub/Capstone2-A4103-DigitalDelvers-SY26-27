"""Download, parse, validate, and merge official PSE EDGE EOD reports only."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date
import logging
from pathlib import Path

from src.ingestion.pipeline import IngestionResult, run_ingestion
from src.logging_config import configure_structured_logging


LOGGER = logging.getLogger(__name__)


def parse_iso_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=parse_iso_date, help="First calendar date, YYYY-MM-DD")
    parser.add_argument("--end-date", type=parse_iso_date, help="Last calendar date, YYYY-MM-DD")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


def _names(paths: Sequence[Path]) -> str:
    return ", ".join(path.name for path in paths) or "none"


def print_summary(result: IngestionResult) -> None:
    """Print the stable, human-readable CLI summary requested for automation."""

    print("PSE EOD ingestion summary")
    print(f"Requested date range: {result.requested_start_date} to {result.requested_end_date}")
    print(f"Downloaded reports ({len(result.downloaded_reports)}): {_names(result.downloaded_reports)}")
    print(
        f"Already-present reports ({len(result.already_present_reports)}): "
        f"{_names(result.already_present_reports)}"
    )
    print(
        f"Unpublished/404 dates ({len(result.unpublished_dates)}): "
        + (", ".join(day.isoformat() for day in result.unpublished_dates) or "none")
    )
    print(
        f"Failed downloads ({len(result.failed_downloads)}): "
        + (
            ", ".join(f"{day}: {message}" for day, message in result.failed_downloads)
            or "none"
        )
    )
    print(f"Parsed reports ({len(result.parsed_reports)}): {_names(result.parsed_reports)}")
    print(
        f"Companies updated ({len(result.companies_updated)}): "
        + (", ".join(result.companies_updated) or "none")
    )
    print(f"Rows added: {result.rows_added}")
    latest = [
        f"{summary.symbol}={summary.latest_date}"
        for summary in result.merge_summaries
        if summary.rows_added > 0
    ]
    print("Latest raw date per updated symbol: " + (", ".join(latest) or "none"))
    print(f"Validation status: {result.validation_status}")
    if result.errors:
        print("Errors: " + " | ".join(result.errors))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if (
        arguments.start_date is not None
        and arguments.end_date is not None
        and arguments.start_date > arguments.end_date
    ):
        parser.error("--start-date cannot be after --end-date")
    configure_structured_logging(verbose=arguments.verbose)
    LOGGER.info("Starting ingestion-only command")
    result = run_ingestion(
        start_date=arguments.start_date,
        end_date=arguments.end_date,
    )
    print_summary(result)
    return 0 if result.successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
