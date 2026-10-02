/**
 * Centralized registry of concise informational tooltips for PSE Pulse.
 * Used on /companies/[ticker].
 */

export interface TooltipItem {
  title: string;
  body: string;
}

export const COMPANY_TOOLTIPS = {
  // --- /companies/[ticker] ---
  // HEADER
  "detail-data-asof": {
    title: "Market data through",
    body: "The most recent trading session included in this company's market data. The forecast targets the following trading session.",
  },
  "detail-forecast-for": {
    title: "Forecast date",
    body: "The trading session for which the displayed closing-price forecast was generated.",
  },
  "detail-view-mode": {
    title: "View mode",
    body: "Beginner highlights the main forecast and charts. Advanced adds per-model predictions, metrics, leaderboard details, and error analysis.",
  },

  // METRIC CARDS
  "metric-prev-close": {
    title: "Previous close",
    body: "The actual closing price from the most recent completed trading session.",
  },
  "metric-forecast-close": {
    title: "Forecasted close",
    body: "The selected principal model's projected closing price for the next trading session.",
  },
  "metric-expected-change": {
    title: "Expected change",
    body: "The peso and percentage difference between the forecasted close and the previous observed close. It is a model projection, not a trading signal.",
  },
  "metric-best-model": {
    title: "Best principal model",
    body: "The principal model with the lowest RMSE on the common chronological out-of-sample evaluation. Its forecast becomes the main displayed prediction.",
  },

  // MODEL FORECAST CARDS
  "forecast-arima": {
    title: "Model forecast",
    body: "This model's projected closing price for the next session. The selected badge marks the principal model with the lowest evaluation RMSE.",
  },
  "forecast-lagreg": {
    title: "Model forecast",
    body: "This model's projected closing price for the next session. The selected badge marks the principal model with the lowest evaluation RMSE.",
  },
  "forecast-lstm": {
    title: "Model forecast",
    body: "This model's projected closing price for the next session. The selected badge marks the principal model with the lowest evaluation RMSE.",
  },

  // HISTORICAL OHLCV
  "chart-ohlcv-title": {
    title: "Historical OHLCV",
    body: "Shows historical Open, High, Low, Close, and Volume data. It provides market context before the next-session forecast.",
  },
  "chart-ohlcv-period": {
    title: "Chart period",
    body: "Choose a preset or specify a start and end date to control the historical range displayed on the chart.",
  },
  "chart-ohlcv-series": {
    title: "Series",
    body: "Choose which OHLC price series and volume data are visible on the historical chart.",
  },
  "chart-ohlcv-legend": {
    title: "Chart legend",
    body: "Identifies the visual series for Open, High, Low, Close, and Volume.",
  },

  // NEXT-DAY PREDICTION
  "chart-nextday-title": {
    title: "Next-day prediction",
    body: "Shows recent actual closing prices together with the projected closing price for the next trading session.",
  },
  "chart-nextday-presets": {
    title: "Lookback window",
    body: "Controls how many recent trading sessions are displayed before the next-session forecast.",
  },
  "chart-nextday-legend": {
    title: "Actual vs. predicted",
    body: "Actual Close represents observed market prices. Predicted Close marks the model estimate for the forecast session.",
  },

  // PREDICTED VS. ACTUAL
  "chart-pva-badges": {
    title: "Evaluation phases",
    body: "Chronological evaluation measures forecasts on held-out historical sessions in time order. Post-formal monitoring tracks later operational forecasts separately.",
  },
  "chart-pva-banner": {
    title: "Formal evaluation cutoff",
    body: "The finalized formal evaluation ends at this cutoff. Later forecasts belong to operational monitoring and do not alter the frozen formal results.",
  },
  "chart-pva-info": {
    title: "Sessions shown",
    body: "The number of sessions currently displayed with both a prediction and actual closing price available for comparison.",
  },

  // MODEL PERFORMANCE LEADERBOARD
  "lb-title": {
    title: "Model performance",
    body: "Compares models using common evaluation metrics. Among the three principal models, the lowest RMSE determines the selected model.",
  },
  "lb-rmse": {
    title: "RMSE (₱)",
    body: "Typical prediction error with larger errors weighted more heavily. Lower is better.",
  },
  "lb-mae": {
    title: "MAE (₱)",
    body: "Average absolute size of the model's prediction errors in pesos. Lower is better.",
  },
  "lb-mase": {
    title: "MASE",
    body: "Scaled forecast error based on the development-series one-step error scale. Lower is better; below 1 does not automatically mean the model beat the evaluated Naive benchmark.",
  },
  "lb-rsquared": {
    title: "Holdout R²",
    body: "Supplementary goodness-of-fit for the held-out period. Higher is generally better, but it can be negative and is not percentage accuracy.",
  },
  "lb-selected": {
    title: "Selected principal model",
    body: "This principal model has the lowest RMSE among LIR, ARIMA, and LSTM and supplies the main next-session forecast.",
  },
  "lb-benchmark": {
    title: "Naive benchmark",
    body: "Uses the previous observed close as the next-close prediction. It is a benchmark, not a fourth principal production model.",
  },

  // ERROR CHARTS
  "chart-error-time": {
    title: "Forecast error over time",
    body: "Shows prediction errors across evaluation sessions. Values closer to zero indicate smaller forecast misses.",
  },
  "chart-error-dist": {
    title: "Error distribution",
    body: "Shows the distribution of absolute per-session forecast errors. More observations near zero indicate smaller prediction misses.",
  },
} as const;

export type CompanyTooltipId = keyof typeof COMPANY_TOOLTIPS;
