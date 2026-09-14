"""Formal archive, provenance, readiness, and no-training preflight tests."""

from datetime import date, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from config.companies import COMPANIES
from config.model_config import ModelId
from scripts.run_formal_experiment import build_parser
from src.data.calendar import PSETradingCalendar
from src.formal.archive import (
    FinalizedRunError,
    FormalArchiveError,
    FormalRunArchive,
)
from src.formal.provenance import (
    GitState,
    build_raw_provenance,
    capture_git_state,
    sha256_file,
)
from src.formal.runner import FormalRunRequest, run_formal_experiment
from src.formal.schema import (
    CorporateActionRecord,
    FormalCompanyEvidence,
    FormalReadinessReport,
    FormalRunState,
    FormalSchemaError,
)
from src.formal.validation import analyze_session_completeness, assess_formal_readiness


MANILA = ZoneInfo("Asia/Manila")


def write_raw_csv(path: Path) -> None:
    path.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-01-02,100,101,99,100.5,1000\n"
        "2026-01-05,101,102,100,101.5,1200\n",
        encoding="utf-8",
    )


def minimal_evidence(symbol: str = "ALI") -> FormalCompanyEvidence:
    development = (date(2026, 1, 2),)
    holdout = (date(2026, 1, 5),)
    return FormalCompanyEvidence(
        symbol=symbol,
        development_target_dates=development,
        holdout_target_dates=holdout,
        cv_fold_target_date_manifests={"folds": ["present"]},
        model_grids_and_seeds={"models": "present"},
        tuning_and_fold_scores={"scores": "present"},
        selected_configurations={"selected": "present"},
        lasso_boundary_metadata={"lower": False, "upper": False, "interior": True},
        arima_diagnostics={"selected_fitted_model": "present"},
        lstm_seed_epoch_metadata={"seed": 42, "epoch": 1},
        canonical_holdout_records=(
            {
                "company": symbol,
                "target_date": "2026-01-05",
                "actual_close": 101.5,
                "lir_prediction": 101.0,
                "arima_prediction": 101.1,
                "lstm_prediction": 101.2,
                "naive_prediction": 100.5,
            },
        ),
        metrics={
            model.value: {
                "rmse": 1.0,
                "mae": 0.8,
                "mase": 0.9,
                "r2": -0.2,
            }
            for model in ModelId
        },
        statistical_tests={"diebold_mariano": "present"},
    )


def complete_archive(tmp_path: Path, run_id: str = "formal-test-001") -> FormalRunArchive:
    root = tmp_path / "formal-runs"
    raw = tmp_path / "ALI.csv"
    write_raw_csv(raw)
    archive = FormalRunArchive.create(
        run_id,
        date(2026, 1, 5),
        git_state={"commit": "a" * 40, "branch": "main", "dirty": False},
        environment={"python_version": "3.12.0", "package_versions": {}},
        root=root,
        expected_symbols=("ALI",),
    )
    snapshot = archive.snapshot_raw_csv("ALI", raw)
    archive.write_json("configuration/model_config.json", {"config": "present"})
    archive.write_json("provenance/readiness.json", {"status": "READY"})
    archive.write_json(
        "provenance/raw_files.json",
        {
            "raw_files": [
                {"symbol": "ALI", "sha256": sha256_file(snapshot)}
            ]
        },
    )
    archive.write_json("provenance/session_completeness.json", {"ALI": "complete"})
    archive.write_json("provenance/corporate_actions.json", {"actions": []})
    archive.write_json("statistics/across_company.json", {"friedman": "present"})
    archive.write_json("companies/ALI/evidence.json", minimal_evidence().as_dict())
    return archive


def clean_git_state() -> GitState:
    return GitState("a" * 40, "main", False, ())


