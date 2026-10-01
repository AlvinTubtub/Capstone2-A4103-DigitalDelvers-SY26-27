/**
 * Centralized educational data for PSE Pulse Learn Stocks.
 * Stores PSE reference data, broker directory entries, terms, and video metadata.
 */

export interface PseMarketSchedule {
  phase: string;
  time: string;
  description: string;
}

export const PSE_MARKET_SCHEDULE: PseMarketSchedule[] = [
  {
    phase: "Pre-Open",
    time: "9:00 AM – 9:15 AM PHT",
    description: "Orders can be entered, modified, or canceled. No trades are executed while the system calculates indicative opening prices.",
  },
  {
    phase: "Pre-Open No-Cancel",
    time: "9:15 AM – 9:30 AM PHT",
    description: "Orders may no longer be canceled before the opening auction.",
  },
  {
    phase: "Market Open / Recess",
    time: "9:30 AM – 12:00 NN PHT",
    description: "Continuous order matching occurs until the noon market recess.",
  },
  {
    phase: "Market Resume",
    time: "1:00 PM – 2:45 PM PHT",
    description: "Continuous order matching resumes after the market recess.",
  },
  {
    phase: "Pre-Close / Run-Off",
    time: "2:45 PM – 3:00 PM PHT",
    description: "The closing auction and trading-at-last determine the closing price; cancellation is restricted after 2:48 PM.",
  },
  {
    phase: "Closing VWAP / Market Close",
    time: "3:00 PM – 3:15 PM PHT",
    description: "The closing VWAP session runs until the official market close at 3:15 PM.",
  },
];

export const PSE_MARKET_SCHEDULE_SOURCE = {
  url: "https://www.pse.com.ph/investing-at-pse/",
  checkedOn: "September 3, 2026",
};

export interface TradingParticipant {
  id: string;
  name: string;
  parentEntity: string;
  pseStatus: string;
  isOnlineTrading: boolean;
  isRetail: boolean;
  websiteUrl: string;
  pseDirectoryUrl: string;
  description: string;
}

export const BROKER_DIRECTORY: TradingParticipant[] = [
  {
    id: "col",
    name: "COL Financial",
    parentEntity: "COL Financial Group, Inc.",
    pseStatus: "Refer to the current PSE Trading Participant Directory",
    isOnlineTrading: true,
    isRetail: true,
    websiteUrl: "https://www.colfinancial.com",
    pseDirectoryUrl: "https://www.pse.com.ph/directory/#tp1",
    description: "Retail-facing brokerage platform. Review its official site for current account, fee, and service information.",
  },
  {
    id: "firstmetro",
    name: "First Metro Securities",
    parentEntity: "First Metro Securities Brokerage Corp. (Metrobank Group)",
    pseStatus: "Refer to the current PSE Trading Participant Directory",
    isOnlineTrading: true,
    isRetail: true,
    websiteUrl: "https://www.firstmetrosec.com.ph",
    pseDirectoryUrl: "https://www.pse.com.ph/directory/#tp1",
    description: "Retail-facing brokerage platform. Review its official site for current account, fee, and service information.",
  },
  {
    id: "bdo",
    name: "BDO Securities",
    parentEntity: "BDO Securities Corporation (BDO Unibank Group)",
    pseStatus: "Refer to the current PSE Trading Participant Directory",
    isOnlineTrading: true,
    isRetail: true,
    websiteUrl: "https://www.bdo.com.ph/securities",
    pseDirectoryUrl: "https://www.pse.com.ph/directory/#tp1",
    description: "Retail-facing brokerage platform. Review its official site for current account, fee, and service information.",
  },
  {
    id: "bpi",
    name: "BPI Securities (BPI Trade)",
    parentEntity: "BPI Securities Corporation (Bank of the Philippine Islands)",
    pseStatus: "Refer to the current PSE Trading Participant Directory",
    isOnlineTrading: true,
    isRetail: true,
    websiteUrl: "https://www.bpitrade.com",
    pseDirectoryUrl: "https://www.pse.com.ph/directory/#tp1",
    description: "Retail-facing brokerage platform. Review its official site for current account, fee, and service information.",
  },
  {
    id: "dragonfi",
    name: "DragonFi Securities",
    parentEntity: "DragonFi Securities, Inc.",
    pseStatus: "Refer to the current PSE Trading Participant Directory",
    isOnlineTrading: true,
    isRetail: true,
    websiteUrl: "https://www.dragonfi.ph",
    pseDirectoryUrl: "https://www.pse.com.ph/directory/#tp1",
    description: "Retail-facing brokerage platform. Review its official site for current account, fee, and service information.",
  },
  {
    id: "philstocks",
    name: "Philstocks Financial",
    parentEntity: "Philstocks Financial, Inc.",
    pseStatus: "Refer to the current PSE Trading Participant Directory",
    isOnlineTrading: true,
    isRetail: true,
    websiteUrl: "https://www.philstocks.ph",
    pseDirectoryUrl: "https://www.pse.com.ph/directory/#tp1",
    description: "Retail-facing brokerage platform. Review its official site for current account, fee, and service information.",
  },
];

