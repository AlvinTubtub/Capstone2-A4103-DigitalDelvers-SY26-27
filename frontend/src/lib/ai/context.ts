import { getCompanyDetail, getCompanies, getDashboard, getLatest, getMetrics } from "@/lib/data";
import { formatDate, formatDateTimePht, formatNum, formatPct, formatPeso } from "@/lib/format";
import { resolveCompanyModelReporting } from "@/lib/modelReporting";
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
  return JSON.stringify({ page, source: "current PSE Pulse operational data", facts }, null, 2);
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
    source: "Chronological out-of-sample predicted-versus-actual observations exported by PSE Pulse.",
    displayLabel: "Latest 60 Evaluation Sessions",
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
    presentationScope: "This chart window is a presentation subset; it is not the complete evaluation used for metrics or statistical tests.",
    fullEvaluation: company.evaluationMetadata ? {
      sessions: company.evaluationMetadata.fullSessionCount,
      firstTargetDate: formatDate(company.evaluationMetadata.fullStartDate),
      lastTargetDate: formatDate(company.evaluationMetadata.fullEndDate),
      metricsScope: company.evaluationMetadata.metricsScope,
      statisticalTestsScope: company.evaluationMetadata.statisticalTestsScope,
    } : "Unavailable in this previously published payload; do not infer it from the 60-session display subset.",
  };
}

