"""Deterministic, fail-closed tests for frozen research-result CSV exports."""

from copy import deepcopy
import csv
from datetime import date, timedelta
from functools import cache
import hashlib
import math
import os
from pathlib import Path

import pytest

from config.companies import COMPANIES
from scripts import export_research_results as exporter
from scripts.export_research_results import (
    ACROSS_COMPANY_COLUMNS,
    BENCHMARK_DM_COLUMNS,
    CONFIGURATION_COLUMNS,
    DATA_QUALITY_COLUMNS,
    DATA_QUALITY_RULE_COLUMNS,
    DATA_PROVENANCE_COLUMNS,
    MODEL_DIAGNOSTIC_COLUMNS,
    DIAGNOSTIC_TYPES,
    FORMAL_AGGREGATE_SHA256,
    FORMAL_CUTOFF,
    FORMAL_GIT_SHA,
    FORMAL_RUN_ID,
    FORMAL_START,
    FORMAL_SCOPE_COLUMNS,
    FrozenFormalScope,
    HOLDOUT_PREDICTION_COLUMNS,
    HOLDOUT_END,
    HOLDOUT_OBSERVATIONS,
    HOLDOUT_START,
    LOSS_TYPES,
    MANIFEST_COLUMNS,
    METHOD_PAIRS,
    METHODS,
    METRIC_COLUMNS,
    PRINCIPAL_METHODS,
    PRINCIPAL_WIN_SUMMARY_COLUMNS,
    PRINCIPAL_WINNER_COLUMNS,
    ResearchEvidence,
    ResearchResultExportError,
    SECTOR_PEER_COLUMNS,
    SUBSTANTIVE_FILE_ORDER,
    SUBSTANTIVE_FILE_ROW_COUNTS,
    SUBSTANTIVE_FILE_SCHEMAS,
    SUPPLEMENTARY_PACKAGE_ID,
    WITHIN_COMPANY_DM_COLUMNS,
    build_data_quality_rule_rows,
    build_frozen_data_quality_rows,
    build_frozen_formal_rows,
    build_data_provenance_rows,
    build_model_diagnostic_rows,
    build_principal_win_summary_rows,
    build_research_rows,
    export_results_manifest,
    load_authoritative_evidence,
    load_frozen_formal_scope,
    load_frozen_diagnostic_evidence,
    publish_research_closure,
    publish_research_rows,
    validate_research_result_package,
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


def _synthetic_quality_rows() -> tuple[dict[str, object], ...]:
    rows = []
    for company in COMPANIES:
        row: dict[str, object] = {column: "" for column in DATA_QUALITY_COLUMNS}
        row.update(
            {
                "symbol": company.symbol,
                "company_name": company.name,
                "sector": company.sector,
                "rule_version": "data-quality-v1",
            }
        )
        rows.append(row)
    return tuple(rows)


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
        dm_families = {}
        for loss_index, loss_type in enumerate(LOSS_TYPES, start=1):
            family = []
            for pair_index, (model_1, model_2) in enumerate(METHOD_PAIRS, start=1):
                unavailable = (model_1, model_2) == ("arima", "naive")
                family.append(
                    {
                        "available": not unavailable,
                        "dm_statistic": None if unavailable else -float(pair_index),
                        "forecast_horizon": 1,
                        "hac_lag": 4,
                        "hln_correction_factor": 0.997,
                        "holm_adjusted_p_value": 1.0 if unavailable else 0.02,
                        "long_run_variance": 0.0 if unavailable else 0.5,
                        "loss_type": loss_type,
                        "mean_loss_differential": -0.01 * pair_index * loss_index,
                        "model_1": model_1,
                        "model_2": model_2,
                        "model_pair": [model_1, model_2],
                        "raw_p_value": 1.0 if unavailable else 0.01,
                        "reject": False if unavailable else True,
                        "sample_size": 246,
                        "unavailable_reason": (
                            "zero or degenerate HAC long-run variance"
                            if unavailable
                            else None
                        ),
                    }
                )
            dm_families[loss_type] = family
        dm_evidence = {
            "alpha": 0.05,
            "company": symbol,
            "hac_lag_policy": "stored policy",
            "hln_small_sample_correction": True,
            "holm_families": dm_families,
            "p_value_sidedness": "two_sided",
            "scope": "complete_aligned_evaluation",
        }
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
            "statistical_tests": {"diebold_mariano": dm_evidence},
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
                    "symbol": symbol,
                    "best_principal_model": "lag_reg",
                    "best_principal_rmse": 1.0,
                    "best_evaluated_method": "lag_reg",
                    "best_evaluated_rmse": 1.0,
                    "best_principal_beats_naive": True,
                    "all_principals_worse_than_naive": False,
                    "naive_rmse": 4.0,
                    "selection_metric": "rmse",
                    "tie_policy": (
                        "Exact RMSE ties are ordered deterministically as lag_reg, "
                        "arima, lstm, naive."
                    ),
                },
                "metrics": deepcopy(metrics),
                "archived_dm_evidence": deepcopy(dm_evidence),
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
    paired_mase = []
    for pair_index, (model_1, model_2) in enumerate(METHOD_PAIRS, start=1):
        paired_mase.append(
            {
                "company_order": symbols,
                "difference_direction": "model_1_mase_minus_model_2_mase",
                "mean_difference": -0.01 * pair_index,
                "median_difference": -0.005 * pair_index,
                "model_1": model_1,
                "model_2": model_2,
                "negative_count": 10,
                "observation_count": 15,
                "positive_count": 5,
                "skewness": 0.1,
                "standard_deviation": 0.2,
                "wilcoxon": {
                    "performed": False,
                    "statistic": None,
                    "raw_p_value": None,
                    "holm_adjusted_p_value": None,
                    "reject": None,
                    "reason": "friedman_not_significant",
                },
                "zero_count": 0,
                "sign_test": {"raw_p_value": 0.3},
            }
        )
    friedman = {
        "statistic": 1.5,
        "raw_p_value": 0.6,
        "reject": False,
    }
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
        formal_across_company={
            "alpha": 0.05,
            "company_count": 15,
            "friedman": friedman,
            "metric": "mase",
            "models": list(METHODS),
            "pairwise_wilcoxon": [],
            "posthoc_correction": None,
            "posthoc_performed": False,
        },
        supplementary_run={
            "package_id": SUPPLEMENTARY_PACKAGE_ID,
            "source_formal_run_id": FORMAL_RUN_ID,
        },
        paired_mase_evidence={
            "alpha": 0.05,
            "company_count": 15,
            "friedman": deepcopy(friedman),
            "metric": "mase",
            "pairs": paired_mase,
            "source_formal_integrity_aggregate_sha256": FORMAL_AGGREGATE_SHA256,
            "source_formal_run_id": FORMAL_RUN_ID,
            "wilcoxon_gate": "performed_only_when_friedman_rejects",
            "wilcoxon_holm_family_size": 6,
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
    predictions, scopes = _frozen_formal_rows()
    first = publish_research_rows(
        rows,
        data_quality_rows=_synthetic_quality_rows(),
        holdout_prediction_rows=predictions,
        formal_scope_rows=scopes,
        output_dir=tmp_path / "research-result",
    )
    first_bytes = tuple(path.read_bytes() for path in first)
    second = publish_research_rows(
        rows,
        data_quality_rows=_synthetic_quality_rows(),
        holdout_prediction_rows=predictions,
        formal_scope_rows=scopes,
        output_dir=tmp_path / "research-result",
    )

    assert tuple(path.read_bytes() for path in second) == first_bytes
    with first[0].open(newline="", encoding="utf-8") as source:
        config_reader = csv.DictReader(source)
        assert tuple(config_reader.fieldnames or ()) == CONFIGURATION_COLUMNS
        assert len(list(config_reader)) == 15
    with first[1].open(newline="", encoding="utf-8") as source:
        metric_reader = csv.DictReader(source)
        assert tuple(metric_reader.fieldnames or ()) == METRIC_COLUMNS
        assert len(list(metric_reader)) == 60
    expected_schemas = (
        (BENCHMARK_DM_COLUMNS, 90),
        (WITHIN_COMPANY_DM_COLUMNS, 180),
        (ACROSS_COMPANY_COLUMNS, 7),
        (PRINCIPAL_WINNER_COLUMNS, 15),
        (SECTOR_PEER_COLUMNS, 15),
        (DATA_QUALITY_COLUMNS, 15),
    )
    for path, (columns, count) in zip(first[2:], expected_schemas):
        with path.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            assert tuple(reader.fieldnames or ()) == columns
            assert len(list(reader)) == count
    assert all(path.parent == tmp_path / "research-result" for path in first)


def test_dm_exports_have_complete_pairs_losses_and_alignment(
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)

    assert len(rows.benchmark_dm) == 90
    assert len(rows.within_company_dm) == 180
    assert {row["symbol"] for row in rows.within_company_dm} == {
        company.symbol for company in COMPANIES
    }
    for symbol in {company.symbol for company in COMPANIES}:
        company_rows = [row for row in rows.within_company_dm if row["symbol"] == symbol]
        assert len(company_rows) == 12
        for loss_type in LOSS_TYPES:
            loss_rows = [row for row in company_rows if row["loss_type"] == loss_type]
            assert {(row["model_1"], row["model_2"]) for row in loss_rows} == set(
                METHOD_PAIRS
            )
            assert all(row["holm_family_size"] == 6 for row in loss_rows)
            assert all(row["sample_size"] == HOLDOUT_OBSERVATIONS for row in loss_rows)
        for loss_type in LOSS_TYPES:
            benchmark_rows = [
                row
                for row in rows.benchmark_dm
                if row["symbol"] == symbol and row["loss_type"] == loss_type
            ]
            assert {(row["model"], row["benchmark"]) for row in benchmark_rows} == {
                (method, "naive") for method in PRINCIPAL_METHODS
            }


def test_unavailable_dm_does_not_synthesize_test_statistics_or_p_values(
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)
    unavailable = [row for row in rows.within_company_dm if row["available"] == "false"]

    assert len(unavailable) == 30
    assert all(row["dm_statistic"] == "" for row in unavailable)
    assert all(row["raw_p_value"] == "" for row in unavailable)
    assert all(row["holm_adjusted_p_value"] == "" for row in unavailable)
    assert all(row["unavailable_reason"] for row in unavailable)


def test_across_company_export_preserves_friedman_gate_without_posthoc_invention(
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)
    friedman = [row for row in rows.across_company if row["test_name"] == "friedman"]
    wilcoxon = [row for row in rows.across_company if row["test_name"] == "wilcoxon"]

    assert len(friedman) == 1
    assert friedman[0]["metric"] == "mase"
    assert friedman[0]["company_count"] == 15
    assert friedman[0]["performed"] == "true"
    assert friedman[0]["reject"] == "false"
    assert len(wilcoxon) == 6
    assert all(row["performed"] == "false" for row in wilcoxon)
    assert all(row["statistic"] == "" for row in wilcoxon)
    assert all(row["raw_p_value"] == "" for row in wilcoxon)
    assert all(row["holm_adjusted_p_value"] == "" for row in wilcoxon)
    assert all(row["median_difference"] != "" for row in wilcoxon)


def test_principal_winners_and_sector_peer_contract(evidence: ResearchEvidence) -> None:
    rows = build_research_rows(evidence)

    assert len(rows.principal_winners) == 15
    assert all(row["best_principal_model"] in PRINCIPAL_METHODS for row in rows.principal_winners)
    assert all(row["best_evaluated_method"] in METHODS for row in rows.principal_winners)
    assert all(row["winner_selection_metric"] == "rmse" for row in rows.principal_winners)
    assert len(rows.sector_peers) == 15
    sectors = {row["sector"] for row in rows.sector_peers}
    assert len(sectors) == 5
    assert {sum(row["sector"] == sector for row in rows.sector_peers) for sector in sectors} == {3}
    status_columns = [
        column for column in SECTOR_PEER_COLUMNS if column.endswith("_status")
    ]
    valid_statuses = {
        "significantly_better",
        "significantly_worse",
        "not_significant",
        "unavailable",
    }
    assert all(
        row[column] in valid_statuses
        for row in rows.sector_peers
        for column in status_columns
    )
    assert not any("sector_winner" in row for row in rows.sector_peers)


def test_best_evaluated_method_can_be_naive_and_ties_are_deterministic(
    evidence: ResearchEvidence,
) -> None:
    changed = deepcopy(evidence)
    formal_metrics = changed.company_evidence["ALI"]["metrics"]
    supplementary = changed.reporting_semantics["companies"][0]
    formal_metrics["arima"]["rmse"] = 1.0
    formal_metrics["naive"]["rmse"] = 0.5
    supplementary["metrics"] = deepcopy(formal_metrics)
    descriptive = supplementary["descriptive_holdout"]
    descriptive.update(
        {
            "best_principal_model": "lag_reg",
            "best_principal_rmse": 1.0,
            "best_evaluated_method": "naive",
            "best_evaluated_rmse": 0.5,
            "best_principal_beats_naive": False,
            "all_principals_worse_than_naive": True,
            "naive_rmse": 0.5,
        }
    )

    row = build_research_rows(changed).principal_winners[0]
    assert row["best_principal_model"] == "lag_reg"
    assert row["lag_reg_rank"] == 1
    assert row["arima_rank"] == 2
    assert row["best_evaluated_method"] == "naive"


def test_conflicting_dm_and_across_company_sources_fail_closed(
    evidence: ResearchEvidence,
) -> None:
    changed_dm = deepcopy(evidence)
    changed_dm.reporting_semantics["companies"][0]["archived_dm_evidence"][
        "holm_families"
    ]["squared_error"][0]["raw_p_value"] = 0.9
    with pytest.raises(ResearchResultExportError, match="DM evidence conflict"):
        build_research_rows(changed_dm)

    changed_across = deepcopy(evidence)
    changed_across.paired_mase_evidence["friedman"]["raw_p_value"] = 0.9
    with pytest.raises(ResearchResultExportError, match="across-company evidence conflict"):
        build_research_rows(changed_across)


def test_phase_one_csv_bytes_remain_frozen(tmp_path: Path, evidence: ResearchEvidence) -> None:
    predictions, scopes = _frozen_formal_rows()
    paths = publish_research_rows(
        build_research_rows(evidence),
        data_quality_rows=_synthetic_quality_rows(),
        holdout_prediction_rows=predictions,
        formal_scope_rows=scopes,
        output_dir=tmp_path / "research-result",
    )
    synthetic_first = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in paths[:2])
    second = publish_research_rows(
        build_research_rows(evidence),
        data_quality_rows=_synthetic_quality_rows(),
        holdout_prediction_rows=predictions,
        formal_scope_rows=scopes,
        output_dir=tmp_path / "research-result",
    )
    assert tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in second[:2]) == synthetic_first


