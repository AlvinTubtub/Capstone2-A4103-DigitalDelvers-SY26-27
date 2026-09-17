"""Forecast from new persisted production models without tuning or refitting."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging

from config.settings import manila_now
from scripts._common import add_runtime_options, add_symbol_selection, selected_symbols
from src.data.calendar import PSETradingCalendar
from src.data.loader import load_company_history
from src.data.validator import OhlcvValidationError
from src.export.formal_display import FormalDisplayError
from src.export.frontend_exporter import (
    FrontendExportBundle,
    FrontendExportError,
    export_frontend_forecasts,
)
from src.export.production_history import ProductionHistoryError
from src.export.schemas import FrontendSchemaError
from src.inference.next_day import NextDayInferenceError
from src.ledger.schema import LedgerValidationError
from src.logging_config import configure_structured_logging
from src.training.orchestration import (
    OrchestrationError,
    forecast_company_from_artifacts,
)
from src.training.production_refit import ModelArtifactCompatibilityError


LOGGER = logging.getLogger(__name__)
FORECAST_OPERATIONAL_ERRORS = (
    OhlcvValidationError,
    OrchestrationError,
    ModelArtifactCompatibilityError,
    NextDayInferenceError,
    OSError,
)
EXPORT_OPERATIONAL_ERRORS = (
    FrontendExportError,
    FrontendSchemaError,
    FormalDisplayError,
    ProductionHistoryError,
    LedgerValidationError,
    OSError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_symbol_selection(parser)
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Generate backend forecast artifacts without updating frontend JSON",
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
    except ValueError as exc:
        LOGGER.error("Forecasting rejected an unknown symbol error=%s", exc)
        return 2
    calendar = PSETradingCalendar.with_holidays(arguments.holiday)
    completed = []
    errors: list[str] = []
    for symbol in symbols:
        try:
            records = load_company_history(symbol)
            LOGGER.info(
                "Persisted-model forecast started symbol=%s rows=%d data_through=%s",
                symbol,
                len(records),
                records[-1].trading_date,
            )
            completed.append(
                forecast_company_from_artifacts(
                    symbol,
                    records,
                    calendar=calendar,
                )
            )
            LOGGER.info("Persisted-model forecast completed symbol=%s", symbol)
        except FORECAST_OPERATIONAL_ERRORS as exc:
            errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
            LOGGER.error(
                "Operational persisted-model forecast rejected symbol=%s error_type=%s error=%s",
                symbol,
                type(exc).__name__,
                exc,
            )
        except Exception:
            LOGGER.exception(
                "Unexpected persisted-model forecasting failure symbol=%s",
                symbol,
            )
            return 1
    if errors:
        LOGGER.error("Forecast run failed errors=%s", errors)
        return 1
    run_at = manila_now()
    if not arguments.no_export:
        try:
            export_frontend_forecasts(
                FrontendExportBundle(
                    companies=tuple(completed),
                    generated_at=run_at,
                    last_run_at=run_at,
                    status="complete",
                )
            )
        except EXPORT_OPERATIONAL_ERRORS as exc:
            LOGGER.error(
                "Operational frontend forecast update rejected error_type=%s error=%s",
                type(exc).__name__,
                exc,
            )
            return 1
        except Exception:
            LOGGER.exception("Unexpected frontend forecast update failure")
            return 1
    LOGGER.info(
        "Forecast run completed symbols=%d exported=%s",
        len(completed),
        not arguments.no_export,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
