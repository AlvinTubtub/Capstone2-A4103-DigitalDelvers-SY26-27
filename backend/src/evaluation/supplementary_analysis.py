"""Read-only derivation of Phase A evidence from one finalized formal archive."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile

from config.model_config import ModelId
from config.settings import SETTINGS, manila_now
from src.artifacts.io import atomic_write_json
from src.evaluation.change_diagnostics import archived_change_diagnostics
from src.evaluation.metrics import EvaluationMetrics
from src.evaluation.statistical_tests import compare_methods_across_companies
from src.formal.archive import FormalArchiveError, FormalRunArchive
from src.formal.validation import DEFAULT_FORMAL_RUNS_ROOT


PHASE_A_ANALYSIS_VERSION = "phase-a-v1"
DEFAULT_SUPPLEMENTARY_ROOT = SETTINGS.artifacts_dir / "evaluations" / "supplementary"


class SupplementaryAnalysisError(RuntimeError):
    """Raised when frozen source evidence cannot support a safe derivation."""


@dataclass(frozen=True, slots=True)
class SupplementaryAnalysisResult:
    output_directory: Path
    source_path: Path
    paired_mase_path: Path
    change_diagnostics_path: Path
    source_formal_integrity_aggregate_sha256: str
    company_count: int
    target_count_per_company: int
    generated: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "analysis_type": "supplementary_analysis",
            "analysis_version": PHASE_A_ANALYSIS_VERSION,
            "output_directory": str(self.output_directory),
            "source_path": str(self.source_path),
            "paired_mase_path": str(self.paired_mase_path),
            "change_diagnostics_path": str(self.change_diagnostics_path),
            "source_formal_integrity_aggregate_sha256": (
                self.source_formal_integrity_aggregate_sha256
            ),
            "company_count": self.company_count,
            "target_count_per_company": self.target_count_per_company,
            "generated": self.generated,
        }


def _load_json_object(path: Path) -> dict[str, object]:
    def reject_non_finite(value: str) -> object:
        raise ValueError(f"non-finite JSON constant {value}")

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_non_finite,
        )
    except (OSError, ValueError) as exc:
        raise SupplementaryAnalysisError(f"Cannot read JSON evidence {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SupplementaryAnalysisError(f"JSON evidence must be an object: {path}")
    return payload


def _metrics_from_evidence(
    payload: Mapping[str, object],
) -> dict[ModelId, EvaluationMetrics]:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise SupplementaryAnalysisError("Company evidence has no metrics object")
    parsed: dict[ModelId, EvaluationMetrics] = {}
    for model in ModelId:
        item = metrics.get(model.value)
        if not isinstance(item, dict):
            raise SupplementaryAnalysisError(
                f"Company evidence has no metrics for {model.value}"
            )
        try:
            parsed[model] = EvaluationMetrics(
                rmse=float(item["rmse"]),
                mae=float(item["mae"]),
                mase=float(item["mase"]),
                r2=float(item["r2"]),
                observations=int(item["observations"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SupplementaryAnalysisError(
                f"Malformed metrics for {model.value}: {exc}"
            ) from exc
    return parsed


def _existing_result(
    output_directory: Path,
    *,
    formal_run_id: str,
    aggregate_sha256: str,
) -> SupplementaryAnalysisResult | None:
    if not output_directory.exists():
        return None
    expected = {
        "source.json",
        "paired_mase_evidence.json",
        "change_diagnostics.json",
    }
    observed = {path.name for path in output_directory.iterdir() if path.is_file()}
    if observed != expected:
        raise SupplementaryAnalysisError(
            "Existing supplementary directory is incomplete or contains unexpected files"
        )
    source = _load_json_object(output_directory / "source.json")
    paired = _load_json_object(output_directory / "paired_mase_evidence.json")
    changes = _load_json_object(output_directory / "change_diagnostics.json")
    if (
        source.get("analysis_version") != PHASE_A_ANALYSIS_VERSION
        or source.get("source_formal_run_id") != formal_run_id
        or source.get("source_formal_integrity_aggregate_sha256") != aggregate_sha256
        or paired.get("analysis_version") != PHASE_A_ANALYSIS_VERSION
        or paired.get("source_formal_run_id") != formal_run_id
        or paired.get("source_formal_integrity_aggregate_sha256") != aggregate_sha256
        or changes.get("analysis_version") != PHASE_A_ANALYSIS_VERSION
        or changes.get("source_formal_run_id") != formal_run_id
        or changes.get("source_formal_integrity_aggregate_sha256") != aggregate_sha256
    ):
        raise SupplementaryAnalysisError(
            "Existing supplementary output does not match the requested formal source"
        )
    try:
        company_count = int(source["source_company_count"])
        target_count = int(source["source_target_count_per_company"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SupplementaryAnalysisError("Existing source metadata is malformed") from exc
    return SupplementaryAnalysisResult(
        output_directory=output_directory,
        source_path=output_directory / "source.json",
        paired_mase_path=output_directory / "paired_mase_evidence.json",
        change_diagnostics_path=output_directory / "change_diagnostics.json",
        source_formal_integrity_aggregate_sha256=aggregate_sha256,
        company_count=company_count,
        target_count_per_company=target_count,
        generated=False,
    )


def generate_phase_a_supplementary_analysis(
    formal_run_id: str,
    *,
    formal_runs_root: Path = DEFAULT_FORMAL_RUNS_ROOT,
    supplementary_root: Path = DEFAULT_SUPPLEMENTARY_ROOT,
) -> SupplementaryAnalysisResult:
    """Verify one finalized archive, derive evidence, and never mutate the source."""

    archive = FormalRunArchive(formal_run_id, root=formal_runs_root)
    if not archive.verify_integrity():
        raise SupplementaryAnalysisError("Formal archive integrity verification failed")
    manifest = _load_json_object(archive.path / "integrity_manifest.json")
    aggregate_sha256 = str(manifest.get("aggregate_sha256", ""))
    if not aggregate_sha256:
        raise SupplementaryAnalysisError("Formal integrity aggregate is missing")
    output_directory = (
        Path(supplementary_root) / formal_run_id / PHASE_A_ANALYSIS_VERSION
    ).resolve()
    existing = _existing_result(
        output_directory,
        formal_run_id=formal_run_id,
        aggregate_sha256=aggregate_sha256,
    )
    if existing is not None:
        return existing

    run = _load_json_object(archive.path / "run.json")
    symbols_value = run.get("expected_symbols")
    if not isinstance(symbols_value, list) or not symbols_value:
        raise SupplementaryAnalysisError("Formal run has no expected-symbol manifest")
    symbols = tuple(sorted(str(symbol) for symbol in symbols_value))
    metrics_by_company: dict[str, dict[ModelId, EvaluationMetrics]] = {}
    diagnostics: list[dict[str, object]] = []
    common_target_dates: tuple[str, ...] | None = None
    for symbol in symbols:
        company = _load_json_object(
            archive.path / "companies" / symbol / "evidence.json"
        )
        records_value = company.get("canonical_holdout_records")
        holdout_dates_value = company.get("holdout_target_dates")
        if not isinstance(records_value, list) or not isinstance(holdout_dates_value, list):
            raise SupplementaryAnalysisError(
                f"Formal company evidence is incomplete for {symbol}"
            )
        if any(not isinstance(item, dict) for item in records_value):
            raise SupplementaryAnalysisError(
                f"Canonical holdout records are malformed for {symbol}"
            )
        target_dates = tuple(str(value) for value in holdout_dates_value)
        record_dates = tuple(str(item.get("target_date")) for item in records_value)
        if record_dates != target_dates:
            raise SupplementaryAnalysisError(
                f"Canonical records and target-date manifest disagree for {symbol}"
            )
        if len(set(target_dates)) != len(target_dates) or target_dates != tuple(
            sorted(target_dates)
        ):
            raise SupplementaryAnalysisError(
                f"Formal target dates are duplicated or unordered for {symbol}"
            )
        if common_target_dates is None:
            common_target_dates = target_dates
        elif target_dates != common_target_dates:
            raise SupplementaryAnalysisError(
                f"Formal target dates differ across companies at {symbol}"
            )
        metrics_by_company[symbol] = _metrics_from_evidence(company)
        company_diagnostics = archived_change_diagnostics(
            symbol,
            records_value,
            archive.path / "frozen_raw" / f"{symbol}.csv",
        )
        diagnostics.extend(item.as_dict() for item in company_diagnostics)

    if common_target_dates is None:
        raise SupplementaryAnalysisError("Formal archive contains no target dates")
    comparison = compare_methods_across_companies(metrics_by_company)
    if comparison.company_count != len(symbols):
        raise SupplementaryAnalysisError("Paired evidence silently lost companies")
    expected_diagnostic_count = len(symbols) * len(ModelId)
    if len(diagnostics) != expected_diagnostic_count:
        raise SupplementaryAnalysisError("Movement diagnostics are incomplete")
    target_count = len(common_target_dates)
    if any(item["observation_count"] != target_count for item in diagnostics):
        raise SupplementaryAnalysisError("Movement diagnostic target counts disagree")

    git_state = run.get("git_state")
    source_git_commit = (
        git_state.get("commit") if isinstance(git_state, dict) else None
    )
    source_payload: dict[str, object] = {
        "schema_id": "forecastph.supplementary-analysis-source",
        "schema_version": 1,
        "analysis_type": "supplementary_analysis",
        "analysis_version": PHASE_A_ANALYSIS_VERSION,
        "source_formal_run_id": formal_run_id,
        "source_formal_integrity_aggregate_sha256": aggregate_sha256,
        "source_cutoff_date": run.get("cutoff_date"),
        "source_holdout_start": common_target_dates[0],
        "source_holdout_end": common_target_dates[-1],
        "source_company_count": len(symbols),
        "source_target_count_per_company": target_count,
        "source_company_order": list(symbols),
        "source_target_dates": list(common_target_dates),
        "generated_at": manila_now().isoformat(),
        "source_git_commit": source_git_commit,
    }
    paired_payload = comparison.paired_evidence_as_dict()
    paired_payload.update(
        {
            "analysis_type": "supplementary_analysis",
            "analysis_version": PHASE_A_ANALYSIS_VERSION,
            "source_formal_run_id": formal_run_id,
            "source_formal_integrity_aggregate_sha256": aggregate_sha256,
        }
    )
    change_payload: dict[str, object] = {
        "schema_id": "forecastph.supplementary-change-diagnostics",
        "schema_version": 1,
        "analysis_type": "supplementary_analysis",
        "analysis_version": PHASE_A_ANALYSIS_VERSION,
        "source_formal_run_id": formal_run_id,
        "source_formal_integrity_aggregate_sha256": aggregate_sha256,
        "company_count": len(symbols),
        "model_count_per_company": len(ModelId),
        "target_count_per_company_model": target_count,
        "diagnostics": diagnostics,
    }

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{PHASE_A_ANALYSIS_VERSION}-",
            dir=output_directory.parent,
        )
    )
    try:
        atomic_write_json(temporary / "source.json", source_payload)
        atomic_write_json(
            temporary / "paired_mase_evidence.json", paired_payload
        )
        atomic_write_json(
            temporary / "change_diagnostics.json", change_payload
        )
        temporary.replace(output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    if not archive.verify_integrity():
        raise FormalArchiveError(
            "Formal archive integrity changed while deriving supplementary evidence"
        )
    return SupplementaryAnalysisResult(
        output_directory=output_directory,
        source_path=output_directory / "source.json",
        paired_mase_path=output_directory / "paired_mase_evidence.json",
        change_diagnostics_path=output_directory / "change_diagnostics.json",
        source_formal_integrity_aggregate_sha256=aggregate_sha256,
        company_count=len(symbols),
        target_count_per_company=target_count,
        generated=True,
    )