def test_authoritative_phase_one_outputs_remain_byte_identical(tmp_path: Path) -> None:
    predictions, scopes = _frozen_formal_rows()
    paths = publish_research_rows(
        build_research_rows(load_authoritative_evidence()),
        data_quality_rows=build_frozen_data_quality_rows(),
        holdout_prediction_rows=predictions,
        formal_scope_rows=scopes,
        output_dir=tmp_path / "research-result",
    )

    expected = (
        "7c648357adaba1e5769d560435bad61a933d67ebb5ee8fc1ded5944416737a97",
        "836974efff91c52c0cdd1d492279b8fe11476fadff6dc575b6a22870eec3548a",
        "a4d0bdef371bad9fe1d0f424da65a702e44b289e4798fa5e69ec94d2710900a3",
        "e9c27f42de578bded049d9d33f7890acceb7cf7d1a9dc169a49f81bf4a639f96",
        "131f69a47061aa75cd2ff467132d193d3aa02d9eaaa8501506d020e827a416b6",
        "6bbb839974d84dd39780565f614f3fdcb4b2c311aeeee3f9897f68bd2b689aef",
        "283cec1287dea54e9a4be8eaec043ee172b97219674e11f38bcc32890148002f",
    )
    assert tuple(
        hashlib.sha256(path.read_bytes()).hexdigest() for path in paths[:7]
    ) == expected


