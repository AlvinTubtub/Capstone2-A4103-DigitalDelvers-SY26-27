export interface StarterQuestionContext {
  symbol?: string;
  watchlistCount?: number;
}

export interface PageAssistantContent {
  label: string;
  description: string;
  questions: string[];
}

export function getStarterQuestions(
  pathname: string,
  context: StarterQuestionContext = {},
): PageAssistantContent {
  const symbol = context.symbol?.toUpperCase();
  if (symbol) {
    return {
      label: `Context: ${symbol}`,
      description: `Ask about ${symbol}'s current forecast, models, metrics, or charts.`,
      questions: [
        `What does ${symbol}'s forecast mean?`,
        `Which model performed best for ${symbol}?`,
        `How did ${symbol}'s best principal model perform?`,
        `Why do ${symbol}'s three model forecasts differ?`,
        `What does the Backtest chart show for ${symbol}?`,
      ],
    };
  }

  const pages: Record<string, PageAssistantContent> = {
    "/": {
      label: "Context: Market Overview",
      description: "Ask about the current dashboard and how to interpret next-session estimates.",
      questions: ["What does ForecastPH predict today?", "Which companies have the largest expected changes?", "How should I read the next-day forecast?", "How accurate are these forecasts?", "What does ForecastPH use to make predictions?"],
    },
    "/companies": {
      label: "Context: Companies Directory",
      description: "Compare the 15 tracked companies using current operational forecasts.",
      questions: ["Which company has the largest forecasted increase?", "Which company has the smallest expected change?", "How can I compare these companies?", "What does Expected Change mean?", "Which models are used?"],
    },
    "/watchlist": {
      label: "Context: My Watchlist",
      description: context.watchlistCount
        ? `Ask about the ${context.watchlistCount} companies pinned in this browser.`
        : "Pin companies to compare their current forecasts here.",
      questions: context.watchlistCount
        ? ["Summarize my watchlist.", "Which pinned company has the largest expected increase?", "Which pinned company has the lowest RMSE?", "Where do the models disagree most?", "Explain the forecasts in my watchlist."]
        : ["How do I add a company to my watchlist?", "What can Ask AI compare in a watchlist?", "What does Expected Change mean?", "What does RMSE mean?"],
    },
    "/compare": {
      label: "Context: Models",
      description: "Ask about current model results, evaluation metrics, and the benchmark.",
      questions: ["Which model wins most often?", "What do RMSE, MAE, MASE, and R² mean?", "Why is Naive included?", "Which model performs best for BPI?", "How are models compared?"],
    },
    "/learn-stocks": {
      label: "Context: Learn Stocks",
      description: "Ask for beginner-friendly explanations of PSE and forecasting concepts.",
      questions: ["What is a stock?", "What are PSE trading hours?", "What does closing price mean?", "What is a forecast?", "How should beginners use ForecastPH?"],
    },
    "/about": {
      label: "Context: About ForecastPH",
      description: "Ask about ForecastPH's objective, architecture, methods, and limitations.",
      questions: ["How does ForecastPH work?", "What models does ForecastPH use?", "What are the project limitations?", "What data does ForecastPH use?", "Is ForecastPH financial advice?"],
    },
  };
  pages["/learn"] = pages["/learn-stocks"];
  return pages[pathname] ?? pages["/"];
}
