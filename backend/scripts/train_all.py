"""Run the complete fresh ForecastPH training lifecycle."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging

from config.settings import manila_now
from scripts._common import add_runtime_options, add_symbol_selection, selected_symbols
from src.artifacts.manager import ArtifactManager, reset_generated_artifacts
from src.data.calendar import PSETradingCalendar
from src.data.loader import load_company_history
from src.export.frontend_exporter import FrontendExportBundle, export_frontend_forecasts
from src.logging_config import configure_structured_logging
from src.training.orchestration import train_company_lifecycle


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_symbol_selection(parser)
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear generated artifacts before training; never reuse old fitted state",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Do not update frontend forecast JSON",
    )
    add_runtime_options(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    if arguments.symbol and not arguments.no_export:
        parser.error("--symbol requires --no-export; a frontend export requires all companies")
    try:
        symbols = selected_symbols(arguments)
    except ValueError:
        LOGGER.exception("Training rejected an unknown symbol")
        return 2
    if arguments.fresh:
        try:
            reset_generated_artifacts()
            LOGGER.info("Cleared generated artifacts for fresh training")
        except Exception:
            LOGGER.exception("Fresh artifact reset failed")
            return 1

    histories = {}
    raw_errors: list[str] = []
    for symbol in symbols:
        try:
            histories[symbol] = load_company_history(symbol)
            LOGGER.info(
                "Validated training data symbol=%s rows=%d first_date=%s last_date=%s",
                symbol,
                len(histories[symbol]),
                histories[symbol][0].trading_date,
                histories[symbol][-1].trading_date,
            )
        except Exception as exc:
            raw_errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
            LOGGER.exception("Training data validation failed symbol=%s", symbol)
    if raw_errors:
        LOGGER.error("Training stopped because raw validation failed errors=%s", raw_errors)
        return 1

    manager = ArtifactManager()
    run = manager.start_run(
        symbols_processed=symbols,
        raw_data_latest_date=max(
            records[-1].trading_date for records in histories.values()
        ),
    )
    calendar = PSETradingCalendar.with_holidays(arguments.holiday)
    completed = []
    errors: list[str] = []
    for symbol in symbols:
        try:
            LOGGER.info("Training company started symbol=%s run_id=%s", symbol, run.run_id)
            completed.append(
                train_company_lifecycle(
                    symbol,
                    histories[symbol],
                    calendar=calendar,
                )
            )
            LOGGER.info("Training company completed symbol=%s run_id=%s", symbol, run.run_id)
        except Exception as exc:
            message = f"{symbol}: {type(exc).__name__}: {exc}"
            errors.append(message)
            LOGGER.exception("Training company failed symbol=%s run_id=%s", symbol, run.run_id)
    if errors:
        manager.fail_run(run.run_id, errors)
        LOGGER.error("Training run failed run_id=%s errors=%s", run.run_id, errors)
        return 1

    completed_at = manila_now()
    if not arguments.no_export:
        try:
            export_frontend_forecasts(
                FrontendExportBundle(
                    companies=tuple(result.frontend_artifacts for result in completed),
                    generated_at=completed_at,
                    last_run_at=completed_at,
                    status="complete",
                )
            )
            LOGGER.info("Frontend export completed run_id=%s", run.run_id)
        except Exception as exc:
            message = f"frontend export: {type(exc).__name__}: {exc}"
            manager.fail_run(run.run_id, [message])
            LOGGER.exception("Frontend export failed run_id=%s", run.run_id)
            return 1
    manager.complete_run(run.run_id, completed_at=completed_at)
    LOGGER.info(
        "Training run completed run_id=%s symbols=%d exported=%s",
        run.run_id,
        len(completed),
        not arguments.no_export,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
