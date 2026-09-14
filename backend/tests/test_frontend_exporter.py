"""Schema and atomic-publication tests for every frontend forecast file."""

from dataclasses import replace
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

import pytest

from config.companies import COMPANIES
from config.model_config import ModelConfig, ModelId
from src.data.split import build_company_evaluation_plan
from src.data.validator import OhlcvRecord
from src.evaluation.evaluator import ModelPredictionOutput, evaluate_prediction_outputs
from src.export import frontend_exporter as exporter_module
from src.export.frontend_exporter import (
    build_frontend_payloads,
    CompanyFrontendArtifacts,
    FrontendExportBundle,
    FrontendExportError,
    export_frontend_forecasts,
)
from src.export.schemas import (
    EVALUATION_MODEL_IDS,
    FrontendSchemaError,
    MODEL_DISPLAY_LABELS,
    NEXT_CLOSE_KEYS,
    PRINCIPAL_MODEL_IDS,
    validate_document,
)
from src.inference.next_day import CompanyNextDayForecast, NextDayPrediction


MANILA = ZoneInfo("Asia/Manila")


def synthetic_records(symbol_index: int, count: int = 80) -> tuple[OhlcvRecord, ...]:
    start = date(2026, 5, 1)
    close = 50.0 + symbol_index
    records: list[OhlcvRecord] = []
    for index in range(count):
        close += 0.4 if index % 3 else -0.15
        records.append(
            OhlcvRecord(
                trading_date=start + timedelta(days=index),
                open=close - 0.2,
                high=close + 0.6,
                low=close - 0.6,
                close=close,
                volume=10_000.0 + symbol_index * 100.0 + index,
            )
        )
    return tuple(records)


def company_source(symbol: str, symbol_index: int) -> CompanyFrontendArtifacts:
    records = synthetic_records(symbol_index)
    plan = build_company_evaluation_plan(
        symbol,
        records,
        model_config=ModelConfig(evaluation_proportion=0.8),
    )
    actual = tuple(pair.actual_close for pair in plan.evaluation_pairs)
    evaluation = evaluate_prediction_outputs(
        plan,
        (
            ModelPredictionOutput(
                symbol=symbol,
                model=ModelId.LAG_REGRESSION,
                target_dates=plan.evaluation_target_dates,
                actual_closes=actual,
                predicted_closes=tuple(value + 0.1 for value in actual),
            ),
            ModelPredictionOutput(
                symbol=symbol,
                model=ModelId.ARIMA,
                target_dates=plan.evaluation_target_dates,
                actual_closes=actual,
                predicted_closes=tuple(value + 0.2 for value in actual),
            ),
            ModelPredictionOutput(
                symbol=symbol,
                model=ModelId.LSTM,
                target_dates=plan.evaluation_target_dates,
                actual_closes=actual,
                predicted_closes=tuple(value + 0.3 for value in actual),
            ),
        ),
    )
    origin = records[-1]
    direction = 0.0 if symbol_index == 0 else (1.0 if symbol_index % 2 else -1.0)
    inference_at = datetime(2026, 7, 20, 18, 30, tzinfo=MANILA)
    forecast_for = date(2026, 7, 21)
    adjustments = {
        ModelId.LAG_REGRESSION: direction,
        ModelId.ARIMA: direction + 0.25,
        ModelId.LSTM: direction - 0.25,
    }
    predictions = tuple(
        NextDayPrediction(
            symbol=symbol,
            model=model,
            origin_date=origin.trading_date,
            forecast_for=forecast_for,
            origin_close=origin.close,
            predicted_delta=adjustments[model],
            predicted_close=origin.close + adjustments[model],
            inference_at=inference_at,
        )
        for model in PRINCIPAL_MODEL_IDS
    )
    return CompanyFrontendArtifacts(
        records=records,
        evaluation=evaluation,
        next_day_forecast=CompanyNextDayForecast(
            symbol=symbol,
            origin_date=origin.trading_date,
            forecast_for=forecast_for,
            predictions=predictions,
        ),
    )