def test_authoritative_data_quality_rows_match_frozen_formal_contract() -> None:
    first = build_frozen_data_quality_rows()
    second = build_frozen_data_quality_rows()

    assert first == second
    assert len(first) == 15
    assert [row["symbol"] for row in first] == [company.symbol for company in COMPANIES]
    assert len({row["symbol"] for row in first}) == 15
    assert {row["start_date"] for row in first} == {"2020-01-02"}
    assert {row["end_date"] for row in first} == {FORMAL_CUTOFF}
    assert {row["row_count"] for row in first} == {1_635}
    assert sum(int(row["row_count"]) for row in first) == 24_525
    assert {row["expected_session_count"] for row in first} == {1_635}
    assert all(row["rule_version"] == "data-quality-v1" for row in first)


def test_data_quality_formal_identity_mismatches_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(exporter, "FORMAL_CUTOFF", "2026-09-10")
    with pytest.raises(ResearchResultExportError, match="identity conflicts"):
        exporter.build_frozen_data_quality_rows()


def test_data_quality_frozen_raw_hash_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(exporter, "sha256_file", lambda path: "0" * 64)
    with pytest.raises(ResearchResultExportError, match="provenance conflicts"):
        exporter.build_frozen_data_quality_rows()


def test_data_quality_company_and_row_count_mismatches_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ResearchResultExportError, match="15 configured"):
        exporter.build_frozen_data_quality_rows(companies=COMPANIES[:-1])

    monkeypatch.setattr(exporter, "FORMAL_ROWS_PER_COMPANY", 1_634)
    with pytest.raises(ResearchResultExportError, match="session count"):
        exporter.build_frozen_data_quality_rows()


def test_data_quality_formal_provenance_row_count_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_load = exporter._load_json

    def changed_load(path: Path):
        payload = deepcopy(original_load(path))
        if path.name == "raw_files.json":
            payload["raw_files"][0]["row_count"] = 1_634
        return payload

    monkeypatch.setattr(exporter, "_load_json", changed_load)
    with pytest.raises(ResearchResultExportError, match="provenance conflicts"):
        exporter.build_frozen_data_quality_rows()


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


