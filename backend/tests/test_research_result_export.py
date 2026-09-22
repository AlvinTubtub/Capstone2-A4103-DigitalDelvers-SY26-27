"""Deterministic, fail-closed tests for frozen research-result CSV exports."""

from copy import deepcopy
import csv
from datetime import date, timedelta
import os
from pathlib import Path

import pytest

from config.companies import COMPANIES
from scripts.export_research_results import (
    CONFIGURATION_COLUMNS,
    FORMAL_AGGREGATE_SHA256,
    FORMAL_CUTOFF,
    FORMAL_GIT_SHA,
    FORMAL_RUN_ID,
    HOLDOUT_END,
    HOLDOUT_OBSERVATIONS,
    HOLDOUT_START,
    METHODS,
    METRIC_COLUMNS,
    ResearchEvidence,
    ResearchResultExportError,
    build_research_rows,
    load_authoritative_evidence,
    publish_research_rows,
)


def _holdout_dates() -> list[str]:
    start = date.fromisoformat(HOLDOUT_START)
    end = date.fromisoformat(HOLDOUT_END)
    span = (end - start).days
    values = [
        start + timedelta(days=(index * span) // (HOLDOUT_OBSERVATIONS - 1))
        for index in range(HOLDOUT_OBSERVATIONS)
    ]
    assert len(set(values)) == HOLDOUT_OBSERVATIONS
    return [value.isoformat() for value in values]


def _synthetic_evidence() -> ResearchEvidence:
    symbols = [company.symbol for company in COMPANIES]
    dates = _holdout_dates()
    metrics = {
        "lag_reg": {"rmse": 1.0, "mae": 1.0, "mase": 0.5, "r2": -0.1, "observations": 246},
        "arima": {"rmse": 2.0, "mae": 2.0, "mase": 1.0, "r2": -0.2, "observations": 246},
        "lstm": {"rmse": 3.0, "mae": 3.0, "mase": 1.5, "r2": -0.3, "observations": 246},
        "naive": {"rmse": 4.0, "mae": 4.0, "mase": 2.0, "r2": -0.4, "observations": 246},
    }
    company_evidence = {}
    audits = []
    semantics = []
    indexed_holdouts = []
    for company in COMPANIES:
        symbol = company.symbol
        records = [
            {
                "company": symbol,
                "target_date": target_date,
                "actual_close": 100.0 + index,
                "lir_prediction": 99.0 + index,
                "arima_prediction": 98.0 + index,
                "lstm_prediction": 97.0 + index,
                "naive_prediction": 96.0 + index,
            }
            for index, target_date in enumerate(dates)
        ]
        company_evidence[symbol] = {
            "symbol": symbol,
            "holdout_target_dates": dates,
            "canonical_holdout_records": records,
            "selected_configurations": {
                "lag_reg": {
                    "alpha": 0.1,
                    "development_fit": {
                        "alpha": 0.1,
                        "selected_features": ["return_lag_1", "rsi_14"],
                    },
                },
                "arima": {
                    "order": [0, 1, 0],
                    "trend": "n",
                    "drift_enabled": False,
                    "development_fit": {
                        "order": [0, 1, 0],
                        "trend": "n",
                        "drift_enabled": False,
                        "convergence_status": "confirmed_converged",
                    },
                },
                "lstm": {
                    "lookback": 5,
                    "hidden_size": 16,
                    "learning_rate": 0.001,
                    "batch_size": 32,
                },
            },
            "tuning_and_fold_scores": {
                "lag_reg": {
                    "mean_validation_rmse": {"0.1": 1.25},
                },
                "arima": {
                    "selected_specification": {
                        "order": [0, 1, 0],
                        "trend": "n",
                        "drift_enabled": False,
                    },
                    "selected_mean_validation_rmse": 1.5,
                    "candidates": [
                        {
                            "completed_all_folds": True,
                            "mean_validation_rmse": 1.5,
                        }
                    ],
                },
                "lstm": {
                    "selected_specification": {
                        "lookback": 5,
                        "hidden_size": 16,
                        "learning_rate": 0.001,
                        "batch_size": 32,
                    },
                    "selected_mean_validation_rmse": 1.75,
                    "selected_validation_rmse_standard_deviation": 0.2,
                    "candidates": [
                        {
                            "completed": True,
                            "mean_validation_rmse": 1.75,
                        }
                    ],
                },
            },
            "lasso_boundary_metadata": {
                "chosen_alpha": 0.1,
                "classification": "interior",
            },
            "lstm_seed_epoch_metadata": {
                "selected_epoch_count": 7,
                "tuning_seeds": [11, 29, 47],
                "final_seed": 42,
                "stage_b": {
                    "lookback": 5,
                    "hidden_size": 16,
                    "learning_rate": 0.001,
                    "batch_size": 32,
                    "selected_epoch_count": 7,
                    "seed": 42,
                },
            },
            "metrics": deepcopy(metrics),
        }
        audits.append(
            {
                "symbol": symbol,
                "reconstructed_denominator": 2.0,
                "methods": [
                    {
                        "model": method,
                        "stored_mae": values["mae"],
                        "stored_mase": values["mase"],
                        "tolerance": 1e-12,
                        "verified": True,
                    }
                    for method, values in metrics.items()
                ],
            }
        )
        semantics.append(
            {
                "symbol": symbol,
                "descriptive_holdout": {
                    "best_principal_model": "lag_reg",
                    "best_evaluated_method": "lag_reg",
                    "best_principal_beats_naive": True,
                    "all_principals_worse_than_naive": False,
                },
                "metrics": deepcopy(metrics),
            }
        )
        indexed_holdouts.append(
            {
                "symbol": symbol,
                "rows": [
                    {"target_date": row["target_date"], "actual_close": row["actual_close"]}
                    for row in records
                ],
            }
        )
    return ResearchEvidence(
        formal_run={
            "run_id": FORMAL_RUN_ID,
            "cutoff_date": FORMAL_CUTOFF,
            "expected_symbols": symbols,
            "git_state": {"commit": FORMAL_GIT_SHA, "dirty": False},
        },
        formal_model_config={
            "model_config": {
                "lag_regression": {"cv_splits": 5},
                "arima": {
                    "cv_splits": 5,
                    "trend_options_by_d": [[0, ["n", "c"]], [1, ["n", "t"]], [2, ["n"]]],
                },
                "lstm": {
                    "cv_splits": 5,
                    "tuning_seeds": [11, 29, 47],
                    "final_seed": 42,
                },
            }
        },
        company_evidence=company_evidence,
        supplementary_source={
            "source_formal_run_id": FORMAL_RUN_ID,
            "source_cutoff_date": FORMAL_CUTOFF,
            "source_git_commit": FORMAL_GIT_SHA,
            "source_formal_integrity_aggregate_sha256": FORMAL_AGGREGATE_SHA256,
            "source_formal_run_state": "FINALIZED",
            "source_holdout_start": HOLDOUT_START,
            "source_holdout_end": HOLDOUT_END,
            "source_target_count_per_company": HOLDOUT_OBSERVATIONS,
            "source_company_count": 15,
            "source_company_order": symbols,
        },
        mase_audit={"company_order": symbols, "companies": audits},
        reporting_semantics={"company_order": symbols, "companies": semantics},
        holdout_index={
            "company_order": symbols,
            "common_target_dates": dates,
            "companies": indexed_holdouts,
        },
    )


@pytest.fixture
def evidence() -> ResearchEvidence:
    return _synthetic_evidence()


def test_builds_exact_configuration_and_metric_contract(evidence: ResearchEvidence) -> None:
    rows = build_research_rows(evidence)

    assert len(rows.configurations) == 15
    assert len(rows.metrics) == 60
    assert [row["symbol"] for row in rows.configurations] == [
        company.symbol for company in COMPANIES
    ]
    assert {row["symbol"] for row in rows.metrics} == {
        company.symbol for company in COMPANIES
    }
    assert {row["method"] for row in rows.metrics} == set(METHODS)
    assert len({(row["symbol"], row["method"]) for row in rows.metrics}) == 60
    assert all(row["holdout_start"] == HOLDOUT_START for row in rows.metrics)
    assert all(row["holdout_end"] == HOLDOUT_END for row in rows.metrics)
    assert all(row["observation_count"] == 246 for row in rows.metrics)
    assert all(row["mase_denominator"] == 2.0 for row in rows.metrics)
    assert all(row["formal_run_id"] == FORMAL_RUN_ID for row in (*rows.configurations, *rows.metrics))
    assert all(row["formal_cutoff"] == FORMAL_CUTOFF for row in (*rows.configurations, *rows.metrics))
    assert all(row["formal_git_sha"] == FORMAL_GIT_SHA for row in (*rows.configurations, *rows.metrics))


def test_configuration_rows_preserve_all_three_formal_selections(
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)

    assert all(row["lir_selected_features"] == "return_lag_1|rsi_14" for row in rows.configurations)
    assert all(row["lir_selected_feature_count"] == 2 for row in rows.configurations)
    assert all((row["arima_p"], row["arima_d"], row["arima_q"]) == (0, 1, 0) for row in rows.configurations)
    assert all(row["arima_trend"] == "n" for row in rows.configurations)
    assert all(row["lstm_tuning_seeds"] == "11|29|47" for row in rows.configurations)
    assert all(row["lstm_final_seed"] == 42 for row in rows.configurations)


def test_negative_r2_and_descriptive_winners_are_preserved(
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)

    assert all(float(row["r2"]) < 0 for row in rows.metrics)
    assert all(row["best_principal_model"] == "lag_reg" for row in rows.metrics)
    assert all(row["best_evaluated_method"] == "lag_reg" for row in rows.metrics)
    assert all(row["best_principal_beats_naive"] == "true" for row in rows.metrics)


def test_publication_is_deterministic_and_has_exact_schemas(
    tmp_path: Path,
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)
    first = publish_research_rows(rows, output_dir=tmp_path / "research-result")
    first_bytes = tuple(path.read_bytes() for path in first)
    second = publish_research_rows(rows, output_dir=tmp_path / "research-result")

    assert tuple(path.read_bytes() for path in second) == first_bytes
    with first[0].open(newline="", encoding="utf-8") as source:
        config_reader = csv.DictReader(source)
        assert tuple(config_reader.fieldnames or ()) == CONFIGURATION_COLUMNS
        assert len(list(config_reader)) == 15
    with first[1].open(newline="", encoding="utf-8") as source:
        metric_reader = csv.DictReader(source)
        assert tuple(metric_reader.fieldnames or ()) == METRIC_COLUMNS
        assert len(list(metric_reader)) == 60


def test_missing_authoritative_source_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ResearchResultExportError, match="integrity"):
        load_authoritative_evidence(
            formal_runs_root=tmp_path / "missing-formal",
            supplementary_runs_root=tmp_path / "missing-supplementary",
        )


