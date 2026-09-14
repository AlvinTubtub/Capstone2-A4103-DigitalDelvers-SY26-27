import { getCompanyDetail, getCompanies, getDashboard, getLatest, getMetrics } from "@/lib/data";
import { formatDate, formatDateTimePht, formatNum, formatPct, formatPeso } from "@/lib/format";
import type { CompanyDetail, CompanySummary, ModelMetric } from "@/lib/types";

export interface ContextOptions {
  route?: string;
  symbol?: string;
  watchlist?: string[];
}

const PRINCIPAL_MODEL_IDS = ["lag_reg", "arima", "lstm"] as const;
const MODEL_IDS = [...PRINCIPAL_MODEL_IDS, "naive"] as const;
type ModelId = (typeof MODEL_IDS)[number];

const MODEL_NAMES: Record<ModelId, string> = {
  lag_reg: "Lag-Informed Regression",
  arima: "ARIMA",
  lstm: "LSTM",
  naive: "Naive benchmark",
};

const NEXT_CLOSE_IDS: Record<string, (typeof PRINCIPAL_MODEL_IDS)[number]> = {
  lag: "lag_reg",
  arima: "arima",
  lstm: "lstm",
};

function asContext(page: string, facts: Record<string, unknown>): string {
  return JSON.stringify({ page, source: "current ForecastPH operational data", facts }, null, 2);
}

