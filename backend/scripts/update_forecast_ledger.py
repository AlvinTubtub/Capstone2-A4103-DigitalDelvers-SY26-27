"""Resolve or issue append-only prospective forecasts without model training."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import logging
from pathlib import Path

from config.ledger_config import DEFAULT_FORECAST_LEDGER_PATH
from config.settings import SETTINGS
from scripts._common import add_symbol_selection, add_verbose_option, selected_symbols
from src.artifacts.production_manifest import load_production_manifest
from src.data.calendar import PSETradingCalendar
from src.data.loader import load_company_history
from src.ledger.lifecycle import (
    issue_company_forecasts,
    load_persisted_next_day_forecast,
    production_model_versions,
    resolve_pending_outcomes,
)
from src.ledger.store import ForecastLedger
from src.logging_config import configure_structured_logging
from src.monitoring.drift import monitor_company_drift


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--resolve-outcomes",
        action="store_true",
        help="Append actual Close outcomes for exact pending target dates",
    )
    action.add_argument(
        "--issue-forecasts",
        action="store_true",
        help="Append current persisted-model forecasts and prospective Naive",
    )
    action.add_argument(
        "--report-drift",
        action="store_true",
        help="Report drift evidence from resolved prospective records only",
    )
    add_symbol_selection(parser)
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=DEFAULT_FORECAST_LEDGER_PATH,
        help="Append-only JSONL ledger path",
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=SETTINGS.artifacts_dir,
        help="Validated production artifact root used for issuance metadata",
    )
    add_verbose_option(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    try:
        symbols = selected_symbols(arguments)
        ledger = ForecastLedger(arguments.ledger_path)
        if arguments.resolve_outcomes:
            results = resolve_pending_outcomes(
                ledger,
                {symbol: load_company_history(symbol) for symbol in symbols},
            )
            print(
                json.dumps(
                    {
                        "action": "resolve_outcomes",
                        "requested_symbols": list(symbols),
                        "outcomes_appended": sum(item.appended for item in results),
                        "idempotent_outcomes": sum(not item.appended for item in results),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.issue_forecasts:
            manifest = load_production_manifest(arguments.artifacts_root)
            appended = 0
            idempotent = 0
            calendar = PSETradingCalendar()
            for symbol in symbols:
                results = issue_company_forecasts(
                    ledger,
                    load_persisted_next_day_forecast(
                        symbol,
                        artifacts_root=arguments.artifacts_root,
                    ),
                    load_company_history(symbol),
                    model_versions=production_model_versions(
                        symbol,
                        artifacts_root=arguments.artifacts_root,
                    ),
                    calendar=calendar,
                    production_run_id=manifest.run_id,
                    source_commit=manifest.source_commit,
                )
                appended += sum(item.appended for item in results)
                idempotent += sum(not item.appended for item in results)
            print(
                json.dumps(
                    {
                        "action": "issue_forecasts",
                        "requested_symbols": list(symbols),
                        "forecasts_appended": appended,
                        "idempotent_forecasts": idempotent,
                        "production_run_id": manifest.run_id,
                        "source_commit": manifest.source_commit,
                    },
                    sort_keys=True,
                )
            )
            return 0
        snapshot = ledger.read()
        reports = [
            monitor_company_drift(snapshot, symbol).as_dict()
            for symbol in symbols
        ]
        print(json.dumps({"action": "report_drift", "reports": reports}, indent=2))
        return 0
    except Exception:
        LOGGER.exception("Prospective forecast ledger action failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