def test_failed_directory_swap_restores_all_previous_csvs(
    tmp_path: Path,
    evidence: ResearchEvidence,
) -> None:
    rows = build_research_rows(evidence)
    predictions, scopes = _frozen_formal_rows()
    output = tmp_path / "research-result"
    output.mkdir()
    previous = {
        name: f"old-{index}\n".encode()
        for index, name in enumerate(
            (
                "selected_configurations.csv",
                "holdout_metrics.csv",
                "benchmark_vs_naive_dm.csv",
                "within_company_dm.csv",
                "across_company_tests.csv",
                "principal_winners.csv",
                "sector_peer_summary.csv",
            )
        )
    }
    for name, content in previous.items():
        (output / name).write_bytes(content)
    calls = 0

    def fail_new_directory(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic replacement failure")
        os.replace(source, destination)

    with pytest.raises(ResearchResultExportError, match="publication failed"):
        publish_research_rows(
            rows,
            data_quality_rows=_synthetic_quality_rows(),
            holdout_prediction_rows=predictions,
            formal_scope_rows=scopes,
            output_dir=output,
            replace=fail_new_directory,
        )

    assert {name: (output / name).read_bytes() for name in previous} == previous
    assert not (output / "data_quality.csv").exists()


AUTHORITATIVE_RESULT_DIR = Path(__file__).resolve().parents[1] / "research-result"


@cache
def _frozen_formal_rows() -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    return build_frozen_formal_rows(load_frozen_formal_scope())


@cache
def _frozen_formal_csv_bytes() -> dict[str, bytes]:
    predictions, scope = _frozen_formal_rows()
    return {
        "holdout_predictions.csv": exporter._csv_bytes(HOLDOUT_PREDICTION_COLUMNS, predictions),
        "formal_scope.csv": exporter._csv_bytes(FORMAL_SCOPE_COLUMNS, scope),
    }


@cache
def _phase_6a2_rows() -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    return (build_data_provenance_rows(load_frozen_formal_scope()),
            build_model_diagnostic_rows(_phase_6a2_source()))


@cache
def _phase_6a2_source() -> dict[str, object]:
    return dict(load_frozen_diagnostic_evidence())


@cache
def _phase_6a2_csv_bytes() -> dict[str, bytes]:
    provenance, diagnostics = _phase_6a2_rows()
    return {
        "data_provenance.csv": exporter._csv_bytes(DATA_PROVENANCE_COLUMNS, provenance),
        "model_diagnostics.csv": exporter._csv_bytes(MODEL_DIAGNOSTIC_COLUMNS, diagnostics),
    }


@pytest.fixture(scope="module")
def frozen_source() -> FrozenFormalScope:
    return load_frozen_formal_scope()


def test_frozen_holdout_rows_expose_stored_aligned_predictions(
    frozen_source: FrozenFormalScope,
) -> None:
    rows, scopes = build_frozen_formal_rows(frozen_source)
    assert len(rows) == 3690
    assert len(scopes) == 15
    assert tuple(row["symbol"] for row in scopes) == tuple(company.symbol for company in COMPANIES)
    assert tuple(row["symbol"] for row in rows) == tuple(
        company.symbol for company in COMPANIES for _ in range(HOLDOUT_OBSERVATIONS)
    )
    common_dates = tuple(row["target_date"] for row in rows[:HOLDOUT_OBSERVATIONS])
    assert len(common_dates) == len(set(common_dates)) == HOLDOUT_OBSERVATIONS
    assert common_dates == tuple(sorted(common_dates))
    assert (common_dates[0], common_dates[-1]) == (HOLDOUT_START, HOLDOUT_END)
    for index, company in enumerate(COMPANIES):
        company_rows = rows[index * HOLDOUT_OBSERVATIONS : (index + 1) * HOLDOUT_OBSERVATIONS]
        stored = frozen_source.company_evidence[company.symbol]["canonical_holdout_records"]
        raw_dates = frozen_source.raw_dates[company.symbol]
        assert tuple(row["target_date"] for row in company_rows) == common_dates
        for row, record in zip(company_rows, stored, strict=True):
            assert tuple(row) == HOLDOUT_PREDICTION_COLUMNS
            assert (row["company_name"], row["sector"]) == (company.name, company.sector)
            target_index = raw_dates.index(row["target_date"])
            assert row["origin_date"] == raw_dates[target_index - 1]
            assert row["origin_date"] < row["target_date"]
            assert row["actual_close"] == record["actual_close"]
            for column, stored_field in (
                ("lag_reg_prediction", "lir_prediction"),
                ("arima_prediction", "arima_prediction"),
                ("lstm_prediction", "lstm_prediction"),
                ("naive_prediction", "naive_prediction"),
            ):
                assert row[column] == record[stored_field]
            assert all(math.isfinite(row[field]) for field in (
                "actual_close", "lag_reg_prediction", "arima_prediction",
                "lstm_prediction", "naive_prediction",
            ))
            assert (row["formal_run_id"], row["formal_cutoff"], row["formal_git_sha"]) == (
                FORMAL_RUN_ID, FORMAL_CUTOFF, FORMAL_GIT_SHA
            )


def test_frozen_formal_scope_records_executed_split(
    frozen_source: FrozenFormalScope,
) -> None:
    _, rows = build_frozen_formal_rows(frozen_source)
    assert len(rows) == 15
    for row, company in zip(rows, COMPANIES, strict=True):
        evidence = frozen_source.company_evidence[company.symbol]
        raw_dates = frozen_source.raw_dates[company.symbol]
        assert tuple(row) == FORMAL_SCOPE_COLUMNS
        assert (row["symbol"], row["company_name"], row["sector"]) == (
            company.symbol, company.name, company.sector
        )
        assert (row["raw_start"], row["raw_end"], row["raw_row_count"]) == (
            FORMAL_START, FORMAL_CUTOFF, len(raw_dates)
        )
        development = evidence["development_target_dates"]
        holdout = evidence["holdout_target_dates"]
        assert (row["development_start"], row["development_end"], row["development_pair_count"]) == (
            development[0], development[-1], len(development)
        )
        assert (row["holdout_start"], row["holdout_end"], row["holdout_pair_count"]) == (
            HOLDOUT_START, HOLDOUT_END, len(holdout)
        )
        assert row["forecast_pair_count"] == len(raw_dates) - 1 == len(development) + len(holdout)
        assert (row["cv_split_count"], row["forecast_horizon"], row["shuffle_used"]) == (5, 1, "false")


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ("missing_prediction", "LIR prediction"),
        ("nonfinite_prediction", "finite"),
        ("differing_dates", "target-date scope"),
        ("duplicate_date", "target-date scope"),
        ("wrong_identity", "identity"),
        ("wrong_raw_count", "provenance"),
        ("wrong_cv", "CV"),
        ("wrong_horizon", "forecast horizon"),
    ),
)
def test_frozen_formal_builder_fails_closed_on_corruption(
    frozen_source: FrozenFormalScope, change: str, message: str,
) -> None:
    source = deepcopy(frozen_source)
    symbol = COMPANIES[0].symbol
    company = source.company_evidence[symbol]
    if change == "missing_prediction":
        del company["canonical_holdout_records"][0]["lir_prediction"]
    elif change == "nonfinite_prediction":
        company["canonical_holdout_records"][0]["arima_prediction"] = float("nan")
    elif change == "differing_dates":
        company["holdout_target_dates"][0] = "2025-09-09"
    elif change == "duplicate_date":
        company["holdout_target_dates"][1] = company["holdout_target_dates"][0]
    elif change == "wrong_identity":
        source.run["git_state"]["commit"] = "wrong"
    elif change == "wrong_raw_count":
        source.raw_provenance["raw_files"][0]["row_count"] -= 1
    elif change == "wrong_cv":
        source.model_config["model_config"]["arima"]["cv_splits"] = 4
    elif change == "wrong_horizon":
        company["statistical_tests"]["diebold_mariano"]["holm_families"]["squared_error"][0]["forecast_horizon"] = 2
    with pytest.raises(ResearchResultExportError, match=message):
        build_frozen_formal_rows(source)


