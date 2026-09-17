"""Read-only frontend forecast JSON validation tests."""

from pathlib import Path
import shutil

import pytest

from src.export.frontend_exporter import FRONTEND_FORECASTS_DIR
from src.export.validation import (
    FrontendForecastValidationError,
    load_strict_json,
    operational_forecast_paths,
    validate_frontend_forecasts,
)


def test_current_complete_frontend_export_is_valid() -> None:
    files = validate_frontend_forecasts(FRONTEND_FORECASTS_DIR)

    assert len(operational_forecast_paths()) == 35
    assert len(files) == 35


def test_operational_tree_has_no_separate_study_directory() -> None:
    assert not (FRONTEND_FORECASTS_DIR / "formal").exists()


@pytest.mark.parametrize("constant", ("NaN", "Infinity", "-Infinity"))
def test_strict_json_rejects_nonstandard_numbers(
    tmp_path: Path,
    constant: str,
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(f'{{"value": {constant}}}\n', encoding="utf-8")

    with pytest.raises(FrontendForecastValidationError, match="forbidden"):
        load_strict_json(path)


def test_complete_export_validation_fails_on_missing_documents(tmp_path: Path) -> None:
    with pytest.raises(FrontendForecastValidationError, match="incomplete"):
        validate_frontend_forecasts(tmp_path)


def test_complete_export_validation_requires_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "forecasts"
    shutil.copytree(FRONTEND_FORECASTS_DIR, output_root)
    (output_root / "manifest.json").unlink(missing_ok=True)

    with pytest.raises(FrontendForecastValidationError, match="missing=.*manifest.json"):
        validate_frontend_forecasts(output_root)


def test_complete_export_validation_rejects_malformed_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "forecasts"
    shutil.copytree(FRONTEND_FORECASTS_DIR, output_root)
    (output_root / "manifest.json").write_text("{malformed\n", encoding="utf-8")

    with pytest.raises(FrontendForecastValidationError, match="Invalid JSON file"):
        validate_frontend_forecasts(output_root)
