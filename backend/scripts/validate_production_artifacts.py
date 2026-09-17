"""Create or validate the complete Phase 14 production artifact package."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging
from pathlib import Path

from config.settings import SETTINGS
from scripts._common import add_verbose_option
from src.artifacts.production_manifest import (
    create_production_manifest,
    validate_production_artifacts,
)
from src.logging_config import configure_structured_logging


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=SETTINGS.artifacts_dir,
        help="Artifact package root (defaults to backend/artifacts)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--create-manifest",
        action="store_true",
        help="Validate the package and atomically create its Phase 14 manifest",
    )
    mode.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Validate freshly generated contents before the manifest exists",
    )
    parser.add_argument("--run-id", help="GitHub Actions run ID for manifest creation")
    parser.add_argument("--source-commit", help="Full source commit SHA")
    parser.add_argument("--source-branch", help="Source branch name")
    parser.add_argument("--expected-run-id", help="Required manifest run ID")
    parser.add_argument("--expected-source-commit", help="Required manifest commit SHA")
    parser.add_argument("--expected-source-branch", help="Required manifest branch")
    parser.add_argument(
        "--require-forecasts",
        action="store_true",
        help="Also require all per-company next-day forecast artifacts",
    )
    parser.add_argument(
        "--require-current-data",
        action="store_true",
        help="Require model boundaries to equal the latest current raw rows",
    )
    add_verbose_option(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    configure_structured_logging(verbose=arguments.verbose)
    creation_values = (
        arguments.run_id,
        arguments.source_commit,
        arguments.source_branch,
    )
    if arguments.create_manifest and any(value is None for value in creation_values):
        parser.error(
            "--create-manifest requires --run-id, --source-commit, and --source-branch"
        )
    if not arguments.create_manifest and any(value is not None for value in creation_values):
        parser.error("manifest creation fields require --create-manifest")
    try:
        report = validate_production_artifacts(
            arguments.artifacts_root,
            require_manifest=not (
                arguments.create_manifest or arguments.skip_manifest
            ),
            require_forecasts=arguments.require_forecasts,
            require_current_data=arguments.require_current_data,
            expected_run_id=arguments.expected_run_id,
            expected_source_commit=arguments.expected_source_commit,
            expected_source_branch=arguments.expected_source_branch,
        )
        if arguments.create_manifest:
            create_production_manifest(
                report,
                run_id=arguments.run_id,
                source_commit=arguments.source_commit,
                source_branch=arguments.source_branch,
            )
            report = validate_production_artifacts(
                arguments.artifacts_root,
                require_manifest=True,
                require_forecasts=arguments.require_forecasts,
                require_current_data=arguments.require_current_data,
                expected_run_id=arguments.run_id,
                expected_source_commit=arguments.source_commit,
                expected_source_branch=arguments.source_branch,
            )
    except Exception:
        LOGGER.exception("Production artifact validation failed")
        return 1
    LOGGER.info(
        "Production artifact validation passed symbols=%d files=%d trained_through=%s manifest=%s",
        len(report.symbols),
        report.validated_file_count,
        report.training_data_through,
        report.manifest is not None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