function finiteNumber(value: string | number | undefined): number | null {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function metricFacts(metrics: Record<string, ModelMetric> | undefined) {
  return Object.fromEntries(
    MODEL_IDS.flatMap((id) => {
      const metric = metrics?.[id];
      if (!metric) return [];
      return [[MODEL_NAMES[id], {
        rmsePhp: formatNum(metric.rmse, 4),
        maePhp: formatNum(metric.mae, 4),
        mase: formatNum(metric.mase, 4),
        r2: formatNum(metric.r2, 4),
      }]];
    }),
  );
}

function companySummary(company: CompanySummary) {
  return {
    ticker: company.symbol,
    companyName: company.name,
    sector: company.sector,
    latestClose: formatPeso(company.latestClose),
    predictedClose: formatPeso(company.predictedClose),
    expectedChange: formatPct(company.pctChange),
    selectedPrincipalModel: company.bestModel,
    forecastTargetDate: company.forecastDate ? formatDate(company.forecastDate) : "unavailable",
  };
}

function predictionFacts(company: CompanyDetail) {
  return Object.fromEntries(
    Object.entries(company.nextClose ?? {}).flatMap(([id, value]) => {
      const modelId = NEXT_CLOSE_IDS[id];
      return modelId && Number.isFinite(Number(value))
        ? [[MODEL_NAMES[modelId], formatPeso(value)]]
        : [];
    }),
  );
}

function selectedMetric(company: CompanyDetail): ModelMetric | undefined {
  const selectedId = MODEL_IDS.find((id) => MODEL_NAMES[id] === company.model);
  return selectedId ? company.metrics[selectedId] : undefined;
}

function modelPredictionSpread(company: CompanyDetail) {
  const values = Object.entries(company.nextClose ?? {})
    .filter(([id]) => Boolean(NEXT_CLOSE_IDS[id]))
    .map(([, value]) => Number(value))
    .filter(Number.isFinite);
  if (values.length !== PRINCIPAL_MODEL_IDS.length) return null;
  const spread = Math.max(...values) - Math.min(...values);
  return {
    amount: formatPeso(spread),
    percentageOfLatestClose: company.previousClose > 0
      ? formatPct((spread / company.previousClose) * 100)
      : "unavailable",
    definition: "Maximum principal-model forecast minus minimum principal-model forecast; not a confidence interval.",
  };
}

function visibleBacktestFacts(company: CompanyDetail) {
  const dates = company.backtestDates ?? [];
  const actual = company.backtestActual ?? [];
  const predicted = company.backtestByModel?.[company.model] ?? [];
  const usable = Math.min(dates.length, actual.length, predicted.length);
  const errors = Array.from({ length: usable }, (_, index) => predicted[index] - actual[index])
    .filter(Number.isFinite);
  const meanAbsoluteError = errors.length
    ? errors.reduce((sum, error) => sum + Math.abs(error), 0) / errors.length
    : null;
  const rootMeanSquaredError = errors.length
    ? Math.sqrt(errors.reduce((sum, error) => sum + error ** 2, 0) / errors.length)
    : null;
  return {
    source: "Chronological out-of-sample predicted-versus-actual observations exported by ForecastPH.",
    selectedModel: company.model,
    sessions: usable,
    firstTargetDate: dates[0] ? formatDate(dates[0]) : "unavailable",
    lastTargetDate: usable ? formatDate(dates[usable - 1]) : "unavailable",
    visibleWindowMae: meanAbsoluteError === null ? "unavailable" : formatPeso(meanAbsoluteError),
    visibleWindowRmse: rootMeanSquaredError === null ? "unavailable" : formatPeso(rootMeanSquaredError),
    latestObservation: usable ? {
      targetDate: formatDate(dates[usable - 1]),
      actualClose: formatPeso(actual[usable - 1]),
      predictedClose: formatPeso(predicted[usable - 1]),
      errorPredictedMinusActual: formatPeso(predicted[usable - 1] - actual[usable - 1]),
    } : "unavailable",
    chartMeaning: "Backtest compares one-step-ahead predicted closes with actual closes on unseen evaluation dates.",
    errorChartMeaning: "Forecast Error Over Time plots predicted close minus actual close for those same out-of-sample dates.",
  };
}

export async function buildCompanyContext(symbol: string): Promise<string> {
  const cleanSymbol = symbol.toUpperCase().trim();
  const company = await getCompanyDetail(cleanSymbol);
  if (!company) {
    const companies = await getCompanies();
    return asContext("company", {
      requestedTicker: cleanSymbol,
      status: "That company is not available in the current ForecastPH data.",
      trackedTickers: companies.map(({ symbol: ticker }) => ticker),
    });
  }

  const chosenMetric = selectedMetric(company);
  return asContext("company", {
    company: { ticker: company.symbol, name: company.name, sector: company.sector },
    currentForecast: {
      latestObservedClose: formatPeso(company.previousClose),
      projectedNextClose: formatPeso(company.predictedClose),
      projectedPesoChange: formatPeso(company.pesoChange),
      projectedPercentageChange: formatPct(company.pctChange),
      directionLabel: company.direction,
      selectedPrincipalModel: company.model,
      selectionRule: "Lowest RMSE among the three principal models on the common chronological out-of-sample evaluation.",
      principalModelPredictions: predictionFacts(company),
      modelPredictionSpread: modelPredictionSpread(company),
    },
    dates: {
      marketDataThrough: company.dataAsOf ? formatDate(company.dataAsOf) : "unavailable",
      forecastTargetDate: company.forecastDate ? formatDate(company.forecastDate) : "unavailable",
      inferenceGeneratedAtPht: company.inferenceAt ? formatDateTimePht(company.inferenceAt) : "unavailable",
    },
    evaluation: {
      metricsByModel: metricFacts(company.metrics),
      selectedModelMetrics: chosenMetric
        ? {
            rmsePhp: formatNum(chosenMetric.rmse, 4),
            maePhp: formatNum(chosenMetric.mae, 4),
            mase: formatNum(chosenMetric.mase, 4),
            r2: formatNum(chosenMetric.r2, 4),
          }
        : "unavailable",
      visibleBacktestWindow: visibleBacktestFacts(company),
    },
    limitations: [
      "Forecasts are model estimates, not guarantees or trading recommendations.",
      "The operational data contains price/volume history and model outputs, not news, sentiment, fundamentals, or causal explanations.",
    ],
  });
}

export async function buildHomeContext(): Promise<string> {
  const [dashboard, companies, latest] = await Promise.all([getDashboard(), getCompanies(), getLatest()]);
  return asContext("home", {
    project: "ForecastPH is an educational next-session PSE closing-price forecasting and model-comparison project.",
    trackedCompanyCount: companies.length,
    marketDataThrough: "Not present in home summary data; use a company page for its symbol-specific dataAsOf date.",
    forecastTargetDate: latest?.forecastDate ? formatDate(latest.forecastDate) : "unavailable",
    generatedAtPht: latest?.generatedAt ? formatDateTimePht(latest.generatedAt) : "unavailable",
    marketSnapshot: dashboard ? {
      forecastedIncreases: dashboard.marketSummary.gainers,
      forecastedDecreases: dashboard.marketSummary.losers,
      unchanged: dashboard.marketSummary.unchanged,
      strongestForecastedIncrease: dashboard.topGainer ? companySummary(dashboard.topGainer) : "unavailable",
      strongestForecastedDecrease: dashboard.topLoser ? companySummary(dashboard.topLoser) : "unavailable",
    } : "unavailable",
    models: ["Lag-Informed Regression", "ARIMA", "LSTM"],
    benchmark: "Naive benchmark (previous observed close as the next-close prediction)",
    limitations: "Estimates reflect implemented historical-data patterns and may not capture unexpected events; they are not investment advice.",
  });
}

export async function buildCompaniesContext(): Promise<string> {
  const companies = await getCompanies();
  return asContext("companies", {
    trackedCompanyCount: companies.length,
    companies: companies.map(companySummary),
    comparisonNote: "Expected change is projected close versus latest observed close; it is not a buy/sell signal.",
  });
}

export async function buildWatchlistContext(watchlist?: string[]): Promise<string> {
  const requested = [...new Set((Array.isArray(watchlist) ? watchlist : [])
    .filter((symbol): symbol is string => typeof symbol === "string")
    .map((symbol) => symbol.toUpperCase().trim()).filter(Boolean))].slice(0, 5);
  const companies = await getCompanies();
  const selected = companies.filter((company) => requested.includes(company.symbol));
  if (!selected.length) {
    return asContext("watchlist", {
      storage: "Browser-only, maximum five companies.",
      pinnedCompanyCount: 0,
      status: "No valid pinned companies were supplied by the current browser watchlist.",
    });
  }

  const details = (await Promise.all(selected.map(({ symbol }) => getCompanyDetail(symbol))))
    .filter((detail): detail is CompanyDetail => Boolean(detail));
  const detailBySymbol = new Map(details.map((detail) => [detail.symbol, detail]));
  const rows = selected.map((company) => {
    const detail = detailBySymbol.get(company.symbol);
    const metric = detail ? selectedMetric(detail) : undefined;
    return {
      ...companySummary(company),
      selectedModelRmsePhp: metric ? formatNum(metric.rmse, 4) : "unavailable",
      modelPredictionSpread: detail ? modelPredictionSpread(detail) : null,
    };
  });
  const byChange = [...selected].sort((a, b) => a.pctChange - b.pctChange);
  const rowRmse = (row: (typeof rows)[number]) => {
    const detail = detailBySymbol.get(row.ticker);
    return finiteNumber(detail ? selectedMetric(detail)?.rmse : undefined) ?? Infinity;
  };
  const rmseRows = rows.filter((row) => rowRmse(row) !== Infinity);
  const spreadValue = (row: (typeof rows)[number]) => {
    const values = Object.entries(detailBySymbol.get(row.ticker)?.nextClose ?? {})
      .filter(([id]) => Boolean(NEXT_CLOSE_IDS[id])).map(([, value]) => Number(value));
    return values.length === 3 ? Math.max(...values) - Math.min(...values) : -Infinity;
  };
  const spreadRows = rows.filter((row) => spreadValue(row) !== -Infinity);

  return asContext("watchlist", {
    storage: "Browser-only, maximum five companies.",
    pinnedCompanyCount: rows.length,
    pinnedTickers: rows.map(({ ticker }) => ticker),
    companies: rows,
    strongestForecastedIncrease: companySummary(byChange[byChange.length - 1]),
    strongestForecastedDecline: byChange[0].pctChange < 0
      ? companySummary(byChange[0])
      : "No pinned company has a negative expected change.",
    lowestSelectedModelRmse: rmseRows.length
      ? [...rmseRows].sort((a, b) => rowRmse(a) - rowRmse(b))[0]
      : "unavailable",
    largestModelPredictionSpread: spreadRows.length
      ? [...spreadRows].sort((a, b) => spreadValue(b) - spreadValue(a))[0]
      : "unavailable",
    spreadDefinition: "Maximum principal-model prediction minus minimum principal-model prediction; not a confidence interval.",
  });
}

export function buildLearnStocksContext(): string {
  return asContext("learn-stocks", {
    mode: "Beginner educational tutor for stocks, tickers, the PSE, OHLCV, closing price, forecasts, backtesting, metrics, the Naive benchmark, and model disagreement.",
    modelNames: ["Lag-Informed Regression", "ARIMA", "LSTM"],
    benchmark: "Naive benchmark uses the previous observed close as the next-close prediction.",
    metricGuide: {
      RMSE: "Lower is better; measured in pesos and penalizes larger errors more strongly.",
      MAE: "Lower is better; average absolute forecast error in pesos.",
      MASE: "Lower is better; evaluation MAE divided by the common one-step scale from development Close. Below 1 is below that scale, but does not by itself prove lower held-out error than the evaluated Naive method.",
      R2: "Higher is generally better; negative values can occur when predictions are worse than a constant-mean reference on the evaluated sample. It is not percentage accuracy.",
    },
    boundaries: "Explain concepts, not personalized investment decisions. Current schedules and broker details should be verified with official sources.",
  });
}

export function buildAboutContext(): string {
  return asContext("about", {
    objective: "Educational next-session closing-price forecasting for 15 PSE companies across five sectors.",
    models: ["Lag-Informed Regression", "ARIMA", "LSTM"],
    benchmark: "Naive benchmark only; not a production principal model.",
    lifecycle: ["Chronological development and out-of-sample evaluation", "Company-level principal-model selection by lowest evaluation RMSE", "Fresh production refit of all three principal models", "Persisted-model next-session inference", "Frontend JSON export separated from the Python forecasting backend"],
    data: "Validated official PSE end-of-day OHLCV history used by the implemented models.",
    limitations: ["Historical patterns do not guarantee future prices.", "Unexpected news and events may not be captured.", "Performance varies by company.", "Educational and research use only; not investment advice."],
  });
}

export async function buildCompareContext(): Promise<string> {
  const [metrics, companies, latest] = await Promise.all([getMetrics(), getCompanies(), getLatest()]);
  if (!metrics || !companies.length) return asContext("compare", { status: "Current operational model-evaluation data is unavailable." });

  const wins = Object.fromEntries(PRINCIPAL_MODEL_IDS.map((id) => [MODEL_NAMES[id], 0])) as Record<string, number>;
  const bestByCompany = companies.map((company) => {
    const rows = PRINCIPAL_MODEL_IDS.map((id) => ({ id, rmse: finiteNumber(metrics.perCompany[company.symbol]?.metrics[id]?.rmse) }))
      .filter((row): row is { id: (typeof PRINCIPAL_MODEL_IDS)[number]; rmse: number } => row.rmse !== null);
    const minimum = rows.length ? Math.min(...rows.map(({ rmse }) => rmse)) : null;
    const tied = minimum === null ? [] : rows.filter(({ rmse }) => rmse === minimum);
    const winner = tied[0];
    if (winner) wins[MODEL_NAMES[winner.id]] += 1;
    return {
      ticker: company.symbol,
      winner: winner ? MODEL_NAMES[winner.id] : "unavailable",
      exactTie: tied.length > 1,
      tiedModels: tied.map(({ id }) => MODEL_NAMES[id]),
      tiePolicy: "LIR, then ARIMA, then LSTM",
      winningRmsePhp: minimum === null ? "unavailable" : formatNum(minimum, 4),
    };
  });

  return asContext("compare", {
    source: "Current fresh-training chronological out-of-sample evaluation.",
    companiesEvaluated: companies.length,
    evaluationSessionCount: "Not present in metrics.json; do not infer or invent it.",
    forecastTargetDate: latest?.forecastDate ? formatDate(latest.forecastDate) : "unavailable",
    metricsGeneratedAtPht: metrics.generatedAt ? formatDateTimePht(metrics.generatedAt) : "unavailable",
    principalModelWinnerCounts: wins,
    bestPrincipalModelByCompany: bestByCompany,
    descriptiveAggregateStatistic: metrics.aggregateStatistic ?? "legacy unspecified",
    descriptiveAggregateMetrics: Object.fromEntries(
      Object.entries(metrics.aggregate).map(([name, values]) => [
        name === "Naive baseline" ? "Naive benchmark" : name,
        {
          rmsePhp: formatNum(values.rmse, 4),
          maePhp: formatNum(values.mae, 4),
          mase: formatNum(values.mase, 4),
          r2: formatNum(values.r2, 4),
        },
      ]),
    ),
    perCompanyMetrics: Object.fromEntries(companies.map(({ symbol }) => [symbol, metricFacts(metrics.perCompany[symbol]?.metrics)])),
    comparisonRules: {
      principalSelection: "The best principal model is the lowest-RMSE LIR, ARIMA, or LSTM result per company on the common chronological out-of-sample evaluation.",
      evaluatedSelection: "The best evaluated method uses the same RMSE rule but also includes Naive, so it can differ from the best principal model.",
      crossCompany: "Do not select a winner from median or mean raw-peso RMSE/MAE. Use median MASE, within-company ranks, win counts, and counts beating Naive.",
      r2: "R² is supplementary, may be negative, and is not percentage accuracy or a selection criterion.",
      naive: "Separately evaluated benchmark, not a production principal model.",
      statisticalSignificance: "No statistical-significance claim is supplied in current operational context.",
    },
  });
}

export async function buildGeneralContext(): Promise<string> {
  const companies = await getCompanies();
  return asContext("general", {
    project: "ForecastPH is an educational next-session PSE closing-price forecasting project.",
    trackedCompanyCount: companies.length,
    trackedTickers: companies.map(({ symbol }) => symbol),
    principalModels: ["Lag-Informed Regression", "ARIMA", "LSTM"],
    benchmark: "Naive benchmark",
    limitation: "Forecasts are estimates, not guarantees or investment advice.",
  });
}

export async function buildContextForRequest(options?: ContextOptions): Promise<string> {
  const route = options?.route || "";
  const symbol = options?.symbol;
  if (symbol || route.startsWith("/companies/")) {
    const resolved = symbol || route.replace("/companies/", "").split("/")[0];
    if (resolved && resolved !== "undefined") return buildCompanyContext(resolved);
  }
  if (route === "/compare") return buildCompareContext();
  if (route === "/" || route === "") return buildHomeContext();
  if (route === "/companies") return buildCompaniesContext();
  if (route === "/watchlist") return buildWatchlistContext(options?.watchlist);
  if (route === "/learn" || route === "/learn-stocks") return buildLearnStocksContext();
  if (route === "/about") return buildAboutContext();
  return buildGeneralContext();
}