def test_new_frozen_csvs_are_in_deterministic_manifest(tmp_path: Path) -> None:
    output = _copy_substantive_package(tmp_path)
    first_path, first = export_results_manifest(output_dir=output)
    first_bytes = first_path.read_bytes()
    second_path, second = export_results_manifest(output_dir=output)
    assert second_path.read_bytes() == first_bytes
    assert first.package_content_sha256 == second.package_content_sha256
    entries = {row["filename"]: row for row in first.manifest_rows}
    assert tuple(entries) == SUBSTANTIVE_FILE_ORDER
    for filename, count, columns in (
        ("holdout_predictions.csv", 3690, HOLDOUT_PREDICTION_COLUMNS),
        ("formal_scope.csv", 15, FORMAL_SCOPE_COLUMNS),
    ):
        entry = entries[filename]
        assert entry["row_count"] == count
        assert entry["column_count"] == len(columns)
        assert entry["sha256"] == hashlib.sha256((output / filename).read_bytes()).hexdigest()
        assert entry["source_scope"] == "formal"
        assert entry["validation_status"] == "PASS"
        assert entry["supplementary_package_id"] == ""
        assert entry["package_content_sha256"] == first.package_content_sha256


@pytest.mark.parametrize("filename", ("holdout_predictions.csv", "formal_scope.csv"))
def test_missing_new_frozen_csv_fails_closed(tmp_path: Path, filename: str) -> None:
    output = _copy_substantive_package(tmp_path)
    (output / filename).unlink()
    with pytest.raises(ResearchResultExportError, match="missing"):
        validate_research_result_package(output)


@pytest.mark.parametrize(
    ("filename", "row_index", "column", "value", "message"),
    (
        ("holdout_predictions.csv", 0, "lag_reg_prediction", "", "numeric"),
        ("holdout_predictions.csv", 0, "naive_prediction", "nan", "finite"),
        ("holdout_predictions.csv", 1, "target_date", HOLDOUT_START, "dates conflict"),
        ("holdout_predictions.csv", 0, "origin_date", HOLDOUT_END, "not earlier"),
        ("formal_scope.csv", 0, "raw_row_count", "1634", "conflicts"),
        ("formal_scope.csv", 0, "development_pair_count", "1387", "pair scope"),
        ("formal_scope.csv", 0, "cv_split_count", "4", "conflicts"),
        ("formal_scope.csv", 0, "shuffle_used", "true", "conflicts"),
    ),
)
def test_new_csv_corruption_fails_package_validation(
    tmp_path: Path, filename: str, row_index: int, column: str,
    value: str, message: str,
) -> None:
    output = _copy_complete_package(tmp_path)
    _rewrite_csv_cell(output / filename, row_index=row_index, column=column, value=value)
    with pytest.raises(ResearchResultExportError, match=message):
        validate_research_result_package(output)


def test_publication_preserves_existing_research_index(
    tmp_path: Path, evidence: ResearchEvidence,
) -> None:
    destination = tmp_path / "research-result"
    destination.mkdir()
    readme = b"# Existing research index\n"
    (destination / "README.md").write_bytes(readme)
    frozen = load_frozen_formal_scope()
    predictions, scopes = build_frozen_formal_rows(frozen)
    publish_research_rows(
        build_research_rows(evidence),
        data_quality_rows=_synthetic_quality_rows(),
        holdout_prediction_rows=predictions,
        formal_scope_rows=scopes,
        output_dir=destination,
    )
    assert (destination / "README.md").read_bytes() == readme
    assert (destination / "holdout_predictions.csv").is_file()
    assert (destination / "formal_scope.csv").is_file()


def test_invalid_new_rows_are_rejected_before_publication(
    tmp_path: Path, evidence: ResearchEvidence,
) -> None:
    destination = tmp_path / "research-result"
    predictions, scopes = _frozen_formal_rows()
    malformed = [dict(row) for row in predictions]
    malformed[0]["naive_prediction"] = float("nan")
    with pytest.raises(ResearchResultExportError, match="finite"):
        publish_research_rows(
            build_research_rows(evidence),
            data_quality_rows=_synthetic_quality_rows(),
            holdout_prediction_rows=malformed,
            formal_scope_rows=scopes,
            output_dir=destination,
        )
    assert not destination.exists()


def test_frozen_provenance_exact_schema_and_source_evidence() -> None:
    rows, _ = _phase_6a2_rows()
    source = load_frozen_formal_scope()
    by_symbol = {item["symbol"]: item for item in source.raw_provenance["raw_files"]}
    assert len(rows) == 15
    assert tuple(row["symbol"] for row in rows) == tuple(c.symbol for c in COMPANIES)
    for company, row in zip(COMPANIES, rows, strict=True):
        archived = by_symbol[company.symbol]
        assert set(row) == set(DATA_PROVENANCE_COLUMNS)
        assert row["company_name"] == company.name and row["sector"] == company.sector
        assert row["source_name"] == archived["source_name"]
        assert row["source_reference"] == archived["source_reference"]
        assert row["retrieval_date"] == archived["retrieval_date"]
        assert date.fromisoformat(row["retrieval_date"]).isoformat() == row["retrieval_date"]
        assert row["raw_sha256"] == archived["sha256"]
        assert row["start_date"] == FORMAL_START and row["end_date"] == FORMAL_CUTOFF
        assert row["row_count"] == 1635
        assert row["correction_count"] == len(archived["correction_history"])
        assert row["session_completeness_status"] == "PASS"
        assert (row["formal_run_id"], row["formal_cutoff"], row["formal_git_sha"]) == (
            FORMAL_RUN_ID, FORMAL_CUTOFF, FORMAL_GIT_SHA)


@pytest.mark.parametrize(("field", "value", "message"), (
    ("sha256", "0" * 64, "SHA-256"),
    ("source_name", "", "source metadata"),
    ("source_reference", None, "source metadata"),
    ("retrieval_date", None, "retrieval date"),
    ("row_count", 1634, "scope"),
))
def test_frozen_provenance_fails_closed_on_corruption(
    field: str, value: object, message: str,
) -> None:
    source = deepcopy(load_frozen_formal_scope())
    source.raw_provenance["raw_files"][0][field] = value
    with pytest.raises(ResearchResultExportError, match=message):
        build_data_provenance_rows(source)