@pytest.fixture
def export_bundle() -> FrontendExportBundle:
    return FrontendExportBundle(
        companies=tuple(
            company_source(company.symbol, index)
            for index, company in enumerate(COMPANIES)
        ),
        generated_at=datetime(2026, 7, 20, 18, 45, tzinfo=MANILA),
        last_run_at=datetime(2026, 7, 20, 18, 40, tzinfo=MANILA),
    )


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_operational_file_matches_contract_and_new_artifacts(
    tmp_path: Path,
    export_bundle: FrontendExportBundle,
) -> None:
    output_root = tmp_path / "frontend" / "public" / "forecasts"
    output_root.mkdir(parents=True)
    output_root.joinpath("companies.json").write_text(
        '[{"latestClose":999999}]\n', encoding="utf-8"
    )

    result = export_frontend_forecasts(export_bundle, output_root=output_root)

    expected_relative_paths = {
        "companies.json",
        "dashboard.json",
        "latest.json",
        "metrics.json",
        *(f"company/{company.symbol}.json" for company in COMPANIES),
        *(f"history/{company.symbol}.json" for company in COMPANIES),
    }
    assert {path.relative_to(output_root).as_posix() for path in result.files} == (
        expected_relative_paths
    )
    assert len(result.files) == 4 + 2 * len(COMPANIES)

    for path in result.files:
        relative_path = path.relative_to(output_root).as_posix()
        validate_document(relative_path, load_json(path))

    companies = load_json(output_root / "companies.json")
    dashboard = load_json(output_root / "dashboard.json")
    latest = load_json(output_root / "latest.json")
    metrics = load_json(output_root / "metrics.json")
    assert len(companies) == len(COMPANIES)
    assert all(company["latestClose"] != 999999 for company in companies)
    assert dashboard["totalCompanies"] == len(COMPANIES)
    assert dashboard["missingCompanies"] == []
    assert dashboard["topGainer"] is not None
    assert dashboard["topLoser"] is not None
    assert latest["forecastDate"] == "2026-07-21"
    assert latest["generatedAt"].endswith("+08:00")
    assert latest["lastRunAt"].endswith("+08:00")
    assert metrics["statisticalTests"]["schema_id"] == (
        "forecastph.evaluation-statistics"
    )
    assert metrics["statisticalTests"]["scope"] == "complete_aligned_evaluation"
    across_company_tests = metrics["statisticalTests"]["across_company"]
    assert across_company_tests["metric"] == "mase"
    assert isinstance(across_company_tests["posthoc_performed"], bool)
    assert metrics["aggregateStatistic"] == "median"
    assert metrics["crossCompany"]["selectionBasis"].startswith(
        "median_within_company_rmse_rank"
    )
    assert metrics["crossCompany"]["companyCount"] == len(export_bundle.companies)
    assert set(metrics["crossCompany"]["methods"]) == {
        MODEL_DISPLAY_LABELS[model] for model in EVALUATION_MODEL_IDS
    }
    assert all(
        "bestPrincipalModel" in company
        and "bestEvaluatedMethod" in company
        and "bestPrincipalBeatsNaive" in company
        and "allPrincipalsWorseThanNaive" in company
        for company in metrics["perCompany"].values()
    )
    assert all(
        len(
            company["statisticalTests"]["diebold_mariano"]["holm_families"][
                loss_type
            ]
        )
        == 6
        for company in metrics["perCompany"].values()
        for loss_type in ("squared_error", "absolute_error")
    )
    assert all(
        isinstance(company["bestPrincipalBeatsNaive"], bool)
        for company in metrics["perCompany"].values()
    )

    source = next(item for item in export_bundle.companies if item.symbol == "ALI")
    detail = load_json(output_root / "company" / "ALI.json")
    history = load_json(output_root / "history" / "ALI.json")
    assert history == {"symbol": "ALI", "ohlcv": detail["ohlcv"]}
    assert len(detail["backtestDates"]) == 60
    assert detail["backtestDates"] == [
        value.isoformat() for value in source.evaluation.backtest.target_dates[-60:]
    ]
    assert detail["backtestActual"] == list(
        source.evaluation.backtest.actual_closes[-60:]
    )
    assert detail["evaluationMetadata"] == {
        "fullSessionCount": 64,
        "fullStartDate": "2026-05-17",
        "fullEndDate": "2026-07-19",
        "displayedSessionCount": 60,
        "displayedStartDate": detail["backtestDates"][0],
        "displayedEndDate": detail["backtestDates"][-1],
        "displayWindowLimit": 60,
        "metricsScope": "complete_aligned_evaluation",
        "statisticalTestsScope": "complete_aligned_evaluation",
    }
    assert detail["bestPrincipalModel"] == "Lag-Informed Regression"
    assert detail["bestEvaluatedMethod"] == "Lag-Informed Regression"
    assert detail["bestPrincipalBeatsNaive"] is True
    assert detail["allPrincipalsWorseThanNaive"] is False
    assert metrics["perCompany"]["ALI"]["evaluationMetadata"] == detail[
        "evaluationMetadata"
    ]
    assert detail["productionBacktestDates"] == []
    assert detail["productionBacktestActual"] == []
    assert all(not values for values in detail["productionBacktestByModel"].values())
    assert set(detail["nextClose"]) == {"lag", "arima", "lstm"}
    for model in PRINCIPAL_MODEL_IDS:
        prediction = source.next_day_forecast.prediction_for(model)
        assert detail["nextClose"][NEXT_CLOSE_KEYS[model]] == prediction.predicted_close
    for model in EVALUATION_MODEL_IDS:
        canonical = source.evaluation.backtest.records_for(model)[-60:]
        label = MODEL_DISPLAY_LABELS[model]
        assert detail["backtestByModel"][label] == [
            record.predicted_close for record in canonical
        ]
        exported_errors = [
            predicted - actual
            for predicted, actual in zip(
                detail["backtestByModel"][label],
                detail["backtestActual"],
                strict=True,
            )
        ]
        assert exported_errors == pytest.approx([record.error for record in canonical])
        canonical_metric = source.evaluation.metrics_for(model)
        assert detail["metrics"][model.value] == {
            "rmse": canonical_metric.rmse,
            "mae": canonical_metric.mae,
            "mase": canonical_metric.mase,
            "r2": canonical_metric.r2,
        }