def test_invalid_company_count_fails_closed(evidence: ResearchEvidence) -> None:
    with pytest.raises(ResearchResultExportError, match="15 unique"):
        build_research_rows(evidence, companies=COMPANIES[:-1])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_formal_run_id", "wrong", "source_formal_run_id"),
        ("source_cutoff_date", "2026-09-10", "source_cutoff_date"),
        ("source_git_commit", "0" * 40, "source_git_commit"),
        (
            "source_formal_integrity_aggregate_sha256",
            "0" * 64,
            "source_formal_integrity_aggregate_sha256",
        ),
    ],
)
def test_conflicting_formal_provenance_fails_closed(
    evidence: ResearchEvidence,
    field: str,
    value: object,
    message: str,
) -> None:
    changed = deepcopy(evidence)
    changed.supplementary_source[field] = value

    with pytest.raises(ResearchResultExportError, match=message):
        build_research_rows(changed)


def test_conflicting_mase_denominator_fails_closed(evidence: ResearchEvidence) -> None:
    changed = deepcopy(evidence)
    changed.mase_audit["companies"][0]["reconstructed_denominator"] = 9.0

    with pytest.raises(ResearchResultExportError, match="MASE denominator conflicts"):
        build_research_rows(changed)


@pytest.mark.parametrize(
    ("field", "value"),
    [("order", [4, 1, 0]), ("trend", "c")],
)
def test_invalid_arima_specification_fails_closed(
    evidence: ResearchEvidence,
    field: str,
    value: object,
) -> None:
    changed = deepcopy(evidence)
    changed.company_evidence["ALI"]["selected_configurations"]["arima"][field] = value

    with pytest.raises(ResearchResultExportError, match="ARIMA"):
        build_research_rows(changed)