def test_incomplete_frozen_session_fails_provenance_export() -> None:
    source = deepcopy(load_frozen_formal_scope())
    source.session_completeness["companies"][0]["missing_dates"] = ["2020-01-03"]
    with pytest.raises(ResearchResultExportError, match="completeness"):
        build_data_provenance_rows(source)


def test_finalized_diagnostic_rows_keep_fitted_and_holdout_scopes_distinct() -> None:
    _, rows = _phase_6a2_rows()
    source = _phase_6a2_source()
    entries = source["status"]["companies"]
    assert len(rows) == 60
    assert tuple((row["symbol"], row["diagnostic_scope"], row["diagnostic_name"])
                 for row in rows) == tuple((company.symbol, scope, name)
                                         for company in COMPANIES for scope, name in DIAGNOSTIC_TYPES)
    assert len({(row["symbol"], row["diagnostic_scope"], row["diagnostic_name"])
                for row in rows}) == 60
    for index, company in enumerate(COMPANIES):
        actual = rows[index * 4:index * 4 + 4]
        fitted = entries[index]["fitted_model_diagnostics"]
        holdout = source["formal_companies"][company.symbol]["arima_diagnostics"]["holdout_forecast_errors"]
        assert all(set(row) == set(MODEL_DIAGNOSTIC_COLUMNS) for row in actual)
        assert all(row["model"] == "arima" and row["available"] == "true" for row in actual)
        assert all(row["supplementary_package_id"] == SUPPLEMENTARY_PACKAGE_ID for row in actual)
        assert actual[0]["boolean_result"] == exporter._bool_text(fitted["stability_flag"])
        assert actual[1]["boolean_result"] == exporter._bool_text(fitted["invertibility_flag"])
        for row, stored in ((actual[2], fitted["fitted_residuals"]["ljung_box"]),
                            (actual[3], holdout["ljung_box"])):
            assert row["observations"] == stored["observations"]
            assert row["lag"] == stored["lag"]
            assert row["model_df"] == stored["model_df"]
            assert row["statistic"] == stored["statistic"]
            assert row["p_value"] == stored["p_value"]
            assert math.isfinite(row["statistic"]) and 0 <= row["p_value"] <= 1
            assert row["boolean_result"] == ""
        assert actual[2]["evidence_source"] == "supplementary_arima_diagnostic_status"
        assert actual[3]["evidence_source"] == "formal_arima_holdout_diagnostics"


@pytest.mark.parametrize(("path", "value", "message"), (
    (("fitted_model_diagnostics", "stability_flag"), None, "stability_flag missing"),
    (("fitted_model_diagnostics", "fitted_residuals", "ljung_box", "p_value"), float("nan"), "finite"),
    (("fitted_model_diagnostics", "fitted_residuals", "ljung_box", "statistic"), float("inf"), "finite"),
    (("fitted_model_diagnostics", "fitted_residuals", "ljung_box", "p_value"), 2.0, "p-value"),
))
def test_malformed_finalized_diagnostic_fails_closed(
    path: tuple[str, ...], value: object, message: str,
) -> None:
    source = deepcopy(_phase_6a2_source())
    item = source["status"]["companies"][0]
    for part in path[:-1]:
        item = item[part]
    item[path[-1]] = value
    with pytest.raises(ResearchResultExportError, match=message):
        build_model_diagnostic_rows(source)


def test_missing_finalized_diagnostic_and_unavailability_reason_fail_closed() -> None:
    source = deepcopy(_phase_6a2_source())
    fitted = source["status"]["companies"][0]["fitted_model_diagnostics"]
    fitted["fitted_residuals"].pop("ljung_box")
    with pytest.raises(ResearchResultExportError, match="object"):
        build_model_diagnostic_rows(source)
    source = deepcopy(_phase_6a2_source())
    lb = source["status"]["companies"][0]["fitted_model_diagnostics"]["fitted_residuals"]["ljung_box"]
    lb["available"] = False
    lb["unavailable_reason"] = None
    with pytest.raises(ResearchResultExportError, match="unavailable reason"):
        build_model_diagnostic_rows(source)


def test_phase_6a2_manifest_and_package_validation(tmp_path: Path) -> None:
    output = _copy_substantive_package(tmp_path)
    path, validation = export_results_manifest(output_dir=output)
    first = path.read_bytes()
    assert export_results_manifest(output_dir=output)[0].read_bytes() == first
    entries = {row["filename"]: row for row in validation.manifest_rows}
    assert len(entries) == 14
    for filename, count, schema, scope in (
        ("data_provenance.csv", 15, DATA_PROVENANCE_COLUMNS, "formal"),
        ("model_diagnostics.csv", 60, MODEL_DIAGNOSTIC_COLUMNS, "formal+supplementary"),
    ):
        row = entries[filename]
        with (output / filename).open(encoding="utf-8", newline="") as handle:
            assert tuple(csv.DictReader(handle).fieldnames or ()) == schema
        assert row["row_count"] == count and row["column_count"] == len(schema)
        assert row["source_scope"] == scope and row["validation_status"] == "PASS"
        assert row["sha256"] == hashlib.sha256((output / filename).read_bytes()).hexdigest()
        assert row["package_content_sha256"] == validation.package_content_sha256
    assert entries["model_diagnostics.csv"]["supplementary_package_id"] == SUPPLEMENTARY_PACKAGE_ID


@pytest.mark.parametrize(("filename", "column", "value", "message"), (
    ("data_provenance.csv", "raw_sha256", "bad", "SHA-256"),
    ("data_provenance.csv", "formal_run_id", "wrong", "formal_run_id"),
    ("model_diagnostics.csv", "p_value", "nan", "finite"),
    ("model_diagnostics.csv", "evidence_source", "", "provenance"),
    ("model_diagnostics.csv", "supplementary_package_id", "wrong", "provenance"),
))
def test_phase_6a2_package_corruption_fails_closed(
    tmp_path: Path, filename: str, column: str, value: str, message: str,
) -> None:
    output = _copy_complete_package(tmp_path)
    row_index = 2 if filename == "model_diagnostics.csv" and column == "p_value" else 0
    _rewrite_csv_cell(output / filename, row_index=row_index, column=column, value=value)
    with pytest.raises(ResearchResultExportError, match=message):
        validate_research_result_package(output)