export interface EducationalVideo {
  id: string;
  title: string;
  topic: string;
  channel: string;
  youtubeId: string;
  description: string;
  directUrl: string;
}

export const EDUCATIONAL_VIDEOS: EducationalVideo[] = [
  {
    id: "pse-stock-market-101",
    title: "Stock Market 101",
    topic: "Philippine Stock Market Basics",
    channel: "The Philippine Stock Exchange, Inc.",
    youtubeId: "PNk-VjcUt1U",
    description: "An official PSE Market Education introduction to stock-market investing.",
    directUrl: "https://www.youtube.com/watch?v=PNk-VjcUt1U",
  },
  {
    id: "pse-investing-equities",
    title: "Investing in Stocks or Equities",
    topic: "Stocks and Investing Basics",
    channel: "The Philippine Stock Exchange, Inc.",
    youtubeId: "GnohePDeZgg",
    description: "An official PSE overview of what prospective investors should know before investing in stocks.",
    directUrl: "https://www.youtube.com/watch?v=GnohePDeZgg",
  },
];

export interface TermDefinition {
  term: string;
  category: "market" | "forecastph";
  shortDef: string;
  detailedDef: string;
}

export const GLOSSARY_TERMS: TermDefinition[] = [
  // Foundational equity & ownership terms
  {
    term: "Stock",
    category: "market",
    shortDef: "Fractional ownership unit in a public corporation.",
    detailedDef: "A stock (also known as equity) represents a fractional claim on a corporation's assets and future earnings. Buying stock makes you a part-owner of the company.",
  },
  {
    term: "Share",
    category: "market",
    shortDef: "Single individual unit of stock ownership.",
    detailedDef: "A corporation divides its total capital into equal units called shares. Owning shares entitles the holder to proportionate voting rights and dividend distributions.",
  },
  {
    term: "Shareholder",
    category: "market",
    shortDef: "Individual or entity that legally owns shares in a company.",
    detailedDef: "A shareholder (or stockholder) is any person, company, or institution that owns at least one share of a company's stock, sharing in its financial performance.",
  },
  {
    term: "Stockholder",
    category: "market",
    shortDef: "Synonym for shareholder; an owner of corporation shares.",
    detailedDef: "A stockholder holds equity shares in a company. The terms shareholder and stockholder are interchangeable in Philippine stock market terminology.",
  },
  {
    term: "Dividend",
    category: "market",
    shortDef: "Distribution of corporate earnings paid to shareholders.",
    detailedDef: "A dividend is a portion of a company's net profits declared by its board of directors and distributed to eligible shareholders, typically as cash or additional shares.",
  },
  {
    term: "Cash Dividend",
    category: "market",
    shortDef: "Dividend distributed directly in Philippine Pesos (₱).",
    detailedDef: "Cash dividends are paid in money directly into the shareholder's trading account on a per-share basis (e.g., ₱1.50 per share owned).",
  },
  {
    term: "Stock Dividend",
    category: "market",
    shortDef: "Dividend distributed as additional shares instead of cash.",
    detailedDef: "Stock dividends grant shareholders additional shares proportional to their existing holdings, retaining corporate cash while increasing the investor's total share count.",
  },
  {
    term: "Common Stock",
    category: "market",
    shortDef: "Standard equity ownership with voting rights and variable dividends.",
    detailedDef: "Common shares represent standard corporate ownership with voting rights at shareholder meetings and participation in capital growth, but have secondary priority behind preferred shares upon liquidation.",
  },
  {
    term: "Preferred Stock",
    category: "market",
    shortDef: "Class of equity with fixed dividends and liquidation priority.",
    detailedDef: "Preferred shares typically pay a predetermined fixed dividend and take precedence over common stock for dividend payments and asset liquidation, but usually carry no voting rights.",
  },
  {
    term: "Dividend Yield",
    category: "market",
    shortDef: "Annual dividend payout expressed as a percentage of share price.",
    detailedDef: "Calculated as (Annual Dividends per Share ÷ Current Stock Price) × 100. Shows the percentage return an investor receives solely from dividends relative to the price paid for the share.",
  },
  {
    term: "Capital Gain",
    category: "market",
    shortDef: "Profit from selling a stock above its purchase price.",
    detailedDef: "A capital gain is realized when an investor sells an equity asset for a price higher than the original purchase cost (cost basis).",
  },
  {
    term: "Capital Loss",
    category: "market",
    shortDef: "Financial loss from selling a stock below its purchase price.",
    detailedDef: "A capital loss occurs when a stock is sold for less money than was originally paid to acquire it.",
  },
  {
    term: "Market Capitalization",
    category: "market",
    shortDef: "Total market value of a company's outstanding shares.",
    detailedDef: "Calculated as Current Share Price × Total Number of Outstanding Shares. Reflects the aggregate public equity valuation of a corporation on the exchange.",
  },
  // Trading mechanics terms
  {
    term: "Bid",
    category: "market",
    shortDef: "Highest price a buyer is willing to pay.",
    detailedDef: "The bid price represents the highest price currently offered by buyers in the order book. When you want to sell immediately, your order executes against the highest available bid.",
  },
  {
    term: "Ask",
    category: "market",
    shortDef: "Lowest price a seller is willing to accept.",
    detailedDef: "The ask (or offer) price represents the lowest price that sellers are willing to accept. When you place a market buy order, it executes against the best available ask.",
  },
  {
    term: "Open",
    category: "market",
    shortDef: "First trade price during a session.",
    detailedDef: "The opening price determined during the PSE pre-open order-matching auction at 9:30 AM PHT.",
  },
  {
    term: "High",
    category: "market",
    shortDef: "Highest price recorded during the trading session.",
    detailedDef: "The peak price executed for the stock between market open (9:30 AM) and market close (1:00 PM).",
  },
  {
    term: "Low",
    category: "market",
    shortDef: "Lowest price recorded during the trading session.",
    detailedDef: "The lowest price at which shares were traded during that day's official market session.",
  },
  {
    term: "Close",
    category: "market",
    shortDef: "Final official transaction price of the session.",
    detailedDef: "The official closing price established during the 12:45–12:50 PM pre-close run-off. This is the target value PSE Pulse models predict.",
  },
  {
    term: "Volume",
    category: "market",
    shortDef: "Total number of shares traded during the day.",
    detailedDef: "Volume shows trading activity. High volume indicates strong market liquidity and active institutional participation.",
  },
  {
    term: "Volatility",
    category: "market",
    shortDef: "Magnitude of price swings over a given period.",
    detailedDef: "High volatility means prices swing dramatically up and down; low volatility indicates steadier, more gradual price movement.",
  },
  {
    term: "Liquidity",
    category: "market",
    shortDef: "Ease of buying or selling shares without distorting price.",
    detailedDef: "Liquid stocks have tight bid-ask spreads and deep order books, allowing large trades with minimal price impact.",
  },
  {
    term: "Bull Market",
    category: "market",
    shortDef: "Prolonged period of rising market prices and optimism.",
    detailedDef: "A sustained uptrend typically defined by market indices gaining 20% or more from recent lows with strong investor confidence.",
  },
  {
    term: "Bear Market",
    category: "market",
    shortDef: "Prolonged period of falling market prices and pessimism.",
    detailedDef: "A market decline of 20% or more from recent peaks, accompanied by cautious investor sentiment and capital preservation.",
  },
  {
    term: "Diversification",
    category: "market",
    shortDef: "Spreading capital across multiple companies and sectors.",
    detailedDef: "A risk management strategy that mixes different investments within a portfolio to reduce the impact of any single asset's decline.",
  },
  // PSE Pulse terms
  {
    term: "Forecasted Close",
    category: "forecastph",
    shortDef: "Model-estimated closing price for the next session.",
    detailedDef: "The point estimate calculated by the selected machine learning or statistical model for the upcoming trading day's closing price.",
  },
  {
    term: "Actual Price",
    category: "forecastph",
    shortDef: "The real price recorded by the PSE when trading concludes.",
    detailedDef: "The ground-truth closing price published in the official PSE Daily Quotation Report after 1:00 PM PHT.",
  },
  {
    term: "Prediction Error",
    category: "forecastph",
    shortDef: "Predicted Close minus Actual Close (₱).",
    detailedDef: "The arithmetic difference between what the model estimated and what the market actually settled at. Positive means overestimation; negative means underestimation.",
  },
  {
    term: "Backtest",
    category: "forecastph",
    shortDef: "Simulating past predictions using historical holdout data.",
    detailedDef: "A presentation view of the latest 60 out-of-sample evaluation sessions. Full metrics and statistical tests use the complete aligned holdout, whose count and dates are reported separately.",
  },
  {
    term: "Lag-Informed Regression",
    category: "forecastph",
    shortDef: "Interpretable regression using price/volume lags with LASSO regularization.",
    detailedDef: "Interpretable statistical machine learning model that analyzes historical price and volume lags with Partial Autocorrelation (PACF) lag selection and LASSO feature elimination.",
  },
  {
    term: "ARIMA",
    category: "forecastph",
    shortDef: "Autoregressive Integrated Moving Average classical econometric model.",
    detailedDef: "Classical statistical time-series standard that differences non-stationary historical prices and models autoregressive and moving-average error structures.",
  },
  {
    term: "LSTM",
    category: "forecastph",
    shortDef: "Recurrent deep neural network designed for sequence patterns.",
    detailedDef: "Long Short-Term Memory recurrent neural network with specialized gating mechanisms designed to learn non-linear temporal sequence patterns across multi-day horizons.",
  },
  {
    term: "Naive Benchmark",
    category: "forecastph",
    shortDef: "Predicts tomorrow's Close equals today's observed Close.",
    detailedDef: "A neutral random-walk baseline evaluated alongside principal models. It is strictly an evaluation benchmark, not a fourth production principal model.",
  },
  {
    term: "RMSE (Root Mean Squared Error)",
    category: "forecastph",
    shortDef: "Penalizes large errors; measured in Philippine Pesos (₱).",
    detailedDef: "RMSE squares each error before averaging, making it sensitive to large outlier forecasting misses. Lower RMSE indicates smaller average errors.",
  },
  {
    term: "MAE (Mean Absolute Error)",
    category: "forecastph",
    shortDef: "Average absolute difference between prediction and actual.",
    detailedDef: "The average distance between model forecasts and actual prices in Pesos. Directly interpretable as the typical peso forecast miss.",
  },
  {
    term: "MASE (Mean Absolute Scaled Error)",
    category: "forecastph",
    shortDef: "Evaluation MAE scaled by development-series one-step changes.",
    detailedDef: "Scale-free metric dividing evaluation MAE by the common one-step absolute-change scale from development Close. Values below 1.0 are below that development scale, but do not by themselves prove the model beat Naive on held-out dates.",
  },
  {
    term: "Holdout R² (Supplementary)",
    category: "forecastph",
    shortDef: "Supplementary held-out goodness-of-fit that can be negative.",
    detailedDef: "Compares squared holdout errors with a reference based on the holdout-period mean. R² can be negative, is not percentage accuracy, does not select or promote a model, and never guarantees future performance.",
  },
];

