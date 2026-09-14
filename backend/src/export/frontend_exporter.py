"""Build and atomically publish frontend JSON from new backend results only."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import math
import os
from pathlib import Path
import statistics
import tempfile

from config.companies import COMPANIES, Company, get_company
from config.model_config import ModelId
from config.settings import BACKEND_ROOT, as_manila_time
from src.data.validator import OhlcvRecord, require_chronological_records
from src.evaluation.evaluator import CompanyEvaluation
from src.evaluation.model_selection import summarize_cross_company_metrics
from src.export.schemas import (
    BACKTEST_WINDOW,
    EVALUATION_MODEL_IDS,
    MODEL_DISPLAY_LABELS,
    NEXT_CLOSE_KEYS,
    PRINCIPAL_MODEL_IDS,
    FrontendSchemaError,
    validate_document,
)
from src.inference.next_day import CompanyNextDayForecast


LOGGER = logging.getLogger(__name__)
FRONTEND_FORECASTS_DIR = BACKEND_ROOT.parent / "frontend" / "public" / "forecasts"


class FrontendExportError(RuntimeError):
    """Raised before publishing an incomplete or inconsistent frontend export."""


@dataclass(frozen=True, slots=True)
class CompanyFrontendArtifacts:
    """New backend results required to export one configured company."""

    records: tuple[OhlcvRecord, ...]
    evaluation: CompanyEvaluation
    next_day_forecast: CompanyNextDayForecast

    @property
    def symbol(self) -> str:
        return self.evaluation.symbol


@dataclass(frozen=True, slots=True)
class FrontendExportBundle:
    """Complete successful-run inputs; existing frontend JSON is never an input."""

    companies: tuple[CompanyFrontendArtifacts, ...]
    generated_at: datetime
    last_run_at: datetime
    status: str = "complete"


@dataclass(frozen=True, slots=True)
class FrontendExportResult:
    output_root: Path
    files: tuple[Path, ...]


def _metric_payload(evaluation: CompanyEvaluation, model: ModelId) -> dict[str, float]:
    metric = evaluation.metrics_for(model)
    values = {
        "rmse": float(metric.rmse),
        "mae": float(metric.mae),
        "mase": float(metric.mase),
        "r2": float(metric.r2),
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise FrontendExportError(
            f"Non-finite canonical metric symbol={evaluation.symbol} model={model.value}"
        )
    return values


def _validate_source(source: CompanyFrontendArtifacts) -> Company:
    if not isinstance(source.evaluation, CompanyEvaluation):
        raise FrontendExportError("Exporter requires a new CompanyEvaluation artifact")
    if not isinstance(source.next_day_forecast, CompanyNextDayForecast):
        raise FrontendExportError("Exporter requires a new CompanyNextDayForecast artifact")
    company = get_company(source.symbol)
    records = tuple(source.records)
    require_chronological_records(records)
    if source.next_day_forecast.symbol != company.symbol:
        raise FrontendExportError(f"Forecast symbol mismatch for {company.symbol}")
    if source.evaluation.backtest.symbol != company.symbol:
        raise FrontendExportError(f"Backtest symbol mismatch for {company.symbol}")
    if (
        source.evaluation.backtest.target_dates
        != source.evaluation.plan.evaluation_target_dates
    ):
        raise FrontendExportError(f"Backtest dates diverge from the plan for {company.symbol}")
    if len(source.evaluation.backtest.target_dates) < BACKTEST_WINDOW:
        raise FrontendExportError(
            f"{company.symbol} requires at least {BACKTEST_WINDOW} OOS evaluation sessions"
        )
    latest = records[-1]
    forecast = source.next_day_forecast
    if forecast.origin_date != latest.trading_date:
        raise FrontendExportError(f"Forecast origin does not match raw history for {company.symbol}")
    if forecast.forecast_for <= forecast.origin_date:
        raise FrontendExportError(f"Forecast date must follow origin for {company.symbol}")
    predictions = tuple(forecast.predictions)
    by_model = {prediction.model: prediction for prediction in predictions}
    if len(by_model) != len(predictions) or set(by_model) != set(PRINCIPAL_MODEL_IDS):
        raise FrontendExportError(
            f"{company.symbol} must have exactly three unique principal forecasts"
        )
    for model, prediction in by_model.items():
        if (
            prediction.symbol != company.symbol
            or prediction.origin_date != forecast.origin_date
            or prediction.forecast_for != forecast.forecast_for
            or prediction.origin_close != latest.close
        ):
            raise FrontendExportError(
                f"Inconsistent next-day prediction for {company.symbol}/{model.value}"
            )
        if prediction.inference_at.tzinfo is None or prediction.inference_at.utcoffset() is None:
            raise FrontendExportError("Inference timestamps must be timezone-aware")
        if not all(
            math.isfinite(value)
            for value in (
                prediction.origin_close,
                prediction.predicted_delta,
                prediction.predicted_close,
            )
        ):
            raise FrontendExportError("Next-day predictions must be finite")
        if not math.isclose(
            prediction.predicted_close,
            prediction.origin_close + prediction.predicted_delta,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise FrontendExportError("Next-day Close reconstruction is inconsistent")
    for model in EVALUATION_MODEL_IDS:
        records_for_model = source.evaluation.backtest.records_for(model)
        if len(records_for_model) != len(source.evaluation.backtest.target_dates):
            raise FrontendExportError(f"Incomplete OOS records for {company.symbol}/{model.value}")
        for target_date, actual_close, prediction in zip(
            source.evaluation.backtest.target_dates,
            source.evaluation.backtest.actual_closes,
            records_for_model,
            strict=True,
        ):
            if (
                prediction.symbol != company.symbol
                or prediction.model is not model
                or prediction.target_date != target_date
                or prediction.target_date
                <= source.evaluation.plan.development_target_dates[-1]
                or prediction.actual_close != actual_close
                or prediction.origin_date >= prediction.target_date
                or prediction.error != prediction.predicted_close - prediction.actual_close
            ):
                raise FrontendExportError(
                    f"Invalid canonical OOS record for {company.symbol}/{model.value}"
                )
    ranking = source.evaluation.principal_ranking
    if ranking.criterion != "rmse" or ranking.best_model not in PRINCIPAL_MODEL_IDS:
        raise FrontendExportError("Company best model must use principal evaluation RMSE")
    canonical_order = {model: index for index, model in enumerate(PRINCIPAL_MODEL_IDS)}
    expected_best = min(
        PRINCIPAL_MODEL_IDS,
        key=lambda model: (
            source.evaluation.metrics_for(model).rmse,
            canonical_order[model],
        ),
    )
    if ranking.best_model is not expected_best:
        raise FrontendExportError("Company best model disagrees with evaluation RMSE")
    return company


def _ohlcv_payload(records: Sequence[OhlcvRecord]) -> list[dict[str, str | float]]:
    return [
        {
            "date": record.trading_date.isoformat(),
            "open": float(record.open),
            "high": float(record.high),
            "low": float(record.low),
            "close": float(record.close),
            "volume": float(record.volume),
        }
        for record in records
    ]


def _company_payload(
    source: CompanyFrontendArtifacts,
    company: Company,
) -> tuple[dict[str, object], dict[str, object]]:
    evaluation = source.evaluation
    forecast = source.next_day_forecast
    selected_model = evaluation.principal_ranking.best_model
    forecast_by_model = {
        prediction.model: prediction for prediction in forecast.predictions
    }
    selected_prediction = forecast_by_model[selected_model]
    previous_close = float(source.records[-1].close)
    predicted_close = float(selected_prediction.predicted_close)
    peso_change = predicted_close - previous_close
    pct_change = peso_change / previous_close * 100.0
    model_metrics = {
        model.value: _metric_payload(evaluation, model)
        for model in EVALUATION_MODEL_IDS
    }
    window_dates = evaluation.backtest.target_dates[-BACKTEST_WINDOW:]
    window_actual = evaluation.backtest.actual_closes[-BACKTEST_WINDOW:]
    backtest_by_model = {
        MODEL_DISPLAY_LABELS[model]: [
            float(record.predicted_close)
            for record in evaluation.backtest.records_for(model)[-BACKTEST_WINDOW:]
        ]
        for model in EVALUATION_MODEL_IDS
    }
    next_close = {
        NEXT_CLOSE_KEYS[model]: float(forecast_by_model[model].predicted_close)
        for model in PRINCIPAL_MODEL_IDS
    }
    ohlcv = _ohlcv_payload(source.records)
    detail: dict[str, object] = {
        "symbol": company.symbol,
        "name": company.name,
        "sector": company.sector,
        "previousClose": previous_close,
        "predictedClose": predicted_close,
        "pesoChange": peso_change,
        "pctChange": pct_change,
        "direction": "bullish" if pct_change >= 0 else "bearish",
        "model": MODEL_DISPLAY_LABELS[selected_model],
        "metrics": model_metrics,
        "nextClose": next_close,
        "ohlcv": ohlcv,
        "backtestDates": [value.isoformat() for value in window_dates],
        "backtestActual": [float(value) for value in window_actual],
        "backtestByModel": backtest_by_model,
        "productionBacktestDates": [],
        "productionBacktestActual": [],
        "productionBacktestByModel": {
            MODEL_DISPLAY_LABELS[model]: [] for model in PRINCIPAL_MODEL_IDS
        },
        "forecastDate": forecast.forecast_for.isoformat(),
        "dataAsOf": source.records[-1].trading_date.isoformat(),
        "inferenceAt": as_manila_time(selected_prediction.inference_at).isoformat(),
        "backtestMethodology": {
            "source": "chronological_out_of_sample_evaluation",
            "alignment": "common_target_date",
            "window": BACKTEST_WINDOW,
        },
    }
    summary = {
        "symbol": company.symbol,
        "name": company.name,
        "sector": company.sector,
        "latestClose": previous_close,
        "predictedClose": predicted_close,
        "pctChange": pct_change,
        "direction": detail["direction"],
        "bestModel": detail["model"],
        "forecastDate": detail["forecastDate"],
    }
    return detail, summary


def build_frontend_payloads(bundle: FrontendExportBundle) -> dict[str, object]:
    """Build every operational JSON document without reading frontend output files."""

    if not bundle.status.strip():
        raise FrontendExportError("Export status cannot be blank")
    try:
        generated_at = as_manila_time(bundle.generated_at)
        last_run_at = as_manila_time(bundle.last_run_at)
    except ValueError as exc:
        raise FrontendExportError("Export timestamps must be timezone-aware") from exc
    if last_run_at > generated_at:
        raise FrontendExportError("last_run_at cannot follow generated_at")
    sources = tuple(bundle.companies)
    source_by_symbol = {source.symbol: source for source in sources}
    if len(source_by_symbol) != len(sources):
        raise FrontendExportError("Duplicate company export artifacts")
    expected_symbols = {company.symbol for company in COMPANIES}
    if set(source_by_symbol) != expected_symbols:
        missing = sorted(expected_symbols - set(source_by_symbol))
        extra = sorted(set(source_by_symbol) - expected_symbols)
        raise FrontendExportError(
            f"Configured company-set mismatch; missing={missing} extra={extra}"
        )

    payloads: dict[str, object] = {}
    summaries: list[dict[str, object]] = []
    details: dict[str, dict[str, object]] = {}
    histories: dict[str, dict[str, object]] = {}
    evaluations: dict[str, CompanyEvaluation] = {}
    forecast_dates: set[str] = set()
    for symbol in sorted(source_by_symbol):
        source = source_by_symbol[symbol]
        company = _validate_source(source)
        detail, summary = _company_payload(source, company)
        details[symbol] = detail
        summaries.append(summary)
        histories[symbol] = {"symbol": symbol, "ohlcv": detail["ohlcv"]}
        evaluations[symbol] = source.evaluation
        forecast_dates.add(detail["forecastDate"])
    if len(forecast_dates) != 1:
        raise FrontendExportError("All companies must share one frontend forecast date")
    forecast_date = next(iter(forecast_dates))

    sector_counts = Counter(summary["sector"] for summary in summaries)
    gainers = [summary for summary in summaries if summary["pctChange"] > 0]
    losers = [summary for summary in summaries if summary["pctChange"] < 0]
    unchanged = [summary for summary in summaries if summary["pctChange"] == 0]
    # Compatibility metrics are descriptive medians. They are never used to select
    # a cross-company winner because raw peso RMSE/MAE are not scale-comparable.
    aggregate = {
        MODEL_DISPLAY_LABELS[model]: {
            metric_name: float(
                statistics.median(
                    getattr(evaluations[symbol].metrics_for(model), metric_name)
                    for symbol in sorted(evaluations)
                )
            )
            for metric_name in ("rmse", "mae", "mase", "r2")
        }
        for model in EVALUATION_MODEL_IDS
    }
    cross_company = summarize_cross_company_metrics(
        {
            symbol: dict(evaluation.metrics_by_model)
            for symbol, evaluation in evaluations.items()
        }
    )
    cross_company_methods = {
        MODEL_DISPLAY_LABELS[method.model]: {
            "medianMase": method.median_mase,
            "medianRmseRank": method.median_rmse_rank,
            "principalWinCount": method.principal_win_count,
            "evaluatedWinCount": method.evaluated_win_count,
            "beatsNaiveCount": method.beats_naive_count,
        }
        for method in cross_company.methods
    }
    generated_text = generated_at.isoformat()
    last_run_text = last_run_at.isoformat()
    dashboard: dict[str, object] = {
        "generatedAt": generated_text,
        "forecastDate": forecast_date,
        "lastRunAt": last_run_text,
        "status": bundle.status,
        "totalCompanies": len(summaries),
        "missingCompanies": [],
        "sectors": [
            {"name": sector, "count": count}
            for sector, count in sorted(sector_counts.items())
        ],
        "marketSummary": {
            "gainers": len(gainers),
            "losers": len(losers),
            "unchanged": len(unchanged),
        },
        "topGainer": max(gainers, key=lambda item: item["pctChange"]) if gainers else None,
        "topLoser": min(losers, key=lambda item: item["pctChange"]) if losers else None,
    }
    latest = {
        "generatedAt": generated_text,
        "forecastDate": forecast_date,
        "lastRunAt": last_run_text,
        "status": bundle.status,
    }
    metrics = {
        "generatedAt": generated_text,
        "forecastDate": forecast_date,
        "lastRunAt": last_run_text,
        "status": bundle.status,
        "aggregate": aggregate,
        "aggregateStatistic": "median",
        "crossCompany": {
            "companyCount": cross_company.company_count,
            "selectionBasis": (
                "median_within_company_rmse_rank_then_median_mase_then_"
                "evaluated_win_count"
            ),
            "tiePolicy": cross_company.as_dict()["tie_policy"],
            "bestEvaluatedMethod": MODEL_DISPLAY_LABELS[cross_company.best_method],
            "worstEvaluatedMethod": MODEL_DISPLAY_LABELS[cross_company.worst_method],
            "methods": cross_company_methods,
        },
        # Retain compatibility names, now backed by scale-independent ordering.
        "bestModel": MODEL_DISPLAY_LABELS[cross_company.best_method],
        "worstModel": MODEL_DISPLAY_LABELS[cross_company.worst_method],
        "perCompany": {
            symbol: {
                "metrics": details[symbol]["metrics"],
                "bestModel": details[symbol]["model"],
                "bestPrincipalModel": details[symbol]["model"],
                "bestEvaluatedMethod": MODEL_DISPLAY_LABELS[
                    evaluations[symbol].evaluated_ranking.best_model
                ],
                "bestPrincipalBeatsNaive": evaluations[
                    symbol
                ].best_principal_beats_naive,
                "allPrincipalsWorseThanNaive": evaluations[
                    symbol
                ].all_principals_worse_than_naive,
            }
            for symbol in sorted(details)
        },
        "statisticalTests": {},
    }
    payloads["companies.json"] = summaries
    payloads["dashboard.json"] = dashboard
    payloads["latest.json"] = latest
    payloads["metrics.json"] = metrics
    for symbol in sorted(details):
        payloads[f"company/{symbol}.json"] = details[symbol]
        payloads[f"history/{symbol}.json"] = histories[symbol]
    _validate_payload_set(payloads)
    LOGGER.info(
        "Built frontend export payloads companies=%d files=%d forecast_date=%s",
        len(summaries),
        len(payloads),
        forecast_date,
    )
    return payloads


def _validate_payload_set(payloads: Mapping[str, object]) -> None:
    for relative_path, payload in payloads.items():
        validate_document(relative_path, payload)
    companies = payloads["companies.json"]
    symbols = [summary["symbol"] for summary in companies]
    dashboard = payloads["dashboard.json"]
    latest = payloads["latest.json"]
    metrics = payloads["metrics.json"]
    if set(symbols) != set(metrics["perCompany"]):
        raise FrontendSchemaError("Company and metrics symbol sets differ")
    if dashboard["totalCompanies"] != len(symbols):
        raise FrontendSchemaError("Dashboard company total is inconsistent")
    if not (
        dashboard["forecastDate"]
        == latest["forecastDate"]
        == metrics["forecastDate"]
    ):
        raise FrontendSchemaError("Top-level forecast dates differ")
    summary_by_symbol = {summary["symbol"]: summary for summary in companies}
    for symbol in symbols:
        detail = payloads[f"company/{symbol}.json"]
        history = payloads[f"history/{symbol}.json"]
        summary = summary_by_symbol[symbol]
        if history["ohlcv"] != detail["ohlcv"]:
            raise FrontendSchemaError(f"History and company OHLCV differ for {symbol}")
        if metrics["perCompany"][symbol]["metrics"] != detail["metrics"]:
            raise FrontendSchemaError(f"Metrics and company detail differ for {symbol}")
        if any(
            summary[field] != detail[detail_field]
            for field, detail_field in (
                ("symbol", "symbol"),
                ("name", "name"),
                ("sector", "sector"),
                ("latestClose", "previousClose"),
                ("predictedClose", "predictedClose"),
                ("pctChange", "pctChange"),
                ("direction", "direction"),
                ("bestModel", "model"),
                ("forecastDate", "forecastDate"),
            )
        ):
            raise FrontendSchemaError(f"Summary and company detail differ for {symbol}")


def _replace_staged_file(source: Path, destination: Path) -> None:
    os.replace(source, destination)


def _restore_file(destination: Path, previous: bytes | None) -> None:
    if previous is None:
        destination.unlink(missing_ok=True)
        return
    temporary = destination.with_name(f".{destination.name}.rollback.tmp")
    temporary.write_bytes(previous)
    os.replace(temporary, destination)


def _atomic_publish(payloads: Mapping[str, object], output_root: Path) -> tuple[Path, ...]:
    output_root = Path(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    ordered_paths = tuple(payloads)
    with tempfile.TemporaryDirectory(
        prefix=".forecast-export-",
        dir=output_root.parent,
    ) as staging_name:
        staging_root = Path(staging_name)
        for relative_path in ordered_paths:
            staged = staging_root / relative_path
            staged.parent.mkdir(parents=True, exist_ok=True)
            with staged.open("w", encoding="utf-8") as output:
                json.dump(
                    payloads[relative_path],
                    output,
                    indent=2,
                    ensure_ascii=False,
                    allow_nan=False,
                )
                output.write("\n")
            with staged.open("r", encoding="utf-8") as source:
                decoded = json.load(source)
            validate_document(relative_path, decoded)

        destinations = {
            relative_path: output_root / relative_path for relative_path in ordered_paths
        }
        previous_files: dict[str, bytes | None] = {}
        for relative_path, destination in destinations.items():
            if destination.exists() and not destination.is_file():
                raise FrontendExportError(f"Export destination is not a file: {destination}")
            previous_files[relative_path] = (
                destination.read_bytes() if destination.is_file() else None
            )
        replaced: list[str] = []
        try:
            for relative_path, destination in destinations.items():
                destination.parent.mkdir(parents=True, exist_ok=True)
                _replace_staged_file(staging_root / relative_path, destination)
                replaced.append(relative_path)
        except OSError as exc:
            rollback_errors: list[str] = []
            for relative_path in reversed(replaced):
                try:
                    _restore_file(
                        destinations[relative_path], previous_files[relative_path]
                    )
                except OSError as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            detail = f"; rollback errors={rollback_errors}" if rollback_errors else ""
            raise FrontendExportError(f"Atomic frontend export failed{detail}") from exc
    return tuple(destinations[path] for path in ordered_paths)


def export_frontend_forecasts(
    bundle: FrontendExportBundle,
    *,
    output_root: Path = FRONTEND_FORECASTS_DIR,
) -> FrontendExportResult:
    """Validate, stage, and atomically replace all operational frontend files."""

    payloads = build_frontend_payloads(bundle)
    files = _atomic_publish(payloads, output_root)
    LOGGER.info("Published frontend forecast files root=%s count=%d", output_root, len(files))
    return FrontendExportResult(output_root=Path(output_root), files=files)