def test_company_schema_rejects_display_metadata_that_misrepresents_full_holdout(
    export_bundle: FrontendExportBundle,
) -> None:
    detail = build_frontend_payloads(export_bundle)["company/ALI.json"]
    detail["evaluationMetadata"]["fullSessionCount"] = 59

    with pytest.raises(FrontendSchemaError, match="60-session display subset"):
        validate_document("company/ALI.json", detail)


def test_exporter_uses_medians_not_means_for_descriptive_aggregate(
    export_bundle: FrontendExportBundle,
) -> None:
    changed_sources: list[CompanyFrontendArtifacts] = []
    lir_mase_values: list[float] = []
    for index, source in enumerate(export_bundle.companies):
        replacement_mase = 1_000.0 if index == 0 else 0.5
        metrics_by_model = dict(source.evaluation.metrics_by_model)
        metrics_by_model[ModelId.LAG_REGRESSION] = replace(
            metrics_by_model[ModelId.LAG_REGRESSION],
            mase=replacement_mase,
        )
        lir_mase_values.append(replacement_mase)
        changed_sources.append(
            replace(
                source,
                evaluation=replace(
                    source.evaluation,
                    metrics_by_model=tuple(metrics_by_model.items()),
                ),
            )
        )

    payloads = build_frontend_payloads(
        replace(export_bundle, companies=tuple(changed_sources))
    )
    exported = payloads["metrics.json"]["aggregate"][
        MODEL_DISPLAY_LABELS[ModelId.LAG_REGRESSION]
    ]["mase"]

    assert exported == statistics.median(lir_mase_values)
    assert exported != statistics.fmean(lir_mase_values)


def test_incomplete_next_day_artifact_cannot_replace_existing_export(
    tmp_path: Path,
    export_bundle: FrontendExportBundle,
) -> None:
    output_root = tmp_path / "forecasts"
    output_root.mkdir()
    companies_path = output_root / "companies.json"
    previous = b'{"existing":"unchanged"}\n'
    companies_path.write_bytes(previous)
    first = export_bundle.companies[0]
    incomplete_forecast = replace(
        first.next_day_forecast,
        predictions=first.next_day_forecast.predictions[:-1],
    )
    incomplete_source = replace(first, next_day_forecast=incomplete_forecast)
    invalid_bundle = replace(
        export_bundle,
        companies=(incomplete_source, *export_bundle.companies[1:]),
    )

    with pytest.raises(FrontendExportError, match="exactly three"):
        export_frontend_forecasts(invalid_bundle, output_root=output_root)

    assert companies_path.read_bytes() == previous
    assert not (output_root / "dashboard.json").exists()


def test_publish_failure_rolls_back_every_replaced_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    export_bundle: FrontendExportBundle,
) -> None:
    output_root = tmp_path / "forecasts"
    output_root.mkdir()
    previous_companies = b'["previous companies"]\n'
    previous_dashboard = b'{"previous":"dashboard"}\n'
    (output_root / "companies.json").write_bytes(previous_companies)
    (output_root / "dashboard.json").write_bytes(previous_dashboard)
    real_replace = exporter_module._replace_staged_file
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected publication failure")
        real_replace(source, destination)

    monkeypatch.setattr(exporter_module, "_replace_staged_file", fail_second_replace)

    with pytest.raises(FrontendExportError, match="Atomic frontend export failed"):
        export_frontend_forecasts(export_bundle, output_root=output_root)

    assert (output_root / "companies.json").read_bytes() == previous_companies
    assert (output_root / "dashboard.json").read_bytes() == previous_dashboard
    assert not (output_root / "latest.json").exists()
    assert not any(output_root.parent.glob(".forecast-export-*"))
