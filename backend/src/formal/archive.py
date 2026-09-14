"""Fail-closed immutable storage for generated formal-run evidence."""

from collections.abc import Mapping, Sequence
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil

from config.companies import COMPANIES
from config.settings import manila_now
from src.artifacts.io import atomic_write_json
from src.formal.provenance import sha256_file
from src.formal.schema import (
    FORMAL_SCHEMA_ID,
    FORMAL_SCHEMA_VERSION,
    FormalRunState,
    FormalSchemaError,
    validate_company_evidence_payload,
    validate_run_id,
)
from src.formal.validation import DEFAULT_FORMAL_RUNS_ROOT


class FormalArchiveError(RuntimeError):
    """Raised for unsafe, incomplete, or immutable archive operations."""


class FinalizedRunError(FormalArchiveError):
    """Raised whenever a finalized run would be reused or changed."""


class FormalRunArchive:
    """One run directory with terminal FAILED/FINALIZED lifecycle states."""

    def __init__(
        self,
        run_id: str,
        *,
        root: Path = DEFAULT_FORMAL_RUNS_ROOT,
        expected_symbols: Sequence[str] = tuple(
            company.symbol for company in COMPANIES
        ),
    ) -> None:
        self.run_id = validate_run_id(run_id)
        self.root = Path(root).resolve()
        self.path = (self.root / self.run_id).resolve()
        if self.path.parent != self.root:
            raise FormalArchiveError("Unsafe formal run path")
        self.expected_symbols = tuple(sorted(expected_symbols))

    @classmethod
    def create(
        cls,
        run_id: str,
        cutoff_date: date,
        *,
        git_state: Mapping[str, object],
        environment: Mapping[str, object],
        root: Path = DEFAULT_FORMAL_RUNS_ROOT,
        expected_symbols: Sequence[str] = tuple(
            company.symbol for company in COMPANIES
        ),
    ) -> "FormalRunArchive":
        archive = cls(run_id, root=root, expected_symbols=expected_symbols)
        if archive.path.exists():
            try:
                state = archive.state
            except FormalArchiveError:
                state = None
            if state is FormalRunState.FINALIZED:
                raise FinalizedRunError(f"Finalized run ID already exists: {run_id}")
            raise FormalArchiveError(f"Formal run ID already exists: {run_id}")
        archive.path.mkdir(parents=True, exist_ok=False)
        for relative in (
            "configuration",
            "provenance",
            "frozen_raw",
            "companies",
            "statistics",
            "logs",
        ):
            (archive.path / relative).mkdir()
        timestamp = manila_now().isoformat()
        atomic_write_json(
            archive.path / "run.json",
            {
                "schema_id": FORMAL_SCHEMA_ID,
                "schema_version": FORMAL_SCHEMA_VERSION,
                "run_id": archive.run_id,
                "cutoff_date": cutoff_date.isoformat(),
                "created_at": timestamp,
                "git_state": dict(git_state),
                "environment": dict(environment),
                "expected_symbols": list(archive.expected_symbols),
            },
        )
        archive._write_state(FormalRunState.IN_PROGRESS, timestamp=timestamp)
        (archive.path / "logs" / "events.jsonl").touch()
        archive.append_event("archive_created", {"cutoff_date": cutoff_date.isoformat()})
        return archive

    @property
    def state(self) -> FormalRunState:
        try:
            payload = json.loads(
                (self.path / "state.json").read_text(encoding="utf-8")
            )
            return FormalRunState(payload["state"])
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise FormalArchiveError("Formal run state is unreadable") from exc

    def _write_state(
        self,
        state: FormalRunState,
        *,
        timestamp: str | None = None,
        errors: Sequence[str] = (),
    ) -> None:
        atomic_write_json(
            self.path / "state.json",
            {
                "run_id": self.run_id,
                "state": state.value,
                "updated_at": timestamp or manila_now().isoformat(),
                "errors": list(errors),
            },
        )

    def _ensure_in_progress(self) -> None:
        state = self.state
        if state is FormalRunState.FINALIZED:
            raise FinalizedRunError(f"Finalized run is immutable: {self.run_id}")
        if state is not FormalRunState.IN_PROGRESS:
            raise FormalArchiveError(f"Run is terminal with state {state.value}")

    def _safe_path(self, relative_path: str) -> Path:
        if not relative_path or Path(relative_path).is_absolute():
            raise FormalArchiveError("Archive path must be non-empty and relative")
        destination = (self.path / relative_path).resolve()
        if self.path not in destination.parents:
            raise FormalArchiveError("Archive path escapes the run directory")
        return destination

    def write_json(self, relative_path: str, payload: Mapping[str, object]) -> Path:
        self._ensure_in_progress()
        destination = self._safe_path(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(destination, payload)
        return destination

    def snapshot_raw_csv(self, symbol: str, source: Path) -> Path:
        """Copy source bytes once; never transform or overwrite them."""

        self._ensure_in_progress()
        if symbol not in self.expected_symbols:
            raise FormalArchiveError(f"Unexpected formal symbol: {symbol}")
        destination = self._safe_path(f"frozen_raw/{symbol}.csv")
        if destination.exists():
            raise FormalArchiveError(f"Frozen raw snapshot already exists: {symbol}")
        shutil.copyfile(source, destination)
        return destination

    def append_event(
        self,
        event: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self._ensure_in_progress()
        payload = {
            "timestamp": manila_now().isoformat(),
            "event": event,
            "details": dict(details or {}),
        }
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
        with (self.path / "logs" / "events.jsonl").open("a", encoding="utf-8") as output:
            output.write(encoded + "\n")

    def mark_failed(self, errors: Sequence[str]) -> None:
        self._ensure_in_progress()
        messages = tuple(str(error) for error in errors if str(error))
        if not messages:
            raise FormalArchiveError("FAILED state requires at least one error")
        self.append_event("run_failed", {"errors": list(messages)})
        self._write_state(FormalRunState.FAILED, errors=messages)

    def _required_paths(self) -> tuple[str, ...]:
        common = (
            "run.json",
            "state.json",
            "configuration/model_config.json",
            "provenance/readiness.json",
            "provenance/raw_files.json",
            "provenance/session_completeness.json",
            "provenance/corporate_actions.json",
            "statistics/across_company.json",
            "logs/events.jsonl",
        )
        company_paths = tuple(
            f"companies/{symbol}/evidence.json" for symbol in self.expected_symbols
        )
        raw_paths = tuple(f"frozen_raw/{symbol}.csv" for symbol in self.expected_symbols)
        return common + company_paths + raw_paths

    def _validate_completeness(self) -> None:
        missing = [
            relative
            for relative in self._required_paths()
            if not self._safe_path(relative).is_file()
        ]
        if missing:
            raise FormalArchiveError(f"Formal run is incomplete; missing={missing}")
        for symbol in self.expected_symbols:
            evidence_path = self._safe_path(f"companies/{symbol}/evidence.json")
            try:
                payload = json.loads(evidence_path.read_text(encoding="utf-8"))
                validate_company_evidence_payload(payload)
            except (OSError, json.JSONDecodeError, FormalSchemaError) as exc:
                raise FormalArchiveError(
                    f"Invalid company evidence for {symbol}: {exc}"
                ) from exc
        try:
            provenance_payload = json.loads(
                self._safe_path("provenance/raw_files.json").read_text(encoding="utf-8")
            )
            provenance_by_symbol = {
                item["symbol"]: item for item in provenance_payload["raw_files"]
            }
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise FormalArchiveError("Raw provenance manifest is invalid") from exc
        for symbol in self.expected_symbols:
            expected_hash = provenance_by_symbol.get(symbol, {}).get("sha256")
            observed_hash = sha256_file(self._safe_path(f"frozen_raw/{symbol}.csv"))
            if expected_hash != observed_hash:
                raise FormalArchiveError(
                    f"Frozen raw hash disagrees with provenance for {symbol}"
                )

    def finalize(self) -> Path:
        """Validate once, write integrity checksums, and enter immutable state."""

        self._ensure_in_progress()
        self._validate_completeness()
        self.append_event("run_finalized", {})
        self._write_state(FormalRunState.FINALIZED)
        files = tuple(
            sorted(
                path
                for path in self.path.rglob("*")
                if path.is_file() and path.name != "integrity_manifest.json"
            )
        )
        entries = [
            {
                "path": path.relative_to(self.path).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ]
        aggregate = hashlib.sha256()
        for entry in entries:
            aggregate.update(f"{entry['path']}\0{entry['sha256']}\n".encode())
        manifest_path = self.path / "integrity_manifest.json"
        atomic_write_json(
            manifest_path,
            {
                "schema_id": "forecastph.formal-integrity-manifest",
                "schema_version": FORMAL_SCHEMA_VERSION,
                "run_id": self.run_id,
                "files": entries,
                "aggregate_sha256": aggregate.hexdigest(),
            },
        )
        return manifest_path

    def verify_integrity(self) -> bool:
        try:
            manifest = json.loads(
                (self.path / "integrity_manifest.json").read_text(encoding="utf-8")
            )
            if self.state is not FormalRunState.FINALIZED:
                return False
            expected_paths = {entry["path"] for entry in manifest["files"]}
            actual_paths = {
                path.relative_to(self.path).as_posix()
                for path in self.path.rglob("*")
                if path.is_file() and path.name != "integrity_manifest.json"
            }
            if actual_paths != expected_paths:
                return False
            aggregate = hashlib.sha256()
            for entry in manifest["files"]:
                path = self._safe_path(entry["path"])
                if sha256_file(path) != entry["sha256"]:
                    return False
                aggregate.update(
                    f"{entry['path']}\0{entry['sha256']}\n".encode()
                )
            return aggregate.hexdigest() == manifest["aggregate_sha256"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return False