def test_production_only_parameter_cannot_replace_missing_formal_selection(
    evidence: ResearchEvidence,
) -> None:
    changed = deepcopy(evidence)
    selected = changed.company_evidence["ALI"]["selected_configurations"]
    selected.pop("lstm")
    changed.company_evidence["ALI"]["production_lstm"] = {
        "lookback": 5,
        "hidden_size": 16,
        "learning_rate": 0.001,
        "batch_size": 32,
    }

    with pytest.raises(ResearchResultExportError, match="selected LSTM"):
        build_research_rows(changed)


def test_failed_directory_swap_restores_both_previous_csvs(
    tmp_path: Path,
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)
    output = tmp_path / "research-result"
    output.mkdir()
    config_path = output / "selected_configurations.csv"
    metrics_path = output / "holdout_metrics.csv"
    config_path.write_bytes(b"old-config\n")
    metrics_path.write_bytes(b"old-metrics\n")
    calls = 0

    def fail_new_directory(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic replacement failure")
        os.replace(source, destination)

    with pytest.raises(ResearchResultExportError, match="publication failed"):
        publish_research_rows(rows, output_dir=output, replace=fail_new_directory)

    assert config_path.read_bytes() == b"old-config\n"
    assert metrics_path.read_bytes() == b"old-metrics\n"
