/**
 * Centralized educational data for ForecastPH Learn Stocks.
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
    detailedDef: "The official closing price established during the 12:45–12:50 PM pre-close run-off. This is the target value ForecastPH models predict.",
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
  // ForecastPH terms
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
    detailedDef: "A rigorous 60-session out-of-sample evaluation where models predict each day one session at a time without seeing future data.",
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
    term: "R² (Goodness-of-Fit)",
    category: "forecastph",
    shortDef: "Supplementary held-out goodness-of-fit that can be negative.",
    detailedDef: "Measures statistical goodness-of-fit against the mean. R² is not percentage accuracy, does not select the winning model, and never guarantees future performance.",
  },
];
