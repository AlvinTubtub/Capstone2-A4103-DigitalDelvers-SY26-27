"""Phase A supplementary generation remains outside the immutable formal archive."""

from datetime import date
import json

from config.model_config import ModelId
from src.evaluation.supplementary_analysis import (
    generate_phase_a_supplementary_analysis,
)
from src.formal.archive import FormalRunArchive
from src.formal.provenance import sha256_file
from src.formal.schema import FormalCompanyEvidence


def write_raw(path, *, offset: float) -> None:
    path.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        f"2026-01-02,99,101,98,{100 + offset},1000\n"
        f"2026-01-05,100,103,99,{102 + offset},1100\n"
        f"2026-01-06,102,104,101,{103 + offset},1200\n",
        encoding="utf-8",
    )


def evidence(symbol: str, *, offset: float) -> FormalCompanyEvidence:
    targets = (date(2026, 1, 5), date(2026, 1, 6))
    origins = (100.0 + offset, 102.0 + offset)
    actuals = (102.0 + offset, 103.0 + offset)
    rows = tuple(
        {
            "company": symbol,
            "target_date": target.isoformat(),
            "actual_close": actuals[index],
            "lir_prediction": origins[index] + 0.5,
            "arima_prediction": origins[index] + 0.25,
            "lstm_prediction": origins[index] + 0.75,
            "naive_prediction": origins[index],
        }
        for index, target in enumerate(targets)
    )
    metrics = {
        model.value: {
            "rmse": 1.0 + index,
            "mae": 0.8 + index,
            "mase": 0.5 + index * 0.2 + offset / 100.0,
            "r2": -0.1 - index,
            "observations": 2,
        }
        for index, model in enumerate(ModelId)
    }
    return FormalCompanyEvidence(
        symbol=symbol,
        development_target_dates=(date(2026, 1, 2),),
        holdout_target_dates=targets,
        cv_fold_target_date_manifests={"folds": ["present"]},
        model_grids_and_seeds={"models": "present"},
        tuning_and_fold_scores={"scores": "present"},
        selected_configurations={"selected": "present"},
        lasso_boundary_metadata={"lower": False, "upper": False, "interior": True},
        arima_diagnostics={"selected_fitted_model": "present"},
        lstm_seed_epoch_metadata={"seed": 42, "epoch": 1},
        canonical_holdout_records=rows,
        metrics=metrics,
        statistical_tests={"diebold_mariano": "unchanged"},
    )


def finalized_archive(tmp_path) -> FormalRunArchive:
    root = tmp_path / "formal-runs"
    archive = FormalRunArchive.create(
        "FORMAL_TEST_PHASE_A",
        date(2026, 1, 6),
        git_state={"commit": "a" * 40, "branch": "main", "dirty": False},
        environment={"python_version": "3.12", "package_versions": {}},
        root=root,
        expected_symbols=("ALI", "BPI"),
    )
    provenance = []
    for symbol, offset in (("ALI", 0.0), ("BPI", 10.0)):
        raw = tmp_path / f"{symbol}.csv"
        write_raw(raw, offset=offset)
        snapshot = archive.snapshot_raw_csv(symbol, raw)
        provenance.append({"symbol": symbol, "sha256": sha256_file(snapshot)})
        archive.write_json(
            f"companies/{symbol}/evidence.json",
            evidence(symbol, offset=offset).as_dict(),
        )
    archive.write_json("configuration/model_config.json", {"config": "present"})
    archive.write_json("provenance/readiness.json", {"status": "READY"})
    archive.write_json("provenance/raw_files.json", {"raw_files": provenance})
    archive.write_json("provenance/session_completeness.json", {"complete": True})
    archive.write_json("provenance/corporate_actions.json", {"actions": []})
    archive.write_json("statistics/across_company.json", {"friedman": "unchanged"})
    archive.finalize()
    return archive


def test_supplementary_generation_is_external_verified_and_idempotent(tmp_path) -> None:
    archive = finalized_archive(tmp_path)
    supplementary_root = tmp_path / "supplementary"
    source_mtimes = {
        path: path.stat().st_mtime_ns
        for path in archive.path.rglob("*")
        if path.is_file()
    }

    first = generate_phase_a_supplementary_analysis(
        archive.run_id,
        formal_runs_root=archive.root,
        supplementary_root=supplementary_root,
    )
    output_mtimes = {
        path: path.stat().st_mtime_ns
        for path in first.output_directory.iterdir()
        if path.is_file()
    }
    second = generate_phase_a_supplementary_analysis(
        archive.run_id,
        formal_runs_root=archive.root,
        supplementary_root=supplementary_root,
    )

    assert first.generated
    assert not second.generated
    assert first.output_directory != archive.path
    assert archive.verify_integrity()
    assert source_mtimes == {
        path: path.stat().st_mtime_ns
        for path in archive.path.rglob("*")
        if path.is_file()
    }
    assert output_mtimes == {
        path: path.stat().st_mtime_ns
        for path in second.output_directory.iterdir()
        if path.is_file()
    }
    paired = json.loads(first.paired_mase_path.read_text(encoding="utf-8"))
    changes = json.loads(first.change_diagnostics_path.read_text(encoding="utf-8"))
    assert len(paired["pairs"]) == 6
    assert len(changes["diagnostics"]) == 8
    json.dumps(paired, allow_nan=False)
    json.dumps(changes, allow_nan=False)
