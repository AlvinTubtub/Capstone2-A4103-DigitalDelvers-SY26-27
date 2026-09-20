"""Generate read-only Phase A evidence from a verified finalized formal run."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json

from scripts._common import add_verbose_option
from src.evaluation.supplementary_analysis import (
    PHASE_A_ANALYSIS_VERSION,
    generate_phase_a_supplementary_analysis,
)
from src.formal.schema import FormalSchemaError, validate_run_id
from src.logging_config import configure_structured_logging


def _run_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except FormalSchemaError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--formal-run-id",
        required=True,
        type=_run_id,
        help="Finalized formal run used only as immutable source evidence",
    )
    parser.add_argument(
        "--analysis-version",
        default=PHASE_A_ANALYSIS_VERSION,
        choices=(PHASE_A_ANALYSIS_VERSION,),
        help="Supplementary analysis schema/version identifier",
    )
    add_verbose_option(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    result = generate_phase_a_supplementary_analysis(arguments.formal_run_id)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
