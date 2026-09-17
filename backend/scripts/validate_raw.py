"""Validate and report configured immutable raw OHLCV histories."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from scripts._common import add_symbol_selection, add_verbose_option, selected_symbols
from src.data.loader import load_company_history
from src.logging_config import configure_structured_logging


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_symbol_selection(parser, required=False)
    add_verbose_option(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    try:
        symbols = selected_symbols(arguments)
    except ValueError:
        LOGGER.exception("Raw validation rejected an unknown symbol")
        return 2
    failures = 0
    total_rows = 0
    for symbol in symbols:
        try:
            records = load_company_history(symbol)
            total_rows += len(records)
            LOGGER.info(
                "Validated raw OHLCV symbol=%s rows=%d first_date=%s last_date=%s",
                symbol,
                len(records),
                records[0].trading_date,
                records[-1].trading_date,
            )
        except Exception:
            failures += 1
            LOGGER.exception("Raw OHLCV validation failed symbol=%s", symbol)
    LOGGER.info(
        "Raw validation summary symbols=%d rows=%d failures=%d",
        len(symbols),
        total_rows,
        failures,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
