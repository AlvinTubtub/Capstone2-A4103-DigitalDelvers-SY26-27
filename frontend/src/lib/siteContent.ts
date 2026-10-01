/**
 * Centralized informational and explanatory content for PSE Pulse.
 * Shared between website rendering components and Ask AI grounding context.
 */

export interface SectorCardItem {
  name: string;
  queryParam: string;
  image: string;
  description: string;
  tickers: string[];
}

export const HOME_SECTOR_CARDS: SectorCardItem[] = [
  {
    name: "Financials",
    queryParam: "Financials",
    image: "/images/sectors/financials.jpg",
    description: "Banking, capital markets & financial institutions",
    tickers: ["BPI", "MBT", "SECB"],
  },
  {
    name: "Industrial",
    queryParam: "Industrial",
    image: "/images/sectors/industrial.jpg",
    description: "Utilities, power distribution & food manufacturing",
    tickers: ["MER", "JFC", "SHLPH"],
  },
  {
    name: "Mining & Oil",
    queryParam: "Mining and Oil",
    image: "/images/sectors/mining-and-oil.jpg",
    description: "Resource extraction, minerals & energy generation",
    tickers: ["APX", "NIKL", "SCC"],
  },
  {
    name: "Property",
    queryParam: "Property",
    image: "/images/sectors/property.jpg",
    description: "Real estate development, commercial leasing & malls",
    tickers: ["ALI", "SMPH", "MEG"],
  },
  {
    name: "Services",
    queryParam: "Services",
    image: "/images/sectors/services.jpg",
    description: "Telecommunications, retail grocers & port management",
    tickers: ["GLO", "PGOLD", "ICT"],
  },
];

export interface BeginnerGuideCardItem {
  step: number;
  title: string;
  image: string;
  alt: string;
  href: string;
  description: string;
}

export const HOME_BEGINNER_GUIDE_CARDS: BeginnerGuideCardItem[] = [
  {
    step: 1,
    title: "Understand the Forecast",
    image: "/images/learn/understand-forecast.jpg",
    alt: "Trader inspecting stock forecast projections on transparent display",
    href: "/learn-stocks#how-to-read",
    description:
      "PSE Pulse predicts the estimated next trading-day closing price based on numerical historical market data. Predictions are statistical estimates and are not guaranteed.",
  },
  {
    step: 2,
    title: "Check Historical Accuracy",
    image: "/images/learn/check-historical-accuracy.jpg",
    alt: "Analyst inspecting stock market line chart and historical prediction accuracy",
    href: "/learn-stocks#forecast-accuracy",
    description:
      "Always review the Backtest, Forecast Error, RMSE, MAE, MASE, and supplementary holdout R² to understand historical evaluation performance before interpreting a forecast.",
  },
  {
    step: 3,
    title: "Learn Before You Trade",
    image: "/images/learn/learn-before-you-trade.jpg",
    alt: "Traders reviewing market candlestick charts on laptop and tablet",
    href: "/learn-stocks#trading-101",
    description:
      "Build a strong foundation in Philippine stock market fundamentals, risk management, and order types before making financial decisions.",
  },
];

export const COMPANY_FIELD_EXPLANATIONS = {
  latestClose: "Most recent verified transaction price settled by the PSE at market close (₱).",
  predictedClose: "Algorithmic point estimate calculated by the selected model for the upcoming trading day's closing price (₱).",
  expectedChange: "Projected percentage difference between forecasted close and latest observed close ((Forecast - Close) ÷ Close × 100). Not a buy/sell signal.",
  selectedPrincipalModel: "The model among Lag-Informed Regression, ARIMA, and LSTM that achieved the lowest out-of-sample RMSE during historical evaluation.",
};

export const COMPANY_DETAIL_CHART_EXPLANATIONS = {
  historicalOhlcv: "Interactive visual history of verified daily Open, High, Low, Close prices and trading volume with date-range filters (1M, 3M, 6M, 1Y) and zoom controls.",
  nextDayPrediction: "Plots the latest observed close and projects broken dashed trajectory lines representing next-day targets from Lag Regression, ARIMA, and LSTM.",
  latest60Sessions: "Overlays actual closing prices against the chronological out-of-sample forecasts. This chart is a presentation subset, not the full evaluation dataset.",
  forecastErrorResiduals: "Plots the prediction residual (Predicted Close minus Actual Close in ₱). Oscillations around zero indicate balanced forecasts; persistent upward or downward drift indicates directional bias.",
  modelPredictionSpread: "Maximum principal-model forecast minus minimum principal-model forecast for the next session. Represents model disagreement; strictly not a confidence interval.",
};

export const WATCHLIST_EXPLANATIONS = {
  purpose: "A browser-side utility allowing users to pin up to 5 companies for convenient side-by-side comparison of latest prices, forecasts, and model rankings.",
  storage: "Browser-only localStorage (`pse_watchlist`). Pinned tickers are kept locally on your device and are never transmitted to or stored on external servers.",
  capacity: "Maximum 5 pinned companies at any given time.",
  comparisonFeatures: "Side-by-side actual vs. predicted price curves, expected change comparisons, selected model RMSE comparisons, and model disagreement across pinned stocks.",
};