/** Structured educational concepts for safe AI context injection across all routes */
export const CORE_EDUCATIONAL_CONCEPTS = {
  foundations: {
    stock: "A stock (equity) represents fractional ownership in a corporation. Buying a stock makes you a part-owner (shareholder) of that company's assets and earnings.",
    share: "A single unit of ownership in a company. Total equity is divided into individual shares.",
    shareholder: "An individual or entity that owns shares of stock in a company, entitling them to proportionate earnings and voting rights.",
    stockholder: "Synonym for shareholder; holds shares of stock in a corporation.",
    dividend: "A distribution of corporate earnings to eligible shareholders, declared by the board of directors as cash or additional shares.",
    cashDividend: "A dividend paid directly in cash (Philippine Pesos, ₱) per share into the shareholder's trading account.",
    stockDividend: "A dividend paid in additional shares of stock rather than cash, increasing total shares owned.",
    commonStock: "Standard corporate equity conferring voting rights and variable dividends, secondary to preferred stock in liquidation.",
    preferredStock: "A class of equity that pays fixed dividends with priority over common stock, but typically without voting rights.",
    dividendYield: "Annual dividend per share divided by current stock price, expressed as a percentage: (Annual Dividends ÷ Price) × 100.",
    capitalGain: "The profit realized when selling a stock for more than its purchase price.",
    capitalLoss: "The financial loss incurred when selling a stock below its purchase price.",
    marketCapitalization: "Total market value of a company's shares, calculated as Current Share Price × Total Outstanding Shares.",
  },
  modelsAndForecasting: {
    forecastedClose: "Algorithmic point estimate for the next trading day's closing price based on historical numerical patterns. Not a guarantee.",
    backtesting: "Simulating model predictions over historical out-of-sample data to evaluate forecasting error before deploying.",
    lagInformedRegression: "Interpretable regression using autoregressive price and volume features with LASSO regularization.",
    arima: "Autoregressive Integrated Moving Average; classical statistical econometric model tracking cyclical trends and mean-reversion.",
    lstm: "Long Short-Term Memory; recurrent neural network architecture learning non-linear multi-day temporal sequence patterns.",
    naiveBenchmark: "Evaluation baseline predicting tomorrow's Close equals today's observed Close. It is a benchmark, not a production model.",
  },
  metrics: {
    rmse: "Root Mean Squared Error in Philippine Pesos (₱). Lower is better. Squares misses to penalize large errors heavily.",
    mae: "Mean Absolute Error in Philippine Pesos (₱). Lower is better. Represents the typical peso miss magnitude.",
    mase: "Mean Absolute Scaled Error. Lower is better. Divides evaluation MAE by a development one-step change scale. Below 1.0 means below that development scale; compare holdout RMSE to determine if it beat Naive.",
    holdoutR2: "Supplementary goodness-of-fit metric comparing squared holdout errors to sample mean reference. May be negative; not percentage accuracy; never selects or promotes a model.",
  },
};

/** 4-Step sequential learning path displayed on /learn-stocks */
export const LEARNING_PATH_STEPS = [
  {
    step: 1,
    title: "Learn Before You Trade",
    category: "Fundamentals",
    description: "Understand shares, dividends, trading sessions, capital gains, and risk diversification.",
    href: "/learn-stocks#trading-101",
  },
  {
    step: 2,
    title: "Understand a Forecast",
    category: "Predictions",
    description: "Learn how next-day price targets are generated, what expected movement means, and why prices diverge.",
    href: "/learn-stocks#how-to-read",
  },
  {
    step: 3,
    title: "Check Historical Accuracy",
    category: "Evaluation",
    description: "Evaluate out-of-sample backtests, RMSE, MAE, MASE, and the separately evaluated Naive benchmark.",
    href: "/learn-stocks#forecast-accuracy",
  },
  {
    step: 4,
    title: "Explore Companies",
    category: "Practice",
    description: "Inspect 15 PSE companies across 5 sectors, toggle Beginner/Advanced views, and add to Watchlist.",
    href: "/companies",
  },
];
