"""Check or execute one explicit, isolated ForecastPH formal evaluation run."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date
import json
from pathlib import Path

from config.settings import BACKEND_ROOT
from scripts._common import add_verbose_option
from src.formal.runner import FormalRunRequest, run_formal_experiment
from src.formal.schema import FormalRunState, FormalSchemaError, validate_run_id
from src.logging_config import configure_structured_logging


def _date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("cutoff date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("cutoff date must use YYYY-MM-DD")
    return parsed


def _run_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except FormalSchemaError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-id",
        required=True,
        type=_run_id,
        help="Unique formal run identifier",
    )
    parser.add_argument(
        "--cutoff-date",
        required=True,
        type=_date,
        help="Explicit final raw-data date included in the run (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run readiness checks only; never train models or create an archive",
    )
    parser.add_argument(
        "--provenance-file",
        type=Path,
        default=BACKEND_ROOT / "config" / "formal_provenance.json",
        help="Structured raw-source provenance registry",
    )
    parser.add_argument(
        "--corporate-actions-file",
        type=Path,
        default=BACKEND_ROOT / "config" / "corporate_actions.json",
        help="Externally verified corporate-action registry",
    )
    add_verbose_option(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    outcome = run_formal_experiment(
        FormalRunRequest(
            run_id=arguments.run_id,
            cutoff_date=arguments.cutoff_date,
            check_only=arguments.check_only,
            provenance_path=arguments.provenance_file,
            corporate_actions_path=arguments.corporate_actions_file,
        )
    )
    print(json.dumps(outcome.as_dict(), indent=2, sort_keys=True, allow_nan=False))
    if not outcome.readiness.ready:
        return 1
    if arguments.check_only:
        return 0
    return 0 if outcome.state is FormalRunState.FINALIZED else 1


if __name__ == "__main__":
    raise SystemExit(main())
