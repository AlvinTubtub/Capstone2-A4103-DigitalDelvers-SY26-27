"""Frozen September 2026 screening and supporting-package invariants."""

import csv
import hashlib
import json
from pathlib import Path
import shutil

import pandas as pd
import pytest

from scripts import pse_corporate_action_screening_30pct as screening
from scripts.export_research_results import validate_research_result_package


PACKAGE = screening.DEFAULT_OUTPUT_DIR


def test_frozen_formal_scope_and_results() -> None:
    metadata = screening.validate_screening_package(PACKAGE)
    assert metadata["formal_run_id"] == screening.FORMAL_RUN_ID
    assert metadata["formal_cutoff"] == "2026-09-11"
    assert metadata["start_date"] == "2020-01-02"
    assert metadata["company_count"] == 15
    assert metadata["rows_per_company"] == 1635
    assert metadata["rows_screened"] == 24525
    assert metadata["duplicate_symbol_date_rows"] == 0
    assert metadata["missing_symbols"] == []
    assert (metadata["statistical_flag_count"], metadata["known_event_count"], metadata["unique_flagged_stock_dates"]) == (1, 6, 7)
    flags = pd.read_csv(PACKAGE / "material_price_discontinuity_flags.csv")
    statistical = flags[flags["Thirty_Percent_Statistical_Flag"]]
    assert list(zip(statistical.Symbol, statistical.Date)) == [("APX", "2020-10-16")]
    assert statistical.iloc[0]["Close_to_Close_Change_Pct"] == pytest.approx(34.83870967741933)
    assert statistical.iloc[0]["Opening_Gap_Pct"] == pytest.approx(49.67741935483869)
    assert not (statistical.Date >= "2026-07-01").any()


def test_threshold_positive_negative_close_and_opening_gap() -> None:
    raw = pd.DataFrame({
        "Symbol": ["APX"] * 4,
        "Date": ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"],
        "Open": [100, 100, 65, 100], "High": [100, 130, 100, 100],
        "Low": [100, 100, 65, 70], "Close": [100, 130, 100, 70],
        "Volume": [10] * 4, "Name": ["APX"] * 4, "Sector": ["Mining and Oil"] * 4,
        "Value_PHP": [pd.NA] * 4, "Source_File": ["fixture"] * 4,
        "Input_CSV_File": ["fixture"] * 4, "_Symbol_Order": [0] * 4,
    })
    original = raw.copy(deep=True)
    metrics = screening.calculate_metrics(raw)
    flags = screening.combine_flags(metrics, screening.resolve_known_events(metrics), 30.0)
    assert flags["Thirty_Percent_Statistical_Flag"].sum() == 3
    assert flags["Close_Threshold_Flag"].sum() == 2
    assert flags["Opening_Gap_Threshold_Flag"].sum() == 1
    pd.testing.assert_frame_equal(raw, original)


def test_known_events_below_threshold_and_historical_reviews() -> None:
    flags = pd.read_csv(PACKAGE / "material_price_discontinuity_flags.csv")
    manual = pd.read_csv(PACKAGE / "manual_verification_template.csv")
    assert flags["Known_Official_Event_Flag"].sum() == 6
    assert not flags.loc[flags.Known_Official_Event_Flag, "Thirty_Percent_Statistical_Flag"].any()
    assert set(manual.Manual_Verification_Status) == {"VERIFIED"}
    assert (manual.Final_Treatment.str.startswith("RETAINED UNCHANGED")).all()
    resolved = pd.read_csv(PACKAGE / "known_official_events_resolved.csv")
    bpi = resolved[resolved.Symbol == "BPI"].iloc[0]
    assert bpi.Official_Event_Date == "2024-01-01"
    assert bpi.Resolved_Trading_Date == "2024-01-02"


def test_unreviewed_new_flag_stays_pending() -> None:
    flag = pd.read_csv(PACKAGE / "material_price_discontinuity_flags.csv").iloc[[0]].copy()
    flag.loc[:, "Date"] = "2026-09-11"
    manual = screening.manual_template(flag)
    assert manual.iloc[0]["Manual_Verification_Status"] == "PENDING REVIEW"
    assert manual.iloc[0]["Final_Treatment"] == "RETAINED UNCHANGED PENDING MANUAL VERIFICATION"


def test_package_exact_membership_and_integrity(tmp_path: Path) -> None:
    copy = tmp_path / "corporate_action_screening"
    shutil.copytree(PACKAGE, copy)
    assert screening.validate_screening_package(copy)["rows_screened"] == 24525
    (copy / "surprise.csv").write_text("x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="membership"):
        screening.validate_screening_package(copy)
    (copy / "surprise.csv").unlink()
    (copy / "screening_run.log").unlink()
    with pytest.raises(ValueError, match="membership"):
        screening.validate_screening_package(copy)


def test_script_copy_sha_and_metadata_corruption(tmp_path: Path) -> None:
    copy = tmp_path / "corporate_action_screening"
    shutil.copytree(PACKAGE, copy)
    canonical = Path(screening.__file__)
    frozen = copy / canonical.name
    assert frozen.read_bytes() == canonical.read_bytes()
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == screening.validate_screening_package(copy)["script_sha256"]
    metadata_path = copy / "screening_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["formal_cutoff"] = "2026-06-30"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        screening.validate_screening_package(copy)


def test_deterministic_evidence_and_no_local_paths() -> None:
    first = screening._build_evidence(screening.FORMAL_ROOT)
    second = screening._build_evidence(screening.FORMAL_ROOT)
    assert first == second
    for name, payload in first.items():
        assert (PACKAGE / name).read_bytes() == payload
        assert b"/Users/" not in payload
        assert b"C:\\Users\\" not in payload


def test_quality_contradiction_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Change only a temporary quality file path, never finalized evidence.
    original_root = screening.BACKEND_ROOT
    quality_dir = tmp_path / "research-result"
    quality_dir.mkdir()
    for name in ("data_quality.csv", "data_quality_rules.csv"):
        shutil.copyfile(original_root / "research-result" / name, quality_dir / name)
    quality = pd.read_csv(quality_dir / "data_quality.csv", dtype=str, keep_default_na=False)
    quality.loc[quality.symbol == "APX", "material_discontinuity_count"] = "0"
    quality.to_csv(quality_dir / "data_quality.csv", index=False)
    monkeypatch.setattr(screening, "BACKEND_ROOT", tmp_path)
    metrics = pd.DataFrame({"Symbol": ["APX"], "Date": [pd.Timestamp("2020-10-16")], "Close_to_Close_Change_Pct": [34.84]})
    with pytest.raises(ValueError, match="contradiction"):
        screening.cross_check_data_quality(metrics)


def test_root_research_validator_accepts_supporting_package() -> None:
    result = validate_research_result_package(screening.BACKEND_ROOT / "research-result")
    assert result.package_content_sha256