export const COMPARE_EXPLANATIONS = {
  models: {
    lagReg: "Lag-Informed Regression (LIR): Autoregressive linear model with causal lag, volume, and technical indicators regularized using LASSO ('The Pattern Spotter').",
    arima: "ARIMA: Classical econometric autoregressive integrated moving average model for linear time-series trends and error autocorrelation ('The Trend Tracker').",
    lstm: "LSTM: Recurrent deep neural network with input, forget, and output gates capturing non-linear multi-day temporal sequence patterns ('Deep Sequence Memory').",
    naive: "Naive Benchmark: Predicts next Close equals previous observed Close. Evaluated as a baseline to test whether models beat a random walk. Strictly an evaluation benchmark, not a production principal model.",
  },
  metrics: {
    rmse: "Root Mean Squared Error in ₱; lower is better; penalizes large forecasting misses heavily.",
    mae: "Mean Absolute Error in ₱; lower is better; represents typical peso forecast miss.",
    mase: "Mean Absolute Scaled Error; lower is better; scaled by development-series one-step changes. Value < 1.0 indicates error below development scale; does not alone prove beating Naive on held-out dates.",
    holdoutR2: "Supplementary goodness-of-fit comparing squared holdout errors with sample mean reference. May be negative, is not percentage accuracy, and never selects or promotes a model.",
  },
  rules: {
    principalWinner: "The best principal model has the lowest out-of-sample RMSE among LIR, ARIMA, and LSTM per company.",
    evaluatedWinner: "The best evaluated method uses the same lowest-RMSE rule but also includes the Naive benchmark (which can beat all principal models for certain stocks).",
    crossCompanyComparison: "Never rank models by averaging raw peso RMSE/MAE across stocks. Use median MASE, within-company ranks, win counts, and counts beating Naive.",
    benchmarkFirst: "Always evaluate whether a model outperforms the no-change Naive baseline before inferring predictive value.",
    statisticalSignificance: "Lower historical holdout error describes past evaluation performance only; it does not constitute proven statistical significance without formal hypothesis testing.",
  },
};

export const ABOUT_EXPLANATIONS = {
  projectTitle: "Cross-Sector Next-Day Stock Price Forecasting of Selected PSE-Listed Companies",
  researchQuestions: {
    rq1: "RQ1 (Model Comparison): How do Lag-Informed Regression, ARIMA, and LSTM compare in next-session forecasting accuracy across the selected companies?",
    rq2: "RQ2 (Benchmark Utility): Do the principal forecasting models achieve lower historical out-of-sample error than a previous-close Naive benchmark?",
    rq3: "RQ3 (Cross-Sector Behavior): Does the model with the lowest historical evaluation error remain consistent across companies and PSE sectors?",
  },
  methodologySteps: [
    "Step 1: Historical / EOD Market Data Ingestion from official PSE Daily Quotations Reports at 3:15 PM PHT.",
    "Step 2: Validation & Feature Preparation with zero lookahead bias and calendar alignment.",
    "Step 3: Training across three diverse paradigms (LIR, ARIMA, PyTorch LSTM).",
    "Step 4: Chronological Out-of-Sample Evaluation (85% dev / 15% holdout split) without shuffling.",
    "Step 5: Full-Data Production Refit of all three principal models on 100% of validated history.",
    "Step 6: Persisted-Model Daily Forward Inference without daily retraining.",
    "Step 7: Decoupled Frontend Forecast Presentation via atomic static JSON exports.",
  ],
  modelTrainingSchedule:
    "Quarterly fresh model training and evaluation (scheduled Feb 28, May 28, Aug 28, Nov 28 at 8:00 AM PHT). The daily pipeline does NOT retrain models; it performs persisted-model forward inference only.",
  integritySafeguards: [
    "Chronological Evaluation: Strictly no random train/test shuffling.",
    "Common Evaluation Dates: All four methods evaluated on identical target sessions.",
    "Naive Benchmark: Previous Close evaluated alongside principal models.",
    "Common MASE Scaling: Single development-series denominator per company.",
    "Frozen Research Evidence: Historical formal evaluation is preserved separately from live monitoring.",
    "Post-Formal Monitoring: Prospective ledger tracking never rewrites frozen historical metrics.",
    "Tamper-Detectable Evidence: Complete integrity verification manifests ensure provenance.",
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
    note: "The implemented forecasting models primarily use historical numerical market data. Unexpected news, corporate events, policy changes, macroeconomic shocks, and other external information may affect actual market outcomes without being represented directly in the model inputs.",
  },
  systemArchitecture: {
    pipelineFlow:
      "PSE EOD Market Data -> Python Forecasting & Evaluation Backend -> Validated Forecast JSON Artifacts -> Next.js Frontend on Vercel",
    technologyGroups: {
      dataAndModeling: ["Python", "Pandas", "NumPy", "scikit-learn", "statsmodels", "PyTorch"],
      researchAndAutomation: [
        "Chronological evaluation",
        "Persisted model artifacts",
        "Integrity validation",
        "GitHub Actions",
        "Scheduled pipeline automation",
      ],
      webPresentation: ["Next.js", "TypeScript", "Tailwind CSS", "Vercel", "Frontend JSON data layer"],
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
};
