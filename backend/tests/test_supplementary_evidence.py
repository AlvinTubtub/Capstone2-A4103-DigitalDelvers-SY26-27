"""Semantic and source-link regression tests for Phase D evidence."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from config.model_config import ModelId, RegressionFeatureConfig
from scripts import run_supplementary_evidence as cli
from src.artifacts.io import validated_json_text
from src.evaluation.statistical_tests import LossType, MODEL_PAIRS
from src.evaluation.supplementary_archive import EVIDENCE_PATHS
from src.evaluation.supplementary_archive import SupplementaryEvidenceArchive
from src.evaluation.supplementary_evidence import (
    ARIMA_UNAVAILABLE_REASON,
    SupplementaryEvidenceError,
    SupplementaryEvidencePlan,
    finalize_supplementary_plan,
    load_and_validate_finalized_payloads,
    validate_supplementary_payloads,
    verify_source_linkage,
)
from src.features.regression_features import regression_feature_contract
from src.formal.schema import FormalRunState


SYMBOLS = ("AAA", "BBB")
DATES = ("2026-01-05", "2026-01-06")


def _dm_family(loss: LossType) -> list[dict[str, object]]:
    return [
        {
            "model_pair": [left.value, right.value],
            "model_1": left.value,
            "model_2": right.value,
            "loss_type": loss.value,
        }
        for left, right in MODEL_PAIRS
    ]


def valid_payloads() -> dict[str, dict[str, object]]:
    contract = regression_feature_contract(RegressionFeatureConfig()).as_dict()
    names = contract["ordered_candidate_feature_names"]
    selected = names[:2]
    scaler = {name: float(index + 1) for index, name in enumerate(selected)}
    pairs = []
    for left, right in MODEL_PAIRS:
        differences = [0.1, -0.2]
        pairs.append(
            {
                "model_1": left.value,
                "model_2": right.value,
                "company_order": list(SYMBOLS),
                "observation_count": 2,
                "positive_count": 1,
                "negative_count": 1,
                "zero_count": 0,
                "paired_differences": differences,
                "wilcoxon": {"performed": False},
                "sign_test": {"sample_size": 2},
            }
        )
    metrics = {
        model.value: {"rmse": 1.0, "mae": 1.0, "mase": 0.5, "r2": -0.1, "observations": 2}
        for model in ModelId
    }
    company_reports = []
    for symbol in SYMBOLS:
        company_reports.append(
            {
                "symbol": symbol,
                "metrics": metrics,
                "archived_dm_evidence": {
                    "holm_families": {loss.value: _dm_family(loss) for loss in LossType}
                },
            }
        )
    lir_company = {
        "folds": [
            {
                "selected_feature_names": selected,
                "scaler_mean": scaler,
                "scaler_scale": scaler,
            }
        ],
        "development_fit": {
            "selected_feature_names": selected,
            "scaler_mean": scaler,
            "scaler_scale": scaler,
        },
    }
    deployment = {
        "operational_model_families": ["lag_reg", "arima", "lstm"],
        "single_approved_deployment_model": None,
        "automatic_promotion": False,
    }
    return {
        "source/formal_source.json": {
            "source_formal_run_id": "formal-test",
            "source_formal_integrity_aggregate_sha256": "a" * 64,
            "source_company_order": list(SYMBOLS),
            "source_company_count": 2,
            "source_target_count_per_company": 2,
        },
        "source/code_provenance.json": {"git_state": {"dirty": False}},
        "source/prospective_source.json": {"evidence_source": "forecast_ledger_only", "ledger_sha256": "b" * 64},
        "historical/formal_holdout_index.json": {
            "company_order": list(SYMBOLS),
            "common_target_dates": list(DATES),
            "companies": [
                {"symbol": symbol, "rows": [{"target_date": day, "actual_close": 100.0 + index} for index, day in enumerate(DATES)]}
                for symbol in SYMBOLS
            ],
        },
        "historical/paired_mase_evidence.json": {"friedman": {"reject": False}, "pairs": pairs},
        "historical/change_diagnostics.json": {
            "company_order": list(SYMBOLS),
            "diagnostics": [{"symbol": symbol, "model": model.value} for symbol in SYMBOLS for model in ModelId],
        },
        "historical/reporting_semantics.json": {
            "company_order": list(SYMBOLS),
            "companies": company_reports,
            "production_deployment": deployment,
        },
        "historical/mase_denominator_audit.json": {
            "company_order": list(SYMBOLS),
            "companies": [
                {
                    "symbol": symbol,
                    "reconstructed_denominator": 2.0,
                    "methods": [
                        {
                            "model": model.value,
                            "stored_mae": 1.0,
                            "stored_mase": 0.5,
                            "reconstructed_mase": 0.5,
                            "absolute_difference": 0.0,
                            "verified": True,
                        }
                        for model in ModelId
                    ],
                }
                for symbol in SYMBOLS
            ],
        },
        "methodology/lir_feature_contract.json": {
            "company_order": list(SYMBOLS),
            "frozen_feature_configuration": {
                "return_lags": list(range(1, 21)),
                "rolling_return_windows": [5, 10, 20],
                "volume_windows": [5, 20],
                "rsi_period": 14,
                "ema_fast_period": 12,
                "ema_slow_period": 26,
                "macd_signal_period": 9,
                "bollinger_window": 20,
                "bollinger_standard_deviations": 2.0,
                "raw_price_lags": [],
            },
            "candidate_feature_contract": contract,
            "companies": [{"symbol": symbol, **lir_company} for symbol in SYMBOLS],
        },
        "methodology/arima_diagnostic_status.json": {
            "company_order": list(SYMBOLS),
            "companies": [
                {
                    "symbol": symbol,
                    "enhanced_standardized_residual_diagnostics_available": False,
                    "unavailable_reason": ARIMA_UNAVAILABLE_REASON,
                    "refit_performed": False,
                }
                for symbol in SYMBOLS
            ],
        },
        "prospective/prospective_validation_snapshot.json": {
            "company_order": list(SYMBOLS),
            "companies": [{"symbol": symbol} for symbol in SYMBOLS],
        },
    }


def test_complete_semantics_and_arima_limitation_pass() -> None:
    validate_supplementary_payloads(valid_payloads())


def test_sorted_json_round_trip_preserves_lir_feature_contract_semantics() -> None:
    payloads = valid_payloads()
    original_names = list(
        payloads["methodology/lir_feature_contract.json"]
        ["candidate_feature_contract"]["ordered_candidate_feature_names"]
    )

    reloaded = json.loads(validated_json_text(payloads))

    membership = reloaded["methodology/lir_feature_contract.json"][
        "candidate_feature_contract"
    ]["group_membership"]
    assert list(membership) == sorted(membership)
    assert reloaded["methodology/lir_feature_contract.json"][
        "candidate_feature_contract"
    ]["ordered_candidate_feature_names"] == original_names
    validate_supplementary_payloads(reloaded)


@pytest.mark.parametrize(
    "corruption",
    ("wrong_membership", "missing_membership", "extra_membership", "duplicate_group"),
)
def test_lir_membership_and_group_union_corruption_is_rejected(
    corruption: str,
) -> None:
    payloads = valid_payloads()
    contract = payloads["methodology/lir_feature_contract.json"][
        "candidate_feature_contract"
    ]
    membership = contract["group_membership"]
    first_feature = contract["ordered_candidate_feature_names"][0]
    if corruption == "wrong_membership":
        membership[first_feature] = "raw_volume_level_features"
    elif corruption == "missing_membership":
        membership.pop(first_feature)
    elif corruption == "extra_membership":
        membership["not_a_candidate"] = "return_features"
    else:
        contract["groups"]["raw_volume_level_features"].append(first_feature)

    with pytest.raises(SupplementaryEvidenceError, match="feature contract|taxonomy"):
        validate_supplementary_payloads(payloads)


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        ("company_removed", lambda p: p["historical/formal_holdout_index.json"]["companies"].pop()),
        ("contract_changed", lambda p: p["methodology/lir_feature_contract.json"]["candidate_feature_contract"]["ordered_candidate_feature_names"].pop()),
        ("target_shifted", lambda p: p["historical/formal_holdout_index.json"]["common_target_dates"].__setitem__(0, "2026-01-04")),
        ("target_reordered", lambda p: p["historical/formal_holdout_index.json"]["common_target_dates"].reverse()),
        ("duplicate_company_date", lambda p: p["historical/formal_holdout_index.json"]["companies"][0]["rows"].__setitem__(1, deepcopy(p["historical/formal_holdout_index.json"]["companies"][0]["rows"][0]))),
        ("denominator_changed", lambda p: p["historical/mase_denominator_audit.json"]["companies"][0].__setitem__("reconstructed_denominator", 3.0)),
        ("mase_inconsistent", lambda p: p["historical/mase_denominator_audit.json"]["companies"][0]["methods"][0].__setitem__("stored_mase", 0.6)),
    ],
)
def test_semantic_tampering_is_rejected(name: str, mutate) -> None:
    payloads = valid_payloads()
    mutate(payloads)
    with pytest.raises(SupplementaryEvidenceError):
        validate_supplementary_payloads(payloads)


def test_actual_close_mismatch_with_formal_source_is_rejected(tmp_path: Path) -> None:
    payloads = valid_payloads()
    for company in payloads["historical/formal_holdout_index.json"]["companies"]:
        path = tmp_path / "companies" / company["symbol"]
        path.mkdir(parents=True)
        records = [dict(row, company=company["symbol"]) for row in company["rows"]]
        (path / "evidence.json").write_text(json.dumps({"canonical_holdout_records": records}))
    fake = SimpleNamespace(
        run_id="formal-test",
        path=tmp_path,
        state=FormalRunState.FINALIZED,
        verify_integrity=lambda: True,
    )
    (tmp_path / "integrity_manifest.json").write_text(json.dumps({"aggregate_sha256": "a" * 64}))
    validate_supplementary_payloads(payloads, source_archive=fake)
    payloads["historical/formal_holdout_index.json"]["companies"][0]["rows"][0]["actual_close"] = 999.0
    with pytest.raises(SupplementaryEvidenceError, match="actual Close"):
        validate_supplementary_payloads(payloads, source_archive=fake)


def test_check_only_constructs_plan_without_writing(monkeypatch, tmp_path: Path, capsys) -> None:
    plan = SupplementaryEvidencePlan("formal-test", "a" * 64, "b" * 64, valid_payloads())
    monkeypatch.setattr(cli, "build_supplementary_evidence_plan", lambda *args, **kwargs: plan)
    destination = tmp_path / "packages"
    result = cli.main(
        [
            "--formal-run-id", "formal-test", "--package-id", PACKAGE_ID,
            "--check-only", "--supplementary-runs-root", str(destination),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["writes_performed"] is False
    assert not destination.exists()


def test_finalization_rejects_dirty_code_and_semantically_invalid_plan(tmp_path: Path) -> None:
    dirty = valid_payloads()
    dirty["source/code_provenance.json"]["git_state"]["dirty"] = True
    with pytest.raises(SupplementaryEvidenceError, match="clean"):
        finalize_supplementary_plan(
            PACKAGE_ID,
            SupplementaryEvidencePlan("formal-test", "a" * 64, "b" * 64, dirty),
            root=tmp_path,
        )
    invalid = valid_payloads()
    invalid["historical/formal_holdout_index.json"]["companies"].pop()
    with pytest.raises(SupplementaryEvidenceError):
        finalize_supplementary_plan(
            PACKAGE_ID,
            SupplementaryEvidencePlan("formal-test", "a" * 64, "b" * 64, invalid),
            root=tmp_path,
        )
    assert not any(tmp_path.iterdir())


def test_valid_clean_plan_finalizes_and_verifies(tmp_path: Path) -> None:
    payloads = valid_payloads()
    package = finalize_supplementary_plan(
        PACKAGE_ID,
        SupplementaryEvidencePlan("formal-test", "a" * 64, "b" * 64, payloads),
        root=tmp_path,
    )

    assert package.verify_integrity().valid
    assert package.path.is_dir()


def test_finalized_sorted_json_package_loads_and_validates_semantically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payloads = valid_payloads()
    formal_root = tmp_path / "formal"
    formal_path = formal_root / "formal-test"
    (formal_path / "companies").mkdir(parents=True)
    (formal_path / "integrity_manifest.json").write_text(
        json.dumps({"aggregate_sha256": "a" * 64}),
        encoding="utf-8",
    )
    for company in payloads["historical/formal_holdout_index.json"]["companies"]:
        company_path = formal_path / "companies" / company["symbol"]
        company_path.mkdir()
        records = [
            dict(row, company=company["symbol"])
            for row in company["rows"]
        ]
        (company_path / "evidence.json").write_text(
            json.dumps({"canonical_holdout_records": records}),
            encoding="utf-8",
        )

    class FakeFormal:
        state = FormalRunState.FINALIZED

        def __init__(self, run_id, *, root):
            self.run_id = run_id
            self.path = Path(root) / run_id

        def verify_integrity(self):
            return True

    import src.evaluation.supplementary_evidence as module

    monkeypatch.setattr(module, "FormalRunArchive", FakeFormal)
    package = finalize_supplementary_plan(
        PACKAGE_ID,
        SupplementaryEvidencePlan(
            "formal-test",
            "a" * 64,
            "b" * 64,
            payloads,
        ),
        root=tmp_path / "packages",
    )

    loaded = load_and_validate_finalized_payloads(
        package,
        formal_runs_root=formal_root,
    )
    contract = loaded["methodology/lir_feature_contract.json"][
        "candidate_feature_contract"
    ]
    assert list(contract["group_membership"]) == sorted(
        contract["group_membership"]
    )
    assert contract["ordered_candidate_feature_names"] == payloads[
        "methodology/lir_feature_contract.json"
    ]["candidate_feature_contract"]["ordered_candidate_feature_names"]


def test_source_linkage_separately_detects_formal_and_ledger_changes(
    monkeypatch, tmp_path: Path
) -> None:
    payloads = valid_payloads()
    formal_root = tmp_path / "formal"
    formal_path = formal_root / "formal-test"
    formal_path.mkdir(parents=True)
    manifest_path = formal_path / "integrity_manifest.json"
    manifest_path.write_text(json.dumps({"aggregate_sha256": "a" * 64}), encoding="utf-8")
    from src.formal.provenance import sha256_file

    payloads["source/formal_source.json"].update(
        {
            "source_formal_integrity_manifest_sha256": sha256_file(manifest_path),
        }
    )
    ledger = tmp_path / "events.jsonl"
    ledger.write_text("ledger bytes\n", encoding="utf-8")
    payloads["source/prospective_source.json"]["ledger_sha256"] = sha256_file(ledger)
    package = SupplementaryEvidenceArchive.create(
        PACKAGE_ID, source_formal_run_id="formal-test", root=tmp_path / "packages"
    )
    for path in EVIDENCE_PATHS:
        package.write_json(path, payloads[path])
    package.finalize(source_formal_integrity_aggregate_sha256="a" * 64)

    class FakeFormal:
        state = FormalRunState.FINALIZED
        path = formal_path

        def __init__(self, run_id, *, root):
            self.run_id = run_id

        def verify_integrity(self):
            return True

    import src.evaluation.supplementary_evidence as module

    monkeypatch.setattr(module, "FormalRunArchive", FakeFormal)
    assert verify_source_linkage(package, formal_runs_root=formal_root, ledger_path=ledger).valid

    ledger.write_text("changed\n", encoding="utf-8")
    assert not verify_source_linkage(package, formal_runs_root=formal_root, ledger_path=ledger).valid
    ledger.write_text("ledger bytes\n", encoding="utf-8")
    json.loads(manifest_path.read_text())["aggregate_sha256"]
    manifest_path.write_text(json.dumps({"aggregate_sha256": "c" * 64}), encoding="utf-8")
    assert not verify_source_linkage(package, formal_runs_root=formal_root, ledger_path=ledger).valid

    monkeypatch.setattr(FakeFormal, "verify_integrity", lambda self: False)
    assert not verify_source_linkage(package, formal_runs_root=formal_root, ledger_path=ledger).valid


PACKAGE_ID = "FORECASTPH_SUPPLEMENTARY_TEST_02"