AUTHORITATIVE_SUBSTANTIVE_HASHES = {
    "selected_configurations.csv": (
        "7c648357adaba1e5769d560435bad61a933d67ebb5ee8fc1ded5944416737a97"
    ),
    "holdout_metrics.csv": (
        "836974efff91c52c0cdd1d492279b8fe11476fadff6dc575b6a22870eec3548a"
    ),
    "benchmark_vs_naive_dm.csv": (
        "a4d0bdef371bad9fe1d0f424da65a702e44b289e4798fa5e69ec94d2710900a3"
    ),
    "within_company_dm.csv": (
        "e9c27f42de578bded049d9d33f7890acceb7cf7d1a9dc169a49f81bf4a639f96"
    ),
    "across_company_tests.csv": (
        "131f69a47061aa75cd2ff467132d193d3aa02d9eaaa8501506d020e827a416b6"
    ),
    "principal_winners.csv": (
        "6bbb839974d84dd39780565f614f3fdcb4b2c311aeeee3f9897f68bd2b689aef"
    ),
    "sector_peer_summary.csv": (
        "283cec1287dea54e9a4be8eaec043ee172b97219674e11f38bcc32890148002f"
    ),
    "data_quality.csv": (
        "6ce753f5d3a65a62633570c2ca241d85ed13272bef73d64b6f39398da328bd8a"
    ),
}


def _copy_substantive_package(tmp_path: Path) -> Path:
    destination = tmp_path / "research-result"
    destination.mkdir()
    for filename in AUTHORITATIVE_SUBSTANTIVE_HASHES:
        (destination / filename).write_bytes(
            (AUTHORITATIVE_RESULT_DIR / filename).read_bytes()
        )
    for filename, payload in _frozen_formal_csv_bytes().items():
        (destination / filename).write_bytes(payload)
    for filename, payload in _phase_6a2_csv_bytes().items():
        (destination / filename).write_bytes(payload)
    return destination


def _copy_complete_package(tmp_path: Path) -> Path:
    destination = _copy_substantive_package(tmp_path)
    export_results_manifest(output_dir=destination)
    return destination


def _rewrite_csv_cell(
    path: Path,
    *,
    row_index: int,
    column: str,
    value: str,
) -> None:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        columns = tuple(reader.fieldnames or ())
        rows = list(reader)
    rows[row_index][column] = value
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_authoritative_substantive_csv_hashes_are_frozen() -> None:
    assert {
        filename: hashlib.sha256(
            (AUTHORITATIVE_RESULT_DIR / filename).read_bytes()
        ).hexdigest()
        for filename in AUTHORITATIVE_SUBSTANTIVE_HASHES
    } == AUTHORITATIVE_SUBSTANTIVE_HASHES


def test_data_quality_rule_rows_match_the_locked_contract() -> None:
    rows = build_data_quality_rule_rows()
    indexed = {row["rule_name"]: row for row in rows}

    assert len(rows) == 6
    assert tuple(indexed) == (
        "basic_ohlcv_validity",
        "trading_session_continuity",
        "zero_volume",
        "stale_price",
        "ohlcv_activity_proxy",
        "material_discontinuity",
    )
    assert sum(row["rule_category"] == "hard" for row in rows) == 2
    assert sum(row["rule_category"] == "screening" for row in rows) == 4
    assert {row["rule_version"] for row in rows} == {"data-quality-v1"}
    assert indexed["zero_volume"]["threshold_value"] == "0"
    assert indexed["stale_price"]["threshold_value"] == "5"
    assert indexed["stale_price"]["threshold_unit"] == "consecutive sessions"
    assert indexed["ohlcv_activity_proxy"]["threshold_value"] == "0.95"
    assert indexed["material_discontinuity"]["threshold_value"] == "0.30"
    assert all(
        row["fail_condition"] and row["effect_on_dataset_quality"] == "FAIL if rule fails"
        for row in rows
        if row["rule_category"] == "hard"
    )
    assert all(
        row["fail_condition"] == ""
        and row["effect_on_dataset_quality"]
        == "review only; does not cause dataset-quality FAIL"
        for row in rows
        if row["rule_category"] == "screening"
    )


def test_principal_win_summary_is_derived_and_majority_is_deterministic() -> None:
    with (
        AUTHORITATIVE_RESULT_DIR / "principal_winners.csv"
    ).open("r", encoding="utf-8", newline="") as source:
        authoritative = list(csv.DictReader(source))
    rows = build_principal_win_summary_rows(authoritative)

    assert tuple(row["model"] for row in rows) == PRINCIPAL_METHODS
    assert [row["win_count"] for row in rows] == [4, 7, 4]
    assert sum(int(row["win_count"]) for row in rows) == 15
    assert all(row["total_companies"] == 15 for row in rows)
    assert [row["win_share"] for row in rows] == [4 / 15, 7 / 15, 4 / 15]
    assert all(row["strict_majority_threshold"] == 8 for row in rows)
    assert all(row["strict_majority_achieved"] == "false" for row in rows)
    assert all(row["overall_majority_model"] == "" for row in rows)
    assert all(row["selection_metric"] == "rmse" for row in rows)
    assert all(
        row["interpretation"]
        == "descriptive company-level win count; not a statistical significance test"
        for row in rows
    )

    synthetic = [
        {
            "symbol": company.symbol,
            "best_principal_model": (
                "lag_reg" if index < 8 else "arima" if index < 12 else "lstm"
            ),
        }
        for index, company in enumerate(COMPANIES)
    ]
    majority = build_principal_win_summary_rows(synthetic)
    assert [row["strict_majority_achieved"] for row in majority] == [
        "true",
        "false",
        "false",
    ]
    assert {row["overall_majority_model"] for row in majority} == {"lag_reg"}


