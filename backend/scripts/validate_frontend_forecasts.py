"""Validate all frontend forecast JSON without changing generated files."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging
from pathlib import Path

from scripts._common import add_verbose_option
from src.export.frontend_exporter import FRONTEND_FORECASTS_DIR
from src.export.validation import (
    FrontendForecastValidationError,
    validate_frontend_forecasts,
)
from src.logging_config import configure_structured_logging


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=FRONTEND_FORECASTS_DIR,
        help="Forecast JSON root (defaults to frontend/public/forecasts)",
    )
    add_verbose_option(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    try:
        files = validate_frontend_forecasts(arguments.output_root)
    except FrontendForecastValidationError as exc:
        LOGGER.error("Frontend forecast JSON validation rejected error=%s", exc)
        return 1
    except Exception:
        LOGGER.exception("Unexpected frontend forecast JSON validation failure")
        return 1
    LOGGER.info("Frontend forecast JSON validation passed files=%d", len(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
