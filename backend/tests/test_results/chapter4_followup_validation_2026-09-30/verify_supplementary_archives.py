"""Read-only verification of historical supplementary evidence archives."""

from __future__ import annotations

import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_ROOT))

from src.evaluation.supplementary_archive import (  # noqa: E402
    SupplementaryEvidenceArchive,
    SupplementaryPackageState,
)
from src.evaluation.supplementary_evidence import (  # noqa: E402
    load_and_validate_finalized_payloads,
    verify_source_linkage,
)


EXPECTED_PACKAGE_ID = "FORECASTPH_SUPPLEMENTARY_20260921_03"
EXPECTED_FORMAL_RUN_ID = "FORECASTPH_FORMAL_20260911_01"


def load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def verify(candidate_text: str, formal_root_text: str) -> bool:
    candidate = Path(candidate_text).resolve()
    formal_root = Path(formal_root_text).resolve()
    print(f"Candidate: {candidate}")
    print(f"Exists: {candidate.is_dir()}")
    print(f"Integrity manifest present: {(candidate / 'integrity_manifest.json').is_file()}")
    if not candidate.is_dir():
        return False

    package = SupplementaryEvidenceArchive(candidate.name, root=candidate.parent)
    integrity = package.verify_integrity()
    print("Integrity result:")
    print(json.dumps(integrity.as_dict(), indent=2, sort_keys=True))

    try:
        run = load_json(candidate / "run.json")
        state = package.state
        manifest = load_json(candidate / "integrity_manifest.json")
        formal_source = load_json(candidate / "source" / "formal_source.json")
        print(f"State: {state.value}")
        print(f"Run schema: {run.get('schema_id')} v{run.get('schema_version')}")
        print(f"Package ID: {run.get('package_id')}")
        print(f"Source formal run ID: {run.get('source_formal_run_id')}")
        print(f"Manifest aggregate SHA-256: {manifest.get('aggregate_sha256')}")
        print(
            "Source formal aggregate SHA-256: "
            f"{formal_source.get('source_formal_integrity_aggregate_sha256')}"
        )
        semantic_payloads = load_and_validate_finalized_payloads(
            package,
            formal_runs_root=formal_root,
        )
        print(f"Semantic validation: PASS ({len(semantic_payloads)} evidence payloads)")
        linkage = verify_source_linkage(
            package,
            formal_runs_root=formal_root,
            ledger_path=None,
        )
        print("Formal source linkage:")
        print(json.dumps(linkage.as_dict(), indent=2, sort_keys=True))
    except Exception as exc:
        print(f"Semantic/source verification error: {type(exc).__name__}: {exc}")
        return False

    expected_identity = (
        candidate.name == EXPECTED_PACKAGE_ID
        and run.get("package_id") == EXPECTED_PACKAGE_ID
        and run.get("source_formal_run_id") == EXPECTED_FORMAL_RUN_ID
        and formal_source.get("source_formal_run_id") == EXPECTED_FORMAL_RUN_ID
        and manifest.get("source_formal_run_id") == EXPECTED_FORMAL_RUN_ID
    )
    print(f"Expected historical identity: {expected_identity}")
    valid = (
        integrity.valid
        and state is SupplementaryPackageState.FINALIZED
        and linkage.valid
        and expected_identity
    )
    print(f"Overall verified: {valid}")
    return valid


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: verify_supplementary_archives.py ARCHIVE_DIR FORMAL_RUNS_ROOT",
            file=sys.stderr,
        )
        return 64
    return 0 if verify(sys.argv[1], sys.argv[2]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
