"""Lifecycle and tamper tests for Phase D supplementary packages."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.evaluation.supplementary_archive import (
    EVIDENCE_PATHS,
    FinalizedSupplementaryPackageError,
    SupplementaryArchiveError,
    SupplementaryEvidenceArchive,
)


PACKAGE_ID = "FORECASTPH_SUPPLEMENTARY_TEST_01"


def payloads() -> dict[str, dict[str, object]]:
    return {path: {"path": path, "finite": 1.0} for path in EVIDENCE_PATHS}


def finalized(tmp_path: Path) -> SupplementaryEvidenceArchive:
    archive = SupplementaryEvidenceArchive.create(
        PACKAGE_ID, source_formal_run_id="formal-test", root=tmp_path
    )
    values = payloads()
    values["source/formal_source.json"] = {
        "source_formal_run_id": "formal-test",
        "source_formal_integrity_aggregate_sha256": "a" * 64,
    }
    for path, payload in values.items():
        archive.write_json(path, payload)
    archive.finalize(source_formal_integrity_aggregate_sha256="a" * 64)
    return archive


def test_finalized_package_verifies_repeatedly_and_is_api_immutable(tmp_path: Path) -> None:
    archive = finalized(tmp_path)
    before = {
        path.relative_to(archive.path).as_posix(): path.read_bytes()
        for path in archive.path.rglob("*")
        if path.is_file()
    }

    assert archive.verify_integrity().valid
    assert archive.verify_integrity().valid
    after = {
        path.relative_to(archive.path).as_posix(): path.read_bytes()
        for path in archive.path.rglob("*")
        if path.is_file()
    }
    assert after == before
    with pytest.raises(FinalizedSupplementaryPackageError):
        archive.write_json(EVIDENCE_PATHS[0], {"late": True})
    with pytest.raises(FinalizedSupplementaryPackageError):
        SupplementaryEvidenceArchive.create(
            PACKAGE_ID, source_formal_run_id="formal-test", root=tmp_path
        )


def test_incomplete_and_failed_packages_cannot_finalize(tmp_path: Path) -> None:
    incomplete = SupplementaryEvidenceArchive.create(
        "FORECASTPH_SUPPLEMENTARY_INCOMPLETE", source_formal_run_id="formal", root=tmp_path
    )
    with pytest.raises(SupplementaryArchiveError, match="incomplete"):
        incomplete.finalize(source_formal_integrity_aggregate_sha256="a" * 64)
    incomplete.mark_failed(["synthetic"])
    with pytest.raises(SupplementaryArchiveError, match="terminal"):
        incomplete.finalize(source_formal_integrity_aggregate_sha256="a" * 64)


@pytest.mark.parametrize(
    "tamper",
    [
        "modify",
        "delete",
        "extra",
        "manifest_entry",
        "aggregate",
        "source_aggregate",
        "state",
    ],
)
def test_integrity_detects_file_manifest_and_state_tampering(tmp_path: Path, tamper: str) -> None:
    archive = finalized(tmp_path)
    if tamper == "modify":
        target = archive.path / EVIDENCE_PATHS[1]
        target.write_text('{"changed":true}\n', encoding="utf-8")
    elif tamper == "delete":
        (archive.path / EVIDENCE_PATHS[1]).unlink()
    elif tamper == "extra":
        (archive.path / "unexpected.json").write_text("{}\n", encoding="utf-8")
    elif tamper in {"manifest_entry", "aggregate", "source_aggregate"}:
        manifest_path = archive.path / "integrity_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if tamper == "manifest_entry":
            manifest["files"][0]["sha256"] = "0" * 64
        elif tamper == "source_aggregate":
            manifest["source_formal_integrity_aggregate_sha256"] = "0" * 64
        else:
            manifest["aggregate_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        state_path = archive.path / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["state"] = "FAILED"
        state_path.write_text(json.dumps(state), encoding="utf-8")

    assert not archive.verify_integrity().valid


def test_manifest_has_exact_ordered_file_set_and_finite_json(tmp_path: Path) -> None:
    archive = finalized(tmp_path)
    manifest = json.loads((archive.path / "integrity_manifest.json").read_text())
    paths = [item["path"] for item in manifest["files"]]
    assert paths == sorted(("run.json", "state.json", *EVIDENCE_PATHS))
    assert all(set(item) == {"path", "sha256", "size_bytes"} for item in manifest["files"])
    assert json.dumps(deepcopy(manifest), allow_nan=False)
