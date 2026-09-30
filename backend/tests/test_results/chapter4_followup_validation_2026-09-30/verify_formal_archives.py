"""Read-only integrity verification for formal-run archive candidates."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_ROOT))

from src.formal.archive import FormalRunArchive


def verify(candidate_text: str) -> bool:
    candidate = Path(candidate_text).resolve()
    print(f"Candidate: {candidate}")
    print(f"Exists: {candidate.is_dir()}")
    if not candidate.is_dir():
        print("State: UNAVAILABLE")
        print("Integrity verified: False")
        return False

    archive = FormalRunArchive(candidate.name, root=candidate.parent)
    try:
        state = archive.state.value
    except Exception as exc:  # Evidence script must report malformed candidates.
        print(f"State: ERROR ({type(exc).__name__}: {exc})")
        print("Integrity verified: False")
        return False

    integrity = archive.verify_integrity()
    print(f"State: {state}")
    print(f"Integrity verified: {integrity}")
    return state == "FINALIZED" and integrity is True


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: verify_formal_archives.py ARCHIVE_DIR [...]", file=sys.stderr)
        return 64
    results = []
    for candidate in sys.argv[1:]:
        print("---")
        results.append(verify(candidate))
    print("---")
    print(f"Authentic finalized candidates: {sum(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
