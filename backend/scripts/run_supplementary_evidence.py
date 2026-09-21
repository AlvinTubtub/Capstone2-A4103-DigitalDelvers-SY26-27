"""Check, finalize, or verify a Phase D supplementary evidence package."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import logging
from pathlib import Path

from config.ledger_config import DEFAULT_FORECAST_LEDGER_PATH
from src.evaluation.supplementary_archive import (
    DEFAULT_SUPPLEMENTARY_RUNS_ROOT,
    SupplementaryEvidenceArchive,
    validate_package_id,
)
from src.evaluation.supplementary_evidence import (
    build_supplementary_evidence_plan,
    finalize_supplementary_plan,
    load_and_validate_finalized_payloads,
    verify_source_linkage,
)
from src.formal.schema import FormalSchemaError, validate_run_id
from src.formal.validation import DEFAULT_FORMAL_RUNS_ROOT
from src.logging_config import configure_structured_logging


LOGGER = logging.getLogger(__name__)


def _formal_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except FormalSchemaError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _package_id(value: str) -> str:
    try:
        return validate_package_id(value)
    except RuntimeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-id", required=True, type=_package_id)
    parser.add_argument("--formal-run-id", type=_formal_id)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check-only", action="store_true")
    actions.add_argument("--finalize", action="store_true")
    actions.add_argument("--verify", action="store_true")
    parser.add_argument("--formal-runs-root", type=Path, default=DEFAULT_FORMAL_RUNS_ROOT)
    parser.add_argument("--supplementary-runs-root", type=Path, default=DEFAULT_SUPPLEMENTARY_RUNS_ROOT)
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_FORECAST_LEDGER_PATH)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    if (arguments.check_only or arguments.finalize) and not arguments.formal_run_id:
        raise SystemExit("--formal-run-id is required with --check-only or --finalize")
    try:
        if arguments.verify:
            package = SupplementaryEvidenceArchive(
                arguments.package_id, root=arguments.supplementary_runs_root
            )
            integrity = package.verify_integrity()
            if integrity.valid:
                load_and_validate_finalized_payloads(
                    package, formal_runs_root=arguments.formal_runs_root
                )
            linkage = verify_source_linkage(
                package,
                formal_runs_root=arguments.formal_runs_root,
                ledger_path=arguments.ledger_path,
            )
            result = {
                "action": "verify",
                "package_id": arguments.package_id,
                "integrity": integrity.as_dict(),
                "source_linkage": linkage.as_dict(),
            }
            print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
            return 0 if integrity.valid and linkage.valid else 1

        plan = build_supplementary_evidence_plan(
            arguments.formal_run_id,
            formal_runs_root=arguments.formal_runs_root,
            ledger_path=arguments.ledger_path,
        )
        arima_companies = plan.payloads[
            "methodology/arima_diagnostic_status.json"
        ]["companies"]
        available = sum(
            item.get("enhanced_standardized_residual_diagnostics_available")
            is True
            for item in arima_companies
        )
        unavailable = len(arima_companies) - available
        if arguments.check_only:
            result = {
                "action": "check_only",
                "writes_performed": False,
                "package_id": arguments.package_id,
                "formal_run_id": plan.formal_run_id,
                "formal_integrity_aggregate_sha256": plan.formal_aggregate_sha256,
                "ledger_sha256": plan.ledger_sha256,
                "planned_files": list(plan.planned_files),
                "enhanced_arima_diagnostics_available_company_count": available,
                "enhanced_arima_diagnostics_unavailable_company_count": unavailable,
                "status": "PASS",
            }
        else:
            package = finalize_supplementary_plan(
                arguments.package_id,
                plan,
                root=arguments.supplementary_runs_root,
            )
            result = {
                "action": "finalize",
                "package_id": arguments.package_id,
                "package_path": str(package.path),
                "integrity": package.verify_integrity().as_dict(),
                "status": "PASS",
            }
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except Exception:
        LOGGER.exception("Supplementary evidence action failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
