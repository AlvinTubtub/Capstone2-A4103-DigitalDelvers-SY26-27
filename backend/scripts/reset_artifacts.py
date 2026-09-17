"""Safely clear generated backend artifacts while preserving raw source data."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging

from src.artifacts.manager import reset_generated_artifacts
from src.logging_config import configure_structured_logging


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


def _confirmed() -> bool:
    try:
        answer = input(
            'Type "reset" to delete only generated backend/artifacts content: '
        )
    except EOFError:
        return False
    return answer.strip().lower() == "reset"


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    if not arguments.yes and not _confirmed():
        LOGGER.warning("Artifact reset cancelled; pass --yes for non-interactive use")
        return 2
    try:
        directories = reset_generated_artifacts()
    except Exception:
        LOGGER.exception("Artifact reset failed")
        return 1
    LOGGER.info(
        "Artifact reset complete directories=%s",
        ",".join(path.name for path in directories.all_generated_directories()),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