def test_manifest_contract_cross_file_validation_and_determinism(
    tmp_path: Path,
) -> None:
    output = _copy_substantive_package(tmp_path)
    first_path, first_validation = export_results_manifest(output_dir=output)
    first_bytes = first_path.read_bytes()
    second_path, second_validation = export_results_manifest(output_dir=output)

    assert second_path.read_bytes() == first_bytes
    assert first_validation.package_content_sha256 == (
        second_validation.package_content_sha256
    )
    with first_path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        manifest = list(reader)
        assert tuple(reader.fieldnames or ()) == MANIFEST_COLUMNS
    assert len(manifest) == len(SUBSTANTIVE_FILE_ORDER)
    assert tuple(row["filename"] for row in manifest) == SUBSTANTIVE_FILE_ORDER
    assert len({row["filename"] for row in manifest}) == len(SUBSTANTIVE_FILE_ORDER)

    package_source = b""
    for row in manifest:
        filename = row["filename"]
        payload = (output / filename).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        package_source += f"{filename}\t{digest}\n".encode()
        assert int(row["row_count"]) == SUBSTANTIVE_FILE_ROW_COUNTS[filename]
        assert int(row["column_count"]) == len(SUBSTANTIVE_FILE_SCHEMAS[filename])
        assert row["sha256"] == digest
        assert row["formal_run_id"] == FORMAL_RUN_ID
        assert row["formal_cutoff"] == FORMAL_CUTOFF
        assert row["formal_git_sha"] == FORMAL_GIT_SHA
        assert row["formal_archive_sha256"] == FORMAL_AGGREGATE_SHA256
        assert row["validation_status"] == "PASS"
        if filename in {
            "holdout_metrics.csv",
            "within_company_dm.csv",
            "across_company_tests.csv",
            "principal_winners.csv",
            "model_diagnostics.csv",
        }:
            assert row["supplementary_package_id"] == SUPPLEMENTARY_PACKAGE_ID
        else:
            assert row["supplementary_package_id"] == ""
        assert row["rule_version"] == (
            "data-quality-v1"
            if filename in {"data_quality.csv", "data_quality_rules.csv"}
            else ""
        )

    expected_package_hash = hashlib.sha256(package_source).hexdigest()
    assert {
        row["package_content_sha256"] for row in manifest
    } == {expected_package_hash}
    assert "results_manifest.csv" not in package_source.decode()
    assert first_validation.principal_winner_counts == {
        "lag_reg": 4,
        "arima": 7,
        "lstm": 4,
    }
    assert first_validation.best_evaluated_method_counts == {
        "lag_reg": 3,
        "arima": 7,
        "lstm": 4,
        "naive": 1,
    }


def test_package_content_hash_changes_when_valid_substantive_bytes_change(
    tmp_path: Path,
) -> None:
    output = _copy_complete_package(tmp_path)
    original = validate_research_result_package(output).package_content_sha256
    path = output / "selected_configurations.csv"
    with path.open("r", encoding="utf-8", newline="") as source:
        first = next(csv.DictReader(source))
    changed_value = first["lstm_selection_mean_validation_rmse"] + "0"
    _rewrite_csv_cell(
        path,
        row_index=0,
        column="lstm_selection_mean_validation_rmse",
        value=changed_value,
    )

    changed = validate_research_result_package(output).package_content_sha256
    assert changed != original


def test_missing_substantive_csv_fails_closed(tmp_path: Path) -> None:
    output = _copy_complete_package(tmp_path)
    (output / "holdout_metrics.csv").unlink()

    with pytest.raises(ResearchResultExportError, match="missing"):
        validate_research_result_package(output)


@pytest.mark.parametrize(
    "filename",
    ("data_quality_rules.csv", "principal_win_summary.csv"),
)
def test_missing_research_closure_csv_fails_closed(
    tmp_path: Path,
    filename: str,
) -> None:
    output = _copy_complete_package(tmp_path)
    (output / filename).unlink()

    with pytest.raises(ResearchResultExportError, match="missing"):
        validate_research_result_package(output)


@pytest.mark.parametrize(
    ("filename", "row_index", "column", "value", "message"),
    [
        (
            "selected_configurations.csv",
            0,
            "symbol",
            "APX",
            "company symbols",
        ),
        (
            "holdout_metrics.csv",
            3,
            "method",
            "lag_reg",
            "duplicate row",
        ),
        (
            "benchmark_vs_naive_dm.csv",
            0,
            "raw_p_value",
            "0.9",
            "does not match",
        ),
        (
            "within_company_dm.csv",
            0,
            "holm_family_size",
            "5",
            "Holm family size",
        ),
        (
            "across_company_tests.csv",
            1,
            "performed",
            "true",
            "Wilcoxon gate",
        ),
        (
            "principal_winners.csv",
            0,
            "best_principal_model",
            "arima",
            "winner conflicts",
        ),
        (
            "sector_peer_summary.csv",
            0,
            "company_name",
            "Wrong Company",
            "company name",
        ),
        (
            "data_quality.csv",
            0,
            "rule_version",
            "wrong-rule",
            "frozen contract",
        ),
        (
            "data_quality_rules.csv",
            3,
            "threshold_value",
            "4",
            "locked data-quality-v1 rules",
        ),
        (
            "principal_win_summary.csv",
            0,
            "win_count",
            "5",
            "conflicts with principal_winners",
        ),
        (
            "holdout_metrics.csv",
            0,
            "formal_run_id",
            "wrong-run",
            "formal_run_id",
        ),
    ],
)
def test_cross_file_corruption_fails_closed(
    tmp_path: Path,
    filename: str,
    row_index: int,
    column: str,
    value: str,
    message: str,
) -> None:
    output = _copy_complete_package(tmp_path)
    _rewrite_csv_cell(
        output / filename,
        row_index=row_index,
        column=column,
        value=value,
    )

    with pytest.raises(ResearchResultExportError, match=message):
        validate_research_result_package(output)


def test_malformed_csv_fails_closed(tmp_path: Path) -> None:
    output = _copy_complete_package(tmp_path)
    (output / "holdout_metrics.csv").write_bytes(b'"unterminated')

    with pytest.raises(ResearchResultExportError, match="malformed CSV"):
        validate_research_result_package(output)


def test_failed_closure_publication_restores_all_previous_files(tmp_path: Path) -> None:
    output = _copy_complete_package(tmp_path)
    validation = validate_research_result_package(output)
    closure_names = (
        "data_quality_rules.csv",
        "principal_win_summary.csv",
        "results_manifest.csv",
    )
    previous = {name: (output / name).read_bytes() for name in closure_names}
    closure_payloads = {
        name: previous[name]
        for name in ("data_quality_rules.csv", "principal_win_summary.csv")
    }
    calls = 0

    def fail_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 5:
            raise OSError("synthetic replacement failure")
        os.replace(source, destination)

    with pytest.raises(ResearchResultExportError, match="publication failed"):
        publish_research_closure(
            validation,
            closure_payloads=closure_payloads,
            output_dir=output,
            replace=fail_replace,
        )

    assert {name: (output / name).read_bytes() for name in closure_names} == previous
    assert not tuple(output.glob(".research-closure-*"))


def test_manifest_validation_does_not_execute_research_or_model_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = _copy_substantive_package(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("research recomputation path was invoked")

    monkeypatch.setattr(exporter, "load_authoritative_evidence", forbidden)
    monkeypatch.setattr(exporter, "build_research_rows", forbidden)
    monkeypatch.setattr(exporter, "build_frozen_data_quality_rows", forbidden)

    path, validation = export_results_manifest(output_dir=output)
    assert path.is_file()
    assert len(validation.manifest_rows) == len(SUBSTANTIVE_FILE_ORDER)
