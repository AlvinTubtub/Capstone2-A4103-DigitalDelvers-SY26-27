"""Runtime schemas for the operational frontend forecast-data contract."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
import math
from pathlib import Path
from types import MappingProxyType
from typing import Final

from config.model_config import ModelId


BACKTEST_WINDOW: Final[int] = 60
MODEL_DISPLAY_LABELS: Final[Mapping[ModelId, str]] = MappingProxyType(
    {
        ModelId.LAG_REGRESSION: "Lag-Informed Regression",
        ModelId.ARIMA: "ARIMA",
        ModelId.LSTM: "LSTM",
        ModelId.NAIVE: "Naive baseline",
    }
)
NEXT_CLOSE_KEYS: Final[Mapping[ModelId, str]] = MappingProxyType(
    {
        ModelId.LAG_REGRESSION: "lag",
        ModelId.ARIMA: "arima",
        ModelId.LSTM: "lstm",
    }
)
PRINCIPAL_MODEL_IDS: Final[tuple[ModelId, ...]] = (
    ModelId.LAG_REGRESSION,
    ModelId.ARIMA,
    ModelId.LSTM,
)
EVALUATION_MODEL_IDS: Final[tuple[ModelId, ...]] = (
    *PRINCIPAL_MODEL_IDS,
    ModelId.NAIVE,
)


class FrontendSchemaError(ValueError):
    """Raised when a generated JSON document violates the frontend contract."""


def _object(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise FrontendSchemaError(f"{context} must be a JSON object")
    return value


def _array(value: object, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise FrontendSchemaError(f"{context} must be a JSON array")
    return value


def _required(payload: Mapping[str, object], keys: set[str], context: str) -> None:
    missing = sorted(keys - set(payload))
    if missing:
        raise FrontendSchemaError(f"{context} is missing fields: {missing}")


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise FrontendSchemaError(f"{context} must be a non-empty string")
    return value


def _number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FrontendSchemaError(f"{context} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise FrontendSchemaError(f"{context} must be finite")
    return result


def _integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FrontendSchemaError(f"{context} must be an integer")
    return value


def _boolean(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise FrontendSchemaError(f"{context} must be a boolean")
    return value


def _date_only(value: object, context: str) -> str:
    text = _string(value, context)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise FrontendSchemaError(f"{context} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise FrontendSchemaError(f"{context} must be YYYY-MM-DD")
    return text


def _timestamp(value: object, context: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    text = _string(value, context)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise FrontendSchemaError(f"{context} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FrontendSchemaError(f"{context} must include a timezone")
    return text


def validate_model_metric(value: object, context: str) -> None:
    metric = _object(value, context)
    _required(metric, {"rmse", "mae", "mase", "r2"}, context)
    allowed = {"rmse", "mae", "mase", "r2", "ljung_box_pvalue"}
    if set(metric) - allowed:
        raise FrontendSchemaError(f"{context} contains unsupported metric fields")
    for name, number in metric.items():
        _number(number, f"{context}.{name}")


def _validate_evaluation_metadata(
    value: object,
    context: str,
    *,
    displayed_dates: Sequence[str] | None = None,
) -> None:
    metadata = _object(value, context)
    required = {
        "fullSessionCount",
        "fullStartDate",
        "fullEndDate",
        "displayedSessionCount",
        "displayedStartDate",
        "displayedEndDate",
        "displayWindowLimit",
        "metricsScope",
        "statisticalTestsScope",
    }
    _required(metadata, required, context)
    if set(metadata) != required:
        raise FrontendSchemaError(f"{context} contains unsupported fields")
    full_count = _integer(metadata["fullSessionCount"], f"{context}.fullSessionCount")
    displayed_count = _integer(
        metadata["displayedSessionCount"], f"{context}.displayedSessionCount"
    )
    display_limit = _integer(
        metadata["displayWindowLimit"], f"{context}.displayWindowLimit"
    )
    if full_count < BACKTEST_WINDOW or displayed_count != BACKTEST_WINDOW:
        raise FrontendSchemaError(
            f"{context} must describe a full evaluation with a 60-session display subset"
        )
    if display_limit != BACKTEST_WINDOW or displayed_count > full_count:
        raise FrontendSchemaError(f"{context} contains invalid session counts")
    full_start = _date_only(metadata["fullStartDate"], f"{context}.fullStartDate")
    full_end = _date_only(metadata["fullEndDate"], f"{context}.fullEndDate")
    displayed_start = _date_only(
        metadata["displayedStartDate"], f"{context}.displayedStartDate"
    )
    displayed_end = _date_only(
        metadata["displayedEndDate"], f"{context}.displayedEndDate"
    )
    if not full_start <= displayed_start <= displayed_end or displayed_end != full_end:
        raise FrontendSchemaError(
            f"{context} display dates must be the latest subset of the full evaluation"
        )
    for field in ("metricsScope", "statisticalTestsScope"):
        if metadata[field] != "complete_aligned_evaluation":
            raise FrontendSchemaError(f"{context}.{field} has an invalid scope")
    if displayed_dates is not None and (
        len(displayed_dates) != displayed_count
        or displayed_dates[0] != displayed_start
        or displayed_dates[-1] != displayed_end
    ):
        raise FrontendSchemaError(
            f"{context} does not match the exported backtest display arrays"
        )


def validate_company_summary(value: object, context: str = "company summary") -> None:
    summary = _object(value, context)
    required = {
        "symbol",
        "name",
        "sector",
        "latestClose",
        "predictedClose",
        "pctChange",
        "direction",
        "bestModel",
        "forecastDate",
    }
    _required(summary, required, context)
    symbol = _string(summary["symbol"], f"{context}.symbol")
    if symbol != symbol.upper():
        raise FrontendSchemaError(f"{context}.symbol must be uppercase")
    _string(summary["name"], f"{context}.name")
    _string(summary["sector"], f"{context}.sector")
    for field in ("latestClose", "predictedClose", "pctChange"):
        _number(summary[field], f"{context}.{field}")
    if summary["direction"] not in {"bullish", "bearish"}:
        raise FrontendSchemaError(f"{context}.direction is invalid")
    expected_direction = "bullish" if _number(
        summary["pctChange"], f"{context}.pctChange"
    ) >= 0 else "bearish"
    if summary["direction"] != expected_direction:
        raise FrontendSchemaError(f"{context}.direction disagrees with pctChange")
    if summary["bestModel"] not in {
        MODEL_DISPLAY_LABELS[model] for model in PRINCIPAL_MODEL_IDS
    }:
        raise FrontendSchemaError(f"{context}.bestModel is invalid")
    _date_only(summary["forecastDate"], f"{context}.forecastDate")
    if "confidence" in summary:
        _number(summary["confidence"], f"{context}.confidence")


def validate_companies_json(value: object) -> None:
    companies = _array(value, "companies.json")
    if not companies:
        raise FrontendSchemaError("companies.json cannot be empty")
    for index, company in enumerate(companies):
        validate_company_summary(company, f"companies.json[{index}]")
    symbols = [company["symbol"] for company in companies]
    if len(set(symbols)) != len(symbols):
        raise FrontendSchemaError("companies.json symbols must be unique")


def validate_dashboard_json(value: object) -> None:
    dashboard = _object(value, "dashboard.json")
    _required(
        dashboard,
        {
            "generatedAt",
            "forecastDate",
            "lastRunAt",
            "status",
            "totalCompanies",
            "missingCompanies",
            "sectors",
            "marketSummary",
            "topGainer",
            "topLoser",
        },
        "dashboard.json",
    )
    _timestamp(dashboard["generatedAt"], "dashboard.generatedAt")
    _date_only(dashboard["forecastDate"], "dashboard.forecastDate")
    _timestamp(dashboard["lastRunAt"], "dashboard.lastRunAt", nullable=True)
    _string(dashboard["status"], "dashboard.status")
    total = _integer(dashboard["totalCompanies"], "dashboard.totalCompanies")
    if total < 0:
        raise FrontendSchemaError("dashboard.totalCompanies cannot be negative")
    missing = _array(dashboard["missingCompanies"], "dashboard.missingCompanies")
    if any(not isinstance(symbol, str) for symbol in missing):
        raise FrontendSchemaError("dashboard.missingCompanies must contain strings")
    sectors = _array(dashboard["sectors"], "dashboard.sectors")
    sector_total = 0
    for index, item in enumerate(sectors):
        sector = _object(item, f"dashboard.sectors[{index}]")
        _required(sector, {"name", "count"}, f"dashboard.sectors[{index}]")
        _string(sector["name"], f"dashboard.sectors[{index}].name")
        count = _integer(sector["count"], f"dashboard.sectors[{index}].count")
        if count < 1:
            raise FrontendSchemaError("dashboard sector counts must be positive")
        sector_total += count
    if sector_total != total:
        raise FrontendSchemaError("dashboard sector counts must equal totalCompanies")
    market = _object(dashboard["marketSummary"], "dashboard.marketSummary")
    _required(market, {"gainers", "losers", "unchanged"}, "dashboard.marketSummary")
    counts = [
        _integer(market[field], f"dashboard.marketSummary.{field}")
        for field in ("gainers", "losers", "unchanged")
    ]
    if any(count < 0 for count in counts) or sum(counts) != total:
        raise FrontendSchemaError("dashboard market counts must be non-negative and total")
    for field in ("topGainer", "topLoser"):
        if dashboard[field] is not None:
            validate_company_summary(dashboard[field], f"dashboard.{field}")
    if (counts[0] > 0) != (dashboard["topGainer"] is not None):
        raise FrontendSchemaError("dashboard.topGainer disagrees with gainer count")
    if (counts[1] > 0) != (dashboard["topLoser"] is not None):
        raise FrontendSchemaError("dashboard.topLoser disagrees with loser count")


def validate_latest_json(value: object) -> None:
    latest = _object(value, "latest.json")
    _required(latest, {"generatedAt", "forecastDate", "lastRunAt", "status"}, "latest.json")
    _timestamp(latest["generatedAt"], "latest.generatedAt")
    _date_only(latest["forecastDate"], "latest.forecastDate")
    _timestamp(latest["lastRunAt"], "latest.lastRunAt", nullable=True)
    _string(latest["status"], "latest.status")


def _validate_metrics_map(value: object, context: str) -> None:
    metrics = _object(value, context)
    expected = {model.value for model in EVALUATION_MODEL_IDS}
    if set(metrics) != expected:
        raise FrontendSchemaError(f"{context} must contain exactly {sorted(expected)}")
    for model, metric in metrics.items():
        validate_model_metric(metric, f"{context}.{model}")


def validate_metrics_json(value: object) -> None:
    document = _object(value, "metrics.json")
    _required(
        document,
        {
            "generatedAt",
            "forecastDate",
            "lastRunAt",
            "status",
            "aggregate",
            "bestModel",
            "worstModel",
            "perCompany",
            "statisticalTests",
        },
        "metrics.json",
    )
    _timestamp(document["generatedAt"], "metrics.generatedAt")
    _date_only(document["forecastDate"], "metrics.forecastDate")
    _timestamp(document["lastRunAt"], "metrics.lastRunAt", nullable=True)
    _string(document["status"], "metrics.status")
    aggregate = _object(document["aggregate"], "metrics.aggregate")
    expected_labels = {MODEL_DISPLAY_LABELS[model] for model in EVALUATION_MODEL_IDS}
    if set(aggregate) != expected_labels:
        raise FrontendSchemaError("metrics.aggregate has an invalid model set")
    for label, metric in aggregate.items():
        validate_model_metric(metric, f"metrics.aggregate.{label}")
    for field in ("bestModel", "worstModel"):
        if document[field] not in expected_labels:
            raise FrontendSchemaError(f"metrics.{field} is invalid")
    if "aggregateStatistic" in document and document["aggregateStatistic"] != "median":
        raise FrontendSchemaError("metrics.aggregateStatistic must be median")
    if "crossCompany" in document:
        cross_company = _object(document["crossCompany"], "metrics.crossCompany")
        _required(
            cross_company,
            {
                "companyCount",
                "selectionBasis",
                "tiePolicy",
                "bestEvaluatedMethod",
                "worstEvaluatedMethod",
                "methods",
            },
            "metrics.crossCompany",
        )
        company_count = _integer(
            cross_company["companyCount"], "metrics.crossCompany.companyCount"
        )
        if company_count < 1:
            raise FrontendSchemaError("metrics.crossCompany.companyCount must be positive")
        _string(cross_company["selectionBasis"], "metrics.crossCompany.selectionBasis")
        _string(cross_company["tiePolicy"], "metrics.crossCompany.tiePolicy")
        for field in ("bestEvaluatedMethod", "worstEvaluatedMethod"):
            if cross_company[field] not in expected_labels:
                raise FrontendSchemaError(f"metrics.crossCompany.{field} is invalid")
        methods = _object(cross_company["methods"], "metrics.crossCompany.methods")
        if set(methods) != expected_labels:
            raise FrontendSchemaError(
                "metrics.crossCompany.methods has an invalid model set"
            )
        for label, value in methods.items():
            method = _object(value, f"metrics.crossCompany.methods.{label}")
            _required(
                method,
                {
                    "medianMase",
                    "medianRmseRank",
                    "principalWinCount",
                    "evaluatedWinCount",
                    "beatsNaiveCount",
                },
                f"metrics.crossCompany.methods.{label}",
            )
            _number(method["medianMase"], f"metrics.crossCompany.methods.{label}.medianMase")
            median_rank = _number(
                method["medianRmseRank"],
                f"metrics.crossCompany.methods.{label}.medianRmseRank",
            )
            if not 1.0 <= median_rank <= len(EVALUATION_MODEL_IDS):
                raise FrontendSchemaError(
                    f"metrics.crossCompany.methods.{label}.medianRmseRank is invalid"
                )
            for field in (
                "principalWinCount",
                "evaluatedWinCount",
                "beatsNaiveCount",
            ):
                count = _integer(
                    method[field],
                    f"metrics.crossCompany.methods.{label}.{field}",
                )
                if count < 0:
                    raise FrontendSchemaError(
                        f"metrics.crossCompany.methods.{label}.{field} cannot be negative"
                    )
                if count > company_count:
                    raise FrontendSchemaError(
                        f"metrics.crossCompany.methods.{label}.{field} exceeds companyCount"
                    )
    per_company = _object(document["perCompany"], "metrics.perCompany")
    if not per_company:
        raise FrontendSchemaError("metrics.perCompany cannot be empty")
    for symbol, value in per_company.items():
        if not isinstance(symbol, str) or symbol != symbol.upper():
            raise FrontendSchemaError("metrics.perCompany keys must be uppercase symbols")
        company = _object(value, f"metrics.perCompany.{symbol}")
        _required(company, {"metrics", "bestModel"}, f"metrics.perCompany.{symbol}")
        _validate_metrics_map(company["metrics"], f"metrics.perCompany.{symbol}.metrics")
        if company["bestModel"] not in {
            MODEL_DISPLAY_LABELS[model] for model in PRINCIPAL_MODEL_IDS
        }:
            raise FrontendSchemaError(f"metrics.perCompany.{symbol}.bestModel is invalid")
        if "bestPrincipalModel" in company and company["bestPrincipalModel"] not in {
            MODEL_DISPLAY_LABELS[model] for model in PRINCIPAL_MODEL_IDS
        }:
            raise FrontendSchemaError(
                f"metrics.perCompany.{symbol}.bestPrincipalModel is invalid"
            )
        if "bestEvaluatedMethod" in company and company["bestEvaluatedMethod"] not in expected_labels:
            raise FrontendSchemaError(
                f"metrics.perCompany.{symbol}.bestEvaluatedMethod is invalid"
            )
        for field in (
            "bestPrincipalBeatsNaive",
            "allPrincipalsWorseThanNaive",
        ):
            if field in company:
                _boolean(company[field], f"metrics.perCompany.{symbol}.{field}")
        if "evaluationMetadata" in company:
            _validate_evaluation_metadata(
                company["evaluationMetadata"],
                f"metrics.perCompany.{symbol}.evaluationMetadata",
            )
        if "statisticalTests" in company:
            tests = _object(
                company["statisticalTests"],
                f"metrics.perCompany.{symbol}.statisticalTests",
            )
            _required(
                tests,
                {"diebold_mariano"},
                f"metrics.perCompany.{symbol}.statisticalTests",
            )
            dm = _object(
                tests["diebold_mariano"],
                f"metrics.perCompany.{symbol}.statisticalTests.diebold_mariano",
            )
            _required(
                dm,
                {"company", "scope", "holm_families"},
                f"metrics.perCompany.{symbol}.statisticalTests.diebold_mariano",
            )
            if dm["company"] != symbol or dm["scope"] != "complete_aligned_evaluation":
                raise FrontendSchemaError(
                    f"metrics.perCompany.{symbol} DM identity or scope is invalid"
                )
            families = _object(
                dm["holm_families"],
                f"metrics.perCompany.{symbol}.DM.holm_families",
            )
            if set(families) != {"squared_error", "absolute_error"}:
                raise FrontendSchemaError(
                    f"metrics.perCompany.{symbol} DM families are invalid"
                )
            if any(
                len(_array(family, f"metrics.perCompany.{symbol}.DM family")) != 6
                for family in families.values()
            ):
                raise FrontendSchemaError(
                    f"metrics.perCompany.{symbol} DM families must contain six tests"
                )
    statistical_tests = _object(document["statisticalTests"], "metrics.statisticalTests")
    if statistical_tests:
        _required(
            statistical_tests,
            {"schema_id", "schema_version", "scope", "across_company"},
            "metrics.statisticalTests",
        )
        if (
            statistical_tests["schema_id"] != "forecastph.evaluation-statistics"
            or _integer(
                statistical_tests["schema_version"],
                "metrics.statisticalTests.schema_version",
            )
            != 1
            or statistical_tests["scope"] != "complete_aligned_evaluation"
        ):
            raise FrontendSchemaError("metrics.statisticalTests metadata is invalid")
        across_company = _object(
            statistical_tests["across_company"],
            "metrics.statisticalTests.across_company",
        )
        _required(
            across_company,
            {"metric", "friedman", "posthoc_performed", "pairwise_wilcoxon"},
            "metrics.statisticalTests.across_company",
        )
        if across_company["metric"] != "mase":
            raise FrontendSchemaError("Across-company statistics must use MASE")
        _boolean(
            across_company["posthoc_performed"],
            "metrics.statisticalTests.across_company.posthoc_performed",
        )


def validate_ohlcv(value: object, context: str) -> None:
    rows = _array(value, context)
    if not rows:
        raise FrontendSchemaError(f"{context} cannot be empty")
    dates: list[str] = []
    for index, item in enumerate(rows):
        row = _object(item, f"{context}[{index}]")
        _required(row, {"date", "open", "high", "low", "close", "volume"}, context)
        dates.append(_date_only(row["date"], f"{context}[{index}].date"))
        for field in ("open", "high", "low", "close", "volume"):
            _number(row[field], f"{context}[{index}].{field}")
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise FrontendSchemaError(f"{context} dates must be unique and ascending")


def validate_company_json(value: object) -> None:
    company = _object(value, "company JSON")
    required = {
        "symbol",
        "name",
        "sector",
        "previousClose",
        "predictedClose",
        "pesoChange",
        "pctChange",
        "direction",
        "model",
        "metrics",
        "nextClose",
        "ohlcv",
        "backtestDates",
        "backtestActual",
        "backtestByModel",
        "productionBacktestDates",
        "productionBacktestActual",
        "productionBacktestByModel",
        "forecastDate",
        "dataAsOf",
        "inferenceAt",
        "backtestMethodology",
    }
    _required(company, required, "company JSON")
    symbol = _string(company["symbol"], "company.symbol")
    if symbol != symbol.upper():
        raise FrontendSchemaError("company.symbol must be uppercase")
    _string(company["name"], "company.name")
    _string(company["sector"], "company.sector")
    for field in ("previousClose", "predictedClose", "pesoChange", "pctChange"):
        _number(company[field], f"company.{field}")
    if company["direction"] not in {"bullish", "bearish"}:
        raise FrontendSchemaError("company.direction is invalid")
    if company["model"] not in {
        MODEL_DISPLAY_LABELS[model] for model in PRINCIPAL_MODEL_IDS
    }:
        raise FrontendSchemaError("company.model is invalid")
    _validate_metrics_map(company["metrics"], "company.metrics")
    next_close = _object(company["nextClose"], "company.nextClose")
    if set(next_close) != set(NEXT_CLOSE_KEYS.values()):
        raise FrontendSchemaError("company.nextClose must contain lag, arima, and lstm")
    for key, prediction in next_close.items():
        _number(prediction, f"company.nextClose.{key}")
    validate_ohlcv(company["ohlcv"], "company.ohlcv")
    dates = _array(company["backtestDates"], "company.backtestDates")
    actual = _array(company["backtestActual"], "company.backtestActual")
    if len(dates) != BACKTEST_WINDOW or len(actual) != BACKTEST_WINDOW:
        raise FrontendSchemaError("company backtest arrays must contain exactly 60 sessions")
    validated_dates = [
        _date_only(value, f"company.backtestDates[{index}]")
        for index, value in enumerate(dates)
    ]
    if validated_dates != sorted(validated_dates) or len(set(validated_dates)) != len(validated_dates):
        raise FrontendSchemaError("company.backtestDates must be unique and ascending")
    for index, number in enumerate(actual):
        _number(number, f"company.backtestActual[{index}]")
    backtest = _object(company["backtestByModel"], "company.backtestByModel")
    expected_labels = {MODEL_DISPLAY_LABELS[model] for model in EVALUATION_MODEL_IDS}
    if set(backtest) != expected_labels:
        raise FrontendSchemaError("company.backtestByModel has an invalid model set")
    for label, values in backtest.items():
        series = _array(values, f"company.backtestByModel.{label}")
        if len(series) != BACKTEST_WINDOW:
            raise FrontendSchemaError("Every company backtest series must contain 60 values")
        for index, number in enumerate(series):
            _number(number, f"company.backtestByModel.{label}[{index}]")
    production_dates = _array(
        company["productionBacktestDates"], "company.productionBacktestDates"
    )
    production_actual = _array(
        company["productionBacktestActual"], "company.productionBacktestActual"
    )
    production = _object(
        company["productionBacktestByModel"], "company.productionBacktestByModel"
    )
    principal_labels = {MODEL_DISPLAY_LABELS[model] for model in PRINCIPAL_MODEL_IDS}
    if set(production) != principal_labels:
        raise FrontendSchemaError("Production backtest must contain the three principal models")
    if len(production_dates) != len(production_actual) or any(
        len(_array(series, f"company.productionBacktestByModel.{label}"))
        != len(production_dates)
        for label, series in production.items()
    ):
        raise FrontendSchemaError("Production backtest arrays must be aligned")
    validated_production_dates = [
        _date_only(value, f"company.productionBacktestDates[{index}]")
        for index, value in enumerate(production_dates)
    ]
    if validated_production_dates != sorted(validated_production_dates) or len(
        set(validated_production_dates)
    ) != len(validated_production_dates):
        raise FrontendSchemaError("Production backtest dates must be unique and ascending")
    for index, number in enumerate(production_actual):
        _number(number, f"company.productionBacktestActual[{index}]")
    for label, values in production.items():
        for index, number in enumerate(values):
            _number(number, f"company.productionBacktestByModel.{label}[{index}]")
    forecast_date = _date_only(company["forecastDate"], "company.forecastDate")
    data_as_of = _date_only(company["dataAsOf"], "company.dataAsOf")
    if forecast_date <= data_as_of:
        raise FrontendSchemaError("company.forecastDate must follow dataAsOf")
    _timestamp(company["inferenceAt"], "company.inferenceAt")
    methodology = _object(company["backtestMethodology"], "company.backtestMethodology")
    _required(methodology, {"source", "alignment", "window"}, "company.backtestMethodology")
    _string(methodology["source"], "company.backtestMethodology.source")
    _string(methodology["alignment"], "company.backtestMethodology.alignment")
    if _integer(methodology["window"], "company.backtestMethodology.window") != BACKTEST_WINDOW:
        raise FrontendSchemaError("company.backtestMethodology.window must be 60")
    if "evaluationMetadata" in company:
        _validate_evaluation_metadata(
            company["evaluationMetadata"],
            "company.evaluationMetadata",
            displayed_dates=validated_dates,
        )
    principal_labels = {MODEL_DISPLAY_LABELS[model] for model in PRINCIPAL_MODEL_IDS}
    if "bestPrincipalModel" in company and company["bestPrincipalModel"] not in principal_labels:
        raise FrontendSchemaError("company.bestPrincipalModel is invalid")
    if "bestEvaluatedMethod" in company and company["bestEvaluatedMethod"] not in expected_labels:
        raise FrontendSchemaError("company.bestEvaluatedMethod is invalid")
    for field in ("bestPrincipalBeatsNaive", "allPrincipalsWorseThanNaive"):
        if field in company:
            _boolean(company[field], f"company.{field}")
    ohlcv = company["ohlcv"]
    latest_ohlcv = ohlcv[-1]
    if data_as_of != latest_ohlcv["date"]:
        raise FrontendSchemaError("company.dataAsOf must match the latest OHLCV date")
    previous = _number(company["previousClose"], "company.previousClose")
    if previous == 0.0:
        raise FrontendSchemaError("company.previousClose cannot be zero")
    if previous != _number(latest_ohlcv["close"], "company.ohlcv[-1].close"):
        raise FrontendSchemaError("company.previousClose must match the latest OHLCV Close")
    expected_prediction_key = {
        MODEL_DISPLAY_LABELS[model]: NEXT_CLOSE_KEYS[model]
        for model in PRINCIPAL_MODEL_IDS
    }[company["model"]]
    predicted = _number(company["predictedClose"], "company.predictedClose")
    if predicted != _number(next_close[expected_prediction_key], "selected nextClose"):
        raise FrontendSchemaError("company.predictedClose must match the selected model")
    if not math.isclose(
        _number(company["pesoChange"], "company.pesoChange"),
        predicted - previous,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise FrontendSchemaError("company.pesoChange is inconsistent")
    expected_pct_change = (predicted - previous) / previous * 100.0
    if not math.isclose(
        _number(company["pctChange"], "company.pctChange"),
        expected_pct_change,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise FrontendSchemaError("company.pctChange is inconsistent")


def validate_history_json(value: object) -> None:
    history = _object(value, "history JSON")
    _required(history, {"symbol", "ohlcv"}, "history JSON")
    symbol = _string(history["symbol"], "history.symbol")
    if symbol != symbol.upper():
        raise FrontendSchemaError("history.symbol must be uppercase")
    validate_ohlcv(history["ohlcv"], "history.ohlcv")


def validate_document(relative_path: str, value: object) -> None:
    """Validate one generated operational file based on its contract path."""

    if relative_path == "companies.json":
        validate_companies_json(value)
    elif relative_path == "dashboard.json":
        validate_dashboard_json(value)
    elif relative_path == "latest.json":
        validate_latest_json(value)
    elif relative_path == "metrics.json":
        validate_metrics_json(value)
    elif relative_path.startswith("company/") and relative_path.endswith(".json"):
        validate_company_json(value)
        expected_symbol = Path(relative_path).stem
        if value["symbol"] != expected_symbol or expected_symbol != expected_symbol.upper():
            raise FrontendSchemaError("Company filename must match its uppercase symbol")
    elif relative_path.startswith("history/") and relative_path.endswith(".json"):
        validate_history_json(value)
        expected_symbol = Path(relative_path).stem
        if value["symbol"] != expected_symbol or expected_symbol != expected_symbol.upper():
            raise FrontendSchemaError("History filename must match its uppercase symbol")
    else:
        raise FrontendSchemaError(f"Unsupported frontend forecast path: {relative_path}")
