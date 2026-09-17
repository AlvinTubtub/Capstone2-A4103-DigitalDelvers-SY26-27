"""Static safety checks for the two authoritative GitHub Actions workflows."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPOSITORY_ROOT / ".github" / "workflows"
FORBIDDEN_LEGACY_REFERENCES = (
    "prediction_cache",
    "production_history",
    "services.model_selector",
    "services.pdf_pipeline",
    "models/deployment/current",
    "best_models.json",
    "statistical_tests.json",
    "run_pipeline.py",
    "requirements-fast.txt",
    "requirements-inference.txt",
    "requirements-pipeline.txt",
    "FORMAL_CORRECTED",
    "formal_evaluation",
    "evaluate_formal_symbol",
)


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_training_workflow_has_fresh_fail_closed_sequence() -> None:
    text = workflow("train_models.yml")

    required_in_order = (
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "python -m pytest -q",
        "clean imports: PASS",
        "python -m scripts.validate_raw --all --verbose",
        "python -m scripts.train_all --all --fresh --verbose",
        "--skip-manifest",
        "python -m scripts.validate_frontend_forecasts --verbose",
        "--create-manifest",
        "actions/upload-artifact@v4",
        "git add -- frontend/public/forecasts",
    )
    positions = [text.index(item) for item in required_in_order]

    assert positions == sorted(positions)
    assert 'cron: "0 0 28 2,5,8,11 *"' in text
    assert "group: pse-pipeline" in text
    assert "timeout-minutes: 360" in text
    assert "name: forecastph-backend-artifacts" in text
    assert "backend/artifacts/production_manifest.json" in text


def test_daily_workflow_validates_before_ingestion_and_never_trains() -> None:
    text = workflow("update_pipeline.yml")

    required_in_order = (
        "Locate latest valid Phase 14 training artifact",
        "Restore verified production artifact layout",
        "Validate restored production artifacts",
        "python -m scripts.update_eod --verbose",
        "python -m scripts.validate_raw --all --verbose",
        "python -m scripts.update_forecast_ledger --resolve-outcomes --all --verbose",
        "python -m scripts.forecast_all --all --verbose",
        "python -m scripts.update_forecast_ledger --issue-forecasts --all --verbose",
        "python -m scripts.update_forecast_ledger --report-drift --all --verbose",
        "python -m scripts.validate_frontend_forecasts --verbose",
        "git add -- backend/data/raw backend/data/forecast_ledger/events.jsonl frontend/public/forecasts",
    )
    positions = [text.index(item) for item in required_in_order]

    assert positions == sorted(positions)
    assert "train_all.py" not in text
    assert "--workflow train_models.yml" in text
    assert '--branch "$TARGET_BRANCH"' in text
    assert "--status success" in text
    assert "--expected-run-id" in text
    assert (
        "No valid Phase 14 production model artifact exists. "
        "Run PSE Fresh Model Training manually first."
    ) in text
    assert "steps.ingestion.outputs.raw_changed == 'true'" in text
    assert "repository_dispatch:" in text
    assert "types: [update-pse-data]" in text
    assert "workflow_dispatch: {}" in text
    assert "schedule:" not in text


def test_workflows_have_no_legacy_backend_references() -> None:
    combined = workflow("train_models.yml") + workflow("update_pipeline.yml")

    assert all(reference not in combined for reference in FORBIDDEN_LEGACY_REFERENCES)
    assert "python scripts/" not in combined