export async function buildCompanyContext(symbol: string): Promise<string> {
  const cleanSymbol = symbol.toUpperCase().trim();
  const company = await getCompanyDetail(cleanSymbol);
  if (!company) {
    const companies = await getCompanies();
    return asContext("company", {
      requestedTicker: cleanSymbol,
      status: "That company is not available in the current PSE Pulse data.",
      trackedTickers: companies.map(({ symbol: ticker }) => ticker),
    });
  }

  const chosenMetric = selectedMetric(company);
  const reporting = resolveCompanyModelReporting({
    metrics: company.metrics,
    bestModel: company.model,
    bestPrincipalModel: company.bestPrincipalModel,
    bestEvaluatedMethod: company.bestEvaluatedMethod,
    bestPrincipalBeatsNaive: company.bestPrincipalBeatsNaive,
    allPrincipalsWorseThanNaive: company.allPrincipalsWorseThanNaive,
  });
  return asContext("company", {
    company: { ticker: company.symbol, name: company.name, sector: company.sector },
    currentForecast: {
      latestObservedClose: formatPeso(company.previousClose),
      projectedNextClose: formatPeso(company.predictedClose),
      projectedPesoChange: formatPeso(company.pesoChange),
      projectedPercentageChange: formatPct(company.pctChange),
      directionLabel: company.direction,
      selectedPrincipalModel: company.model,
      bestPrincipalModel: reporting?.bestPrincipalModel ?? company.model,
      bestEvaluatedMethod: reporting?.bestEvaluatedMethod ?? "unavailable",
      bestPrincipalBeatNaive: reporting?.bestPrincipalBeatsNaive ?? "unavailable",
      allPrincipalsHadHigherRmseThanNaive:
        reporting?.allPrincipalsWorseThanNaive ?? "unavailable",
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
    project: "PSE Pulse is an educational next-session PSE closing-price forecasting and model-comparison project.",
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
    const reporting = detail ? resolveCompanyModelReporting({
      metrics: detail.metrics,
      bestModel: detail.model,
      bestPrincipalModel: detail.bestPrincipalModel,
      bestEvaluatedMethod: detail.bestEvaluatedMethod,
      bestPrincipalBeatsNaive: detail.bestPrincipalBeatsNaive,
      allPrincipalsWorseThanNaive: detail.allPrincipalsWorseThanNaive,
    }) : null;
    return {
      ...companySummary(company),
      selectedModelRmsePhp: metric ? formatNum(metric.rmse, 4) : "unavailable",
      modelPredictionSpread: detail ? modelPredictionSpread(detail) : null,
      bestEvaluatedMethod: reporting?.bestEvaluatedMethod ?? "unavailable",
      bestPrincipalBeatNaive: reporting?.bestPrincipalBeatsNaive ?? "unavailable",
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
      R2: "Holdout R² is supplementary. It compares squared errors with an evaluation-period mean reference, can be negative, is not percentage accuracy, and never selects or promotes a model.",
    },
    boundaries: "Explain concepts, not personalized investment decisions. Current schedules and broker details should be verified with official sources.",
  });
}

export async function buildAboutContext(): Promise<string> {
  const [metrics, companies, latest, dashboard] = await Promise.all([
    getMetrics(),
    getCompanies(),
    getLatest(),
    getDashboard(),
  ]);

  const wins = Object.fromEntries(
    PRINCIPAL_MODEL_IDS.map((id) => [MODEL_NAMES[id], 0]),
  ) as Record<string, number>;

  let bestByCompany: Array<{
    ticker: string;
    winner: string;
    bestEvaluatedMethod: string;
    winningRmsePhp: string;
  }> = [];

  if (metrics && companies.length) {
    bestByCompany = companies.map((company) => {
      const companyEvaluation = metrics.perCompany[company.symbol];
      const reporting = companyEvaluation
        ? resolveCompanyModelReporting(companyEvaluation)
        : null;
      const rows = PRINCIPAL_MODEL_IDS.map((id) => ({
        id,
        rmse: finiteNumber(metrics.perCompany[company.symbol]?.metrics[id]?.rmse),
      })).filter(
        (row): row is { id: (typeof PRINCIPAL_MODEL_IDS)[number]; rmse: number } =>
          row.rmse !== null,
      );
      const minimum = rows.length ? Math.min(...rows.map(({ rmse }) => rmse)) : null;
      const tied = minimum === null ? [] : rows.filter(({ rmse }) => rmse === minimum);
      const winner = tied[0];
      if (winner) wins[MODEL_NAMES[winner.id]] += 1;
      return {
        ticker: company.symbol,
        winner: winner ? MODEL_NAMES[winner.id] : "unavailable",
        bestEvaluatedMethod: reporting?.bestEvaluatedMethod ?? "unavailable",
        winningRmsePhp: minimum === null ? "unavailable" : formatNum(minimum, 4),
      };
    });
  }

  return asContext("about", {
    project:
      "PSE Pulse is an educational next-session PSE closing-price forecasting and model-comparison platform.",
    objective:
      "Cross-Sector Next-Day Stock Price Forecasting of Selected PSE-Listed Companies.",
    trackedCompanyCount: companies.length || 15,
    trackedSectors: dashboard?.sectors?.map((s) => s.name) ?? [
      "Financials",
      "Industrial",
      "Mining and Oil",
      "Property",
      "Services",
    ],
    forecastTargetDate: latest?.forecastDate
      ? formatDate(latest.forecastDate)
      : "unavailable",
    lastPipelineRunPht:
      latest?.lastRunAt || dashboard?.lastRunAt
        ? formatDateTimePht(latest?.lastRunAt || dashboard?.lastRunAt)
        : "unavailable",
    models: {
      principalModels: [
        "Lag-Informed Regression (LASSO regularized autoregression with causal lag, volume, and technical features)",
        "ARIMA (classical econometric autoregressive integrated moving average)",
        "LSTM (recurrent deep neural network over closing price differences)",
      ],
      benchmark:
        "Naive benchmark (predicts next Close equals previous observed Close; strictly an evaluation benchmark, not a production principal model)",
    },
    lifecycle: [
      "Historical / EOD market data ingestion from official PSE Daily Quotations Reports",
      "Validation and feature preparation with zero lookahead bias",
      "Diverse modeling methodology across LIR, ARIMA, and LSTM",
      "Chronological out-of-sample evaluation (85% dev / 15% holdout split)",
      "Production refit of all three principal models on 100% of validated history",
      "Persisted-model next-session forward inference without retraining",
      "Frontend forecast presentation via atomic JSON exports",
    ],
    modelTrainingSchedule:
      "Quarterly fresh model training and evaluation (scheduled Feb 28, May 28, Aug 28, Nov 28 at 8:00 AM PHT). The daily pipeline does NOT retrain models; it performs persisted-model inference only.",
    evaluationSafeguards: [
      "Chronological Evaluation: strictly no random train/test shuffling.",
      "Common Evaluation Dates: all four methods evaluated on identical target sessions.",
      "Naive Benchmark: previous Close evaluated alongside principal models.",
      "Common MASE Scaling: single development-series denominator per company.",
      "Frozen Research Evidence: historical formal evaluation is preserved separately from live monitoring.",
      "Post-Formal Monitoring: prospective ledger tracking never rewrites frozen historical metrics.",
      "Tamper-Detectable Evidence: integrity verification ensures complete provenance.",
    ],
    accuracyMetrics: {
      RMSE: "Root Mean Square Error; lower is better; peso-denominated; penalizes large errors heavily.",
      MAE: "Mean Absolute Error; lower is better; average absolute error in pesos.",
      MASE: "Mean Absolute Scaled Error; lower is better; scale-independent comparison against development-period one-step baseline. Value < 1.0 indicates error below development scale.",
      R2: "Holdout R²; supplementary metric; may be negative; not percentage accuracy; not the selection/promotion criterion.",
      significanceNote:
        "Lower historical error does not automatically prove statistical significance. Metrics differences describe lower holdout error only.",
    },
    modelPerformanceSummary: metrics
      ? {
          principalModelWinnerCounts: wins,
          bestPrincipalModelByCompany: bestByCompany,
          aggregateMetrics: metrics.aggregate,
        }
      : "Current model evaluation metrics are loading or unavailable.",
    researchQuestions: [
      "RQ1 (Model Comparison): How do Lag-Informed Regression, ARIMA, and LSTM compare in next-session forecasting accuracy across the selected companies?",
      "RQ2 (Benchmark Utility): Do the principal forecasting models achieve lower historical out-of-sample error than a previous-close Naive benchmark?",
      "RQ3 (Cross-Sector Behavior): Does the model with the lowest historical evaluation error remain consistent across companies and PSE sectors?",
    ],
    researchScope: {
      included: [
        "Daily Philippine Stock Exchange OHLCV market data",
        "Next-session closing-price forecasting",
        "15 selected PSE-listed companies across five sectors",
        "Lag-Informed Regression",
        "ARIMA",
        "LSTM",
        "Previous-close Naive evaluation benchmark",
        "Chronological out-of-sample evaluation",
        "Post-formal prospective forecast monitoring",
      ],
      outsideScope: [
        "Intraday price forecasting",
        "Automated trading or order execution",
        "Buy/sell recommendations",
        "Portfolio optimization",
        "Personalized investment advice",
        "News or social-media sentiment forecasting",
        "Fundamental valuation models",
        "Guaranteed price or return predictions",
      ],
      scopeNote:
        "The implemented forecasting models primarily use historical numerical market data. Unexpected news, corporate events, policy changes, macroeconomic shocks, and other external information may affect actual market outcomes without being represented directly in the model inputs.",
    },
    systemArchitecture: {
      pipelineFlow:
        "PSE End-of-Day Market Data -> Python Forecasting & Evaluation Backend -> Validated Forecast / Model Artifacts -> Frontend Forecast JSON -> Next.js PSE Pulse Website",
      technologyGroups: {
        dataAndModeling: [
          "Python",
          "Pandas",
          "NumPy",
          "scikit-learn",
          "statsmodels",
          "PyTorch",
        ],
        researchAndAutomation: [
          "Chronological evaluation",
          "Persisted model artifacts",
          "Integrity validation",
          "GitHub Actions",
          "Scheduled pipeline automation",
        ],
        webPresentation: [
          "Next.js",
          "TypeScript",
          "Tailwind CSS",
          "Vercel",
          "Frontend JSON data layer",
        ],
      },
      frontendInferenceNote:
        "The public Next.js frontend reads validated exported forecast data and does not run Python model training or inference on Vercel.",
    },
    limitations: [
      "Educational decision support only; never constitutes financial advice or trading signals.",
      "Historical pattern limitation: past accuracy does not guarantee future performance.",
      "Unexpected events: breaking news, corporate actions, and macroeconomic shocks cannot be captured by price-pattern models.",
      "Model uncertainty: different forecasting models can disagree and all forecasts contain error.",
      "Independent due diligence: users must verify information independently before making investment decisions.",
    ],
  });
}

export async function buildCompareContext(): Promise<string> {
  const [metrics, companies, latest] = await Promise.all([getMetrics(), getCompanies(), getLatest()]);
  if (!metrics || !companies.length) return asContext("compare", { status: "Current operational model-evaluation data is unavailable." });

  const wins = Object.fromEntries(PRINCIPAL_MODEL_IDS.map((id) => [MODEL_NAMES[id], 0])) as Record<string, number>;
  const bestByCompany = companies.map((company) => {
    const companyEvaluation = metrics.perCompany[company.symbol];
    const reporting = companyEvaluation
      ? resolveCompanyModelReporting(companyEvaluation)
      : null;
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
      bestEvaluatedMethod: reporting?.bestEvaluatedMethod ?? "unavailable",
      bestPrincipalBeatNaive: reporting?.bestPrincipalBeatsNaive ?? "unavailable",
      allPrincipalsHadHigherRmseThanNaive:
        reporting?.allPrincipalsWorseThanNaive ?? "unavailable",
      fullEvaluation: companyEvaluation?.evaluationMetadata ?? "unavailable",
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
      r2: "Holdout R² is supplementary, uses the evaluation-period mean reference, may be negative, and is not percentage accuracy or a selection or promotion criterion.",
      naive: "Separately evaluated benchmark, not a production principal model.",
      statisticalSignificance: "No finalized formal-run evidence is supplied in current operational context. Describe numerical differences only as lower error during the evaluation period; do not make statistical-significance claims.",
    },
  });
}

export async function buildGeneralContext(): Promise<string> {
  const companies = await getCompanies();
  return asContext("general", {
    project: "PSE Pulse is an educational next-session PSE closing-price forecasting project.",
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
