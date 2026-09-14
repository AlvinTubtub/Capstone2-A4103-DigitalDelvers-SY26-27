"""Truthful environment and raw-source provenance for formal runs."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from importlib import metadata as importlib_metadata
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from config.companies import Company
from src.data.validator import OhlcvRecord
from src.formal.schema import CorporateActionRecord, FormalSchemaError


FORMAL_DEPENDENCIES = (
    "joblib",
    "numpy",
    "pandas",
    "scikit-learn",
    "scipy",
    "statsmodels",
    "torch",
)


def sha256_file(path: Path) -> str:
    """Hash file bytes without parsing or rewriting them."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class GitState:
    commit: str | None
    branch: str | None
    dirty: bool | None
    changed_paths: tuple[str, ...]
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "commit": self.commit,
            "branch": self.branch,
            "dirty": self.dirty,
            "changed_paths": list(self.changed_paths),
            "unavailable_reason": self.unavailable_reason,
        }


def _git(repository_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.rstrip("\r\n")


def capture_git_state(repository_root: Path) -> GitState:
    """Capture commit, branch, and exact dirty paths without changing Git state."""

    try:
        commit = _git(repository_root, "rev-parse", "HEAD")
        branch = _git(repository_root, "branch", "--show-current") or None
        status = _git(
            repository_root,
            "-c",
            "core.fsmonitor=false",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return GitState(None, None, None, (), f"{type(exc).__name__}: {exc}")
    changed_paths = tuple(
        line[3:] for line in status.splitlines() if len(line) >= 4
    )
    return GitState(commit, branch, bool(changed_paths), changed_paths)


def capture_environment() -> dict[str, object]:
    versions: dict[str, str | None] = {}
    for dependency in FORMAL_DEPENDENCIES:
        try:
            versions[dependency] = importlib_metadata.version(dependency)
        except importlib_metadata.PackageNotFoundError:
            versions[dependency] = None
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "package_versions": versions,
    }


@dataclass(frozen=True, slots=True)
class RawCsvProvenance:
    symbol: str
    path: str
    source_name: str | None
    source_reference: str | None
    retrieval_date: date | None
    sha256: str
    first_date: date
    last_date: date
    row_count: int
    correction_history: tuple[Mapping[str, object], ...]
    notes: str | None

    @property
    def missing_required_fields(self) -> tuple[str, ...]:
        required = {
            "source_name": self.source_name,
            "source_reference": self.source_reference,
            "retrieval_date": self.retrieval_date,
        }
        return tuple(name for name, value in required.items() if value is None)

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "path": self.path,
            "source_name": self.source_name,
            "source_reference": self.source_reference,
            "retrieval_date": (
                self.retrieval_date.isoformat()
                if self.retrieval_date is not None
                else None
            ),
            "sha256": self.sha256,
            "first_date": self.first_date.isoformat(),
            "last_date": self.last_date.isoformat(),
            "row_count": self.row_count,
            "correction_history": [dict(item) for item in self.correction_history],
            "notes": self.notes,
            "missing_required_fields": list(self.missing_required_fields),
        }


def load_provenance_registry(path: Path) -> dict[str, Mapping[str, object]]:
    """Load declared metadata; absent facts remain absent rather than inferred."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalSchemaError(f"Cannot read provenance registry: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise FormalSchemaError("Unsupported provenance registry schema")
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        raise FormalSchemaError("Provenance registry sources must be an object")
    if any(not isinstance(symbol, str) or not isinstance(value, dict) for symbol, value in sources.items()):
        raise FormalSchemaError("Provenance registry entries must be objects")
    return sources


def build_raw_provenance(
    company: Company,
    raw_path: Path,
    records: Sequence[OhlcvRecord],
    declared: Mapping[str, object] | None,
) -> RawCsvProvenance:
    """Combine computed facts with only explicitly declared source facts."""

    if not records:
        raise FormalSchemaError(f"No raw records for {company.symbol}")
    metadata = {} if declared is None else dict(declared)
    retrieval_value = metadata.get("retrieval_date")
    try:
        retrieval_date = (
            date.fromisoformat(retrieval_value)
            if isinstance(retrieval_value, str)
            else None
        )
    except ValueError as exc:
        raise FormalSchemaError(
            f"Invalid retrieval_date for {company.symbol}"
        ) from exc
    corrections = metadata.get("correction_history", [])
    if not isinstance(corrections, list) or any(
        not isinstance(item, dict) for item in corrections
    ):
        raise FormalSchemaError(
            f"correction_history must be a list of objects for {company.symbol}"
        )
    for correction in corrections:
        if set(correction) != {"date", "description", "source"}:
            raise FormalSchemaError(
                "Correction records require exactly date, description, and source"
            )
        try:
            date.fromisoformat(correction["date"])
        except (TypeError, ValueError) as exc:
            raise FormalSchemaError("Correction record date must use YYYY-MM-DD") from exc
        if any(
            not isinstance(correction[field], str) or not correction[field].strip()
            for field in ("description", "source")
        ):
            raise FormalSchemaError(
                "Correction description and source must be non-empty strings"
            )
    source_name = metadata.get("source_name")
    source_reference = metadata.get("source_reference")
    notes = metadata.get("notes")
    for name, value in (
        ("source_name", source_name),
        ("source_reference", source_reference),
        ("notes", notes),
    ):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise FormalSchemaError(f"{name} must be a non-empty string or null")
    return RawCsvProvenance(
        symbol=company.symbol,
        path=str(Path(raw_path).resolve()),
        source_name=source_name,
        source_reference=source_reference,
        retrieval_date=retrieval_date,
        sha256=sha256_file(raw_path),
        first_date=records[0].trading_date,
        last_date=records[-1].trading_date,
        row_count=len(records),
        correction_history=tuple(corrections),
        notes=notes,
    )


def load_corporate_action_registry(path: Path) -> tuple[CorporateActionRecord, ...]:
    """Validate explicitly supplied actions; an empty registry is valid."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalSchemaError(f"Cannot read corporate-action registry: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise FormalSchemaError("Unsupported corporate-action registry schema")
    actions = payload.get("actions")
    if not isinstance(actions, list):
        raise FormalSchemaError("Corporate actions must be an array")
    parsed: list[CorporateActionRecord] = []
    for item in actions:
        if not isinstance(item, dict):
            raise FormalSchemaError("Corporate action entries must be objects")
        try:
            parsed.append(
                CorporateActionRecord(
                    symbol=item["symbol"],
                    action_date=date.fromisoformat(item["date"]),
                    action_type=item["action_type"],
                    source=item.get("source"),
                    verified=item["verified"],
                    notes=item.get("notes"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FormalSchemaError("Malformed corporate action entry") from exc
    return tuple(parsed)