def test_same_file_has_same_hash_and_changed_file_has_changed_hash(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_bytes(b"same bytes\n")
    second.write_bytes(b"same bytes\n")

    initial = sha256_file(first)
    assert initial == sha256_file(first) == sha256_file(second)
    second.write_bytes(b"changed bytes\n")
    assert sha256_file(second) != initial


def test_finalized_run_is_immutable_and_run_id_cannot_be_reused(tmp_path: Path) -> None:
    archive = complete_archive(tmp_path)
    manifest = archive.finalize()

    assert archive.state is FormalRunState.FINALIZED
    assert manifest.is_file()
    assert archive.verify_integrity()
    with pytest.raises(FinalizedRunError):
        archive.write_json("late.json", {"not": "allowed"})
    with pytest.raises(FinalizedRunError):
        FormalRunArchive.create(
            archive.run_id,
            date(2026, 1, 5),
            git_state={},
            environment={},
            root=archive.root,
            expected_symbols=("ALI",),
        )

    (archive.path / "late-unmanifested-file.txt").write_text(
        "tampering is detectable",
        encoding="utf-8",
    )
    assert not archive.verify_integrity()


def test_incomplete_run_cannot_finalize(tmp_path: Path) -> None:
    archive = FormalRunArchive.create(
        "formal-incomplete",
        date(2026, 1, 5),
        git_state={},
        environment={},
        root=tmp_path,
        expected_symbols=("ALI",),
    )

    with pytest.raises(FormalArchiveError, match="incomplete"):
        archive.finalize()
    assert archive.state is FormalRunState.IN_PROGRESS


def test_run_state_lifecycle_failed_is_terminal(tmp_path: Path) -> None:
    archive = FormalRunArchive.create(
        "formal-failure",
        date(2026, 1, 5),
        git_state={},
        environment={},
        root=tmp_path,
        expected_symbols=("ALI",),
    )
    assert archive.state is FormalRunState.IN_PROGRESS

    archive.mark_failed(["synthetic failure"])

    assert archive.state is FormalRunState.FAILED
    with pytest.raises(FormalArchiveError, match="terminal"):
        archive.write_json("late.json", {})
    with pytest.raises(FormalArchiveError, match="terminal"):
        archive.finalize()


def test_unresolved_lasso_upper_boundary_cannot_finalize() -> None:
    base = minimal_evidence()
    evidence = FormalCompanyEvidence(
        symbol=base.symbol,
        development_target_dates=base.development_target_dates,
        holdout_target_dates=base.holdout_target_dates,
        cv_fold_target_date_manifests=base.cv_fold_target_date_manifests,
        model_grids_and_seeds=base.model_grids_and_seeds,
        tuning_and_fold_scores=base.tuning_and_fold_scores,
        selected_configurations=base.selected_configurations,
        lasso_boundary_metadata={
            "classification": "upper",
            "lower": False,
            "upper": True,
            "interior": False,
            "resolution": None,
        },
        arima_diagnostics=base.arima_diagnostics,
        lstm_seed_epoch_metadata=base.lstm_seed_epoch_metadata,
        canonical_holdout_records=base.canonical_holdout_records,
        metrics=base.metrics,
        statistical_tests=base.statistical_tests,
    )

    with pytest.raises(FormalSchemaError, match="upper-bound"):
        evidence.validate()


@pytest.mark.parametrize(
    "arguments",
    ((), ("--run-id", "formal-001"), ("--cutoff-date", "2026-01-05")),
)
def test_cli_requires_explicit_run_id_and_cutoff(arguments) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(arguments)


def test_dirty_git_state_metadata_is_captured(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        if "rev-parse" in command:
            output = "b" * 40 + "\n"
        elif "branch" in command:
            output = "main\n"
        else:
            output = " M backend/example.py\n?? notes.txt\n"
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr("src.formal.provenance.subprocess.run", fake_run)

    state = capture_git_state(tmp_path)

    assert state.commit == "b" * 40
    assert state.branch == "main"
    assert state.dirty is True
    assert state.changed_paths == ("backend/example.py", "notes.txt")


def test_missing_provenance_is_explicitly_reported(monkeypatch, tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    write_raw_csv(raw_dir / "ALI.csv")
    provenance = tmp_path / "provenance.json"
    provenance.write_text('{"schema_version": 1, "sources": {}}', encoding="utf-8")
    actions = tmp_path / "actions.json"
    actions.write_text('{"schema_version": 1, "actions": []}', encoding="utf-8")
    lir_evidence = tmp_path / "artifacts" / "evaluations" / "lir"
    lir_evidence.mkdir(parents=True)
    lir_evidence.joinpath("ALI.json").write_text(
        json.dumps(
            {
                "tuning": {
                    "alpha_grid_position": {
                        "upper": True,
                        "classification": "upper",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.formal.validation.capture_git_state", lambda _: clean_git_state())
    monkeypatch.setattr("src.formal.validation.capture_environment", lambda: {})

    report = assess_formal_readiness(
        "formal-provenance",
        date(2026, 1, 5),
        companies=(COMPANIES[0],),
        raw_data_dir=raw_dir,
        formal_runs_root=tmp_path / "runs",
        provenance_path=provenance,
        corporate_actions_path=actions,
        repository_root=tmp_path,
        calendar=PSETradingCalendar(frozenset()),
        artifacts_root=tmp_path / "artifacts",
        require_all_companies=False,
    )

    missing = [issue for issue in report.issues if issue.code == "missing_required_provenance"]
    assert {issue.message.rsplit(": ", 1)[-1] for issue in missing} == {
        "source_name",
        "source_reference",
        "retrieval_date",
    }
    assert report.raw_provenance[0]["source_name"] is None
    assert any(
        issue.code == "unresolved_lasso_upper_boundary" for issue in report.issues
    )
    assert not report.ready


def test_missing_duplicate_and_unexpected_sessions_are_reported() -> None:
    result = analyze_session_completeness(
        "ALI",
        (
            date(2026, 1, 2),
            date(2026, 1, 2),
            date(2026, 1, 3),
            date(2026, 1, 6),
        ),
        cutoff_date=date(2026, 1, 6),
        calendar=PSETradingCalendar(frozenset()),
    )

    assert result.missing_dates == (date(2026, 1, 5),)
    assert result.duplicate_dates == (date(2026, 1, 2),)
    assert result.unexpected_dates == (date(2026, 1, 3),)
    assert not result.complete


def test_corporate_action_schema_requires_truthful_verification() -> None:
    record = CorporateActionRecord(
        symbol="ALI",
        action_date=date(2026, 1, 5),
        action_type="stock_split",
        source=None,
        verified=False,
        notes=None,
    )
    assert record.as_dict()["verified"] is False

    with pytest.raises(FormalSchemaError, match="external source"):
        CorporateActionRecord(
            symbol="ALI",
            action_date=date(2026, 1, 5),
            action_type="stock_split",
            source=None,
            verified=True,
        )
    with pytest.raises(FormalSchemaError, match="boolean"):
        CorporateActionRecord(
            symbol="ALI",
            action_date=date(2026, 1, 5),
            action_type="stock_split",
            source="https://example.test/action",
            verified="yes",
        )


def test_check_only_performs_no_training_or_archive_write(tmp_path: Path) -> None:
    readiness = FormalReadinessReport(
        run_id="formal-check-only",
        cutoff_date=date(2026, 1, 5),
        checked_at=datetime(2026, 1, 6, tzinfo=MANILA),
        issues=(),
        raw_provenance=(),
        session_completeness=(),
        git_state={},
        environment={},
    )
    training_called = False

    def forbidden_executor(request, archive):
        nonlocal training_called
        training_called = True
        raise AssertionError("check-only invoked training")

    request = FormalRunRequest(
        run_id="formal-check-only",
        cutoff_date=date(2026, 1, 5),
        check_only=True,
        formal_runs_root=tmp_path / "runs",
    )
    outcome = run_formal_experiment(
        request,
        readiness_checker=lambda _: readiness,
        executor=forbidden_executor,
    )

    assert outcome.readiness.ready
    assert outcome.state is None
    assert not training_called
    assert not request.formal_runs_root.exists()
