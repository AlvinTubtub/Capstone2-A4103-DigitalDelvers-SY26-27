"""Tamper-detectable storage for finalized supplementary evidence packages."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from config.settings import SETTINGS, manila_now
from src.artifacts.io import atomic_write_json
from src.formal.provenance import sha256_file


SUPPLEMENTARY_EVIDENCE_SCHEMA_ID = "forecastph.supplementary-evidence-package"
SUPPLEMENTARY_EVIDENCE_SCHEMA_VERSION = 1
SUPPLEMENTARY_MANIFEST_SCHEMA_ID = "forecastph.supplementary-integrity-manifest"
DEFAULT_SUPPLEMENTARY_RUNS_ROOT = (
    SETTINGS.artifacts_dir / "evaluations" / "supplementary-runs"
)
PACKAGE_ID_PATTERN = re.compile(r"^FORECASTPH_SUPPLEMENTARY_[A-Za-z0-9._-]{3,64}$")

EVIDENCE_PATHS: tuple[str, ...] = (
    "source/formal_source.json",
    "source/code_provenance.json",
    "source/prospective_source.json",
    "historical/formal_holdout_index.json",
    "historical/paired_mase_evidence.json",
    "historical/change_diagnostics.json",
    "historical/reporting_semantics.json",
    "historical/mase_denominator_audit.json",
    "methodology/lir_feature_contract.json",
    "methodology/arima_diagnostic_status.json",
    "prospective/prospective_validation_snapshot.json",
)
MANIFESTED_PATHS: tuple[str, ...] = (
    "run.json",
    "state.json",
    *EVIDENCE_PATHS,
)


class SupplementaryPackageState(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    FINALIZED = "FINALIZED"


class SupplementaryArchiveError(RuntimeError):
    """Raised for unsafe, incomplete, or immutable package operations."""


class FinalizedSupplementaryPackageError(SupplementaryArchiveError):
    """Raised when a finalized package would be reused or modified."""


@dataclass(frozen=True, slots=True)
class VerificationResult:
    valid: bool
    checks: Mapping[str, bool]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "checks": dict(self.checks),
            "errors": list(self.errors),
        }


def validate_package_id(package_id: str) -> str:
    if not isinstance(package_id, str) or PACKAGE_ID_PATTERN.fullmatch(package_id) is None:
        raise SupplementaryArchiveError(
            "package_id must begin FORECASTPH_SUPPLEMENTARY_ and use safe characters"
        )
    return package_id


def aggregate_entries(entries: Sequence[Mapping[str, object]]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: str(item["path"])):
        digest.update(f"{entry['path']}\0{entry['sha256']}\n".encode())
    return digest.hexdigest()


class SupplementaryEvidenceArchive:
    """A separate evidence package with atomic publication at finalization."""

    def __init__(self, package_id: str, *, root: Path = DEFAULT_SUPPLEMENTARY_RUNS_ROOT):
        self.package_id = validate_package_id(package_id)
        self.root = Path(root).resolve()
        self.path = (self.root / self.package_id).resolve()
        if self.path.parent != self.root:
            raise SupplementaryArchiveError("Unsafe supplementary package path")
        self._staging_path: Path | None = None

    @classmethod
    def create(
        cls,
        package_id: str,
        *,
        source_formal_run_id: str,
        root: Path = DEFAULT_SUPPLEMENTARY_RUNS_ROOT,
    ) -> "SupplementaryEvidenceArchive":
        archive = cls(package_id, root=root)
        if archive.path.exists():
            try:
                existing_state = archive.state
            except SupplementaryArchiveError:
                existing_state = None
            if existing_state is SupplementaryPackageState.FINALIZED:
                raise FinalizedSupplementaryPackageError(
                    f"Finalized package ID already exists: {package_id}"
                )
            raise SupplementaryArchiveError(f"Package ID already exists: {package_id}")
        archive.root.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=f".{package_id}-", dir=archive.root)
        ).resolve()
        archive._staging_path = staging
        created_at = manila_now().isoformat()
        atomic_write_json(
            staging / "run.json",
            {
                "schema_id": SUPPLEMENTARY_EVIDENCE_SCHEMA_ID,
                "schema_version": SUPPLEMENTARY_EVIDENCE_SCHEMA_VERSION,
                "package_id": package_id,
                "source_formal_run_id": source_formal_run_id,
                "created_at": created_at,
            },
        )
        archive._write_state(SupplementaryPackageState.IN_PROGRESS, base=staging)
        return archive

    @property
    def working_path(self) -> Path:
        return self._staging_path or self.path

    @property
    def state(self) -> SupplementaryPackageState:
        try:
            payload = json.loads(
                (self.working_path / "state.json").read_text(encoding="utf-8")
            )
            return SupplementaryPackageState(payload["state"])
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise SupplementaryArchiveError("Supplementary package state is unreadable") from exc

    def _write_state(
        self,
        state: SupplementaryPackageState,
        *,
        base: Path | None = None,
        errors: Sequence[str] = (),
    ) -> None:
        atomic_write_json(
            (base or self.working_path) / "state.json",
            {
                "package_id": self.package_id,
                "state": state.value,
                "updated_at": manila_now().isoformat(),
                "errors": list(errors),
            },
        )

    def _ensure_writable(self) -> None:
        if self._staging_path is None:
            if self.path.exists() and self.state is SupplementaryPackageState.FINALIZED:
                raise FinalizedSupplementaryPackageError(
                    f"Finalized package is immutable through the API: {self.package_id}"
                )
            raise SupplementaryArchiveError("Package was not opened for creation")
        if self.state is not SupplementaryPackageState.IN_PROGRESS:
            raise SupplementaryArchiveError(f"Package is terminal with state {self.state.value}")

    def write_json(self, relative_path: str, payload: Mapping[str, object]) -> Path:
        self._ensure_writable()
        if relative_path not in EVIDENCE_PATHS:
            raise SupplementaryArchiveError(f"Unexpected supplementary evidence path: {relative_path}")
        destination = (self.working_path / relative_path).resolve()
        if self.working_path not in destination.parents:
            raise SupplementaryArchiveError("Package path escapes staging directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(destination, payload)
        return destination

    def mark_failed(self, errors: Sequence[str]) -> None:
        self._ensure_writable()
        messages = tuple(str(item) for item in errors if str(item))
        if not messages:
            raise SupplementaryArchiveError("FAILED state requires an error")
        self._write_state(SupplementaryPackageState.FAILED, errors=messages)

    def finalize(
        self,
        *,
        source_formal_integrity_aggregate_sha256: str,
    ) -> Path:
        self._ensure_writable()
        missing = [path for path in EVIDENCE_PATHS if not (self.working_path / path).is_file()]
        if missing:
            raise SupplementaryArchiveError(f"Supplementary package is incomplete; missing={missing}")
        self._write_state(SupplementaryPackageState.FINALIZED)
        entries = [
            {
                "path": relative,
                "sha256": sha256_file(self.working_path / relative),
                "size_bytes": (self.working_path / relative).stat().st_size,
            }
            for relative in sorted(MANIFESTED_PATHS)
        ]
        formal_source = json.loads(
            (self.working_path / "source/formal_source.json").read_text(encoding="utf-8")
        )
        manifest = {
            "schema_id": SUPPLEMENTARY_MANIFEST_SCHEMA_ID,
            "schema_version": SUPPLEMENTARY_EVIDENCE_SCHEMA_VERSION,
            "package_id": self.package_id,
            "source_formal_run_id": formal_source["source_formal_run_id"],
            "source_formal_integrity_aggregate_sha256": source_formal_integrity_aggregate_sha256,
            "finalized_at": manila_now().isoformat(),
            "files": entries,
            "aggregate_sha256": aggregate_entries(entries),
        }
        atomic_write_json(self.working_path / "integrity_manifest.json", manifest)
        staging = self.working_path
        if self.path.exists():
            raise SupplementaryArchiveError(f"Package ID already exists: {self.package_id}")
        staging.replace(self.path)
        self._staging_path = None
        return self.path / "integrity_manifest.json"

    def abort_staging(self) -> None:
        if self._staging_path is not None:
            shutil.rmtree(self._staging_path, ignore_errors=True)
            self._staging_path = None

    def verify_integrity(self) -> VerificationResult:
        checks: dict[str, bool] = {}
        errors: list[str] = []
        try:
            manifest = json.loads((self.path / "integrity_manifest.json").read_text(encoding="utf-8"))
            run = json.loads((self.path / "run.json").read_text(encoding="utf-8"))
            state_payload = json.loads((self.path / "state.json").read_text(encoding="utf-8"))
            formal_source = json.loads(
                (self.path / "source/formal_source.json").read_text(encoding="utf-8")
            )
            checks["state_finalized"] = self.state is SupplementaryPackageState.FINALIZED
            checks["run_schema"] = (
                run.get("schema_id") == SUPPLEMENTARY_EVIDENCE_SCHEMA_ID
                and run.get("schema_version") == SUPPLEMENTARY_EVIDENCE_SCHEMA_VERSION
                and run.get("package_id") == self.package_id
                and state_payload.get("package_id") == self.package_id
            )
            checks["manifest_schema"] = (
                manifest.get("schema_id") == SUPPLEMENTARY_MANIFEST_SCHEMA_ID
                and manifest.get("schema_version") == SUPPLEMENTARY_EVIDENCE_SCHEMA_VERSION
                and manifest.get("package_id") == self.package_id
            )
            checks["source_identity"] = (
                manifest.get("source_formal_run_id")
                == run.get("source_formal_run_id")
                == formal_source.get("source_formal_run_id")
                and manifest.get("source_formal_integrity_aggregate_sha256")
                == formal_source.get("source_formal_integrity_aggregate_sha256")
            )
            entries = manifest.get("files")
            if not isinstance(entries, list):
                raise ValueError("manifest files must be a list")
            paths = [entry.get("path") for entry in entries if isinstance(entry, dict)]
            checks["manifest_paths_unique_ordered"] = paths == sorted(set(paths))
            actual = {
                path.relative_to(self.path).as_posix()
                for path in self.path.rglob("*")
                if path.is_file() and path.name != "integrity_manifest.json"
            }
            checks["exact_file_set"] = set(paths) == actual == set(MANIFESTED_PATHS)
            hashes_ok = True
            sizes_ok = True
            for entry in entries:
                relative = entry["path"]
                path = self.path / relative
                if not path.is_file():
                    hashes_ok = sizes_ok = False
                    continue
                hashes_ok &= sha256_file(path) == entry.get("sha256")
                sizes_ok &= path.stat().st_size == entry.get("size_bytes")
            checks["file_hashes"] = hashes_ok
            checks["file_sizes"] = sizes_ok
            checks["aggregate_sha256"] = (
                aggregate_entries(entries) == manifest.get("aggregate_sha256")
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        for name, passed in checks.items():
            if not passed:
                errors.append(f"failed check: {name}")
        return VerificationResult(not errors and all(checks.values()), checks, tuple(errors))
