import test from "node:test";
import assert from "node:assert/strict";
import {
  CORE_EDUCATIONAL_CONCEPTS,
  GLOSSARY_TERMS,
  LEARNING_PATH_STEPS,
  BROKER_DIRECTORY,
  PSE_MARKET_SCHEDULE,
} from "@/lib/learnData";
import {
  HOME_SECTOR_CARDS,
  HOME_BEGINNER_GUIDE_CARDS,
  COMPANY_FIELD_EXPLANATIONS,
  COMPANY_DETAIL_CHART_EXPLANATIONS,
  WATCHLIST_EXPLANATIONS,
  COMPARE_EXPLANATIONS,
  ABOUT_EXPLANATIONS,
} from "@/lib/siteContent";
import {
  buildContextForRequest,
  buildHomeContext,
  buildCompaniesContext,
  buildCompanyContext,
  buildWatchlistContext,
  buildCompareContext,
  buildLearnStocksContext,
  buildAboutContext,
  buildGeneralContext,
} from "@/lib/ai/context";
import { buildSystemPrompt } from "@/lib/ai/prompt";

test("Educational Glossary Terms - Covers required foundational & forecasting terms", () => {
  const terms = GLOSSARY_TERMS.map((t) => t.term);

  // 13 Required financial fundamentals
  const requiredFundamentals = [
    "Stock",
    "Share",
    "Shareholder",
    "Stockholder",
    "Dividend",
    "Cash Dividend",
    "Stock Dividend",
    "Common Stock",
    "Preferred Stock",
    "Dividend Yield",
    "Capital Gain",
    "Capital Loss",
    "Market Capitalization",
  ];

  for (const term of requiredFundamentals) {
    assert.ok(terms.includes(term), `GLOSSARY_TERMS must include foundational term: "${term}"`);
    const entry = GLOSSARY_TERMS.find((t) => t.term === term);
    assert.ok(entry?.shortDef && entry.shortDef.length > 5, `Term "${term}" must have meaningful shortDef`);
    assert.ok(entry?.detailedDef && entry.detailedDef.length > 10, `Term "${term}" must have meaningful detailedDef`);
    assert.strictEqual(entry?.category, "market", `Term "${term}" must have category "market"`);
  }

  // Required forecasting models and evaluation metrics
  const requiredForecasting = [
    "Lag-Informed Regression",
    "ARIMA",
    "LSTM",
    "Naive Benchmark",
    "RMSE (Root Mean Squared Error)",
    "MAE (Mean Absolute Error)",
    "MASE (Mean Absolute Scaled Error)",
    "Holdout R² (Supplementary)",
    "Backtest",
    "Forecasted Close",
  ];

  for (const term of requiredForecasting) {
    assert.ok(terms.includes(term), `GLOSSARY_TERMS must include forecasting term: "${term}"`);
    const entry = GLOSSARY_TERMS.find((t) => t.term === term);
    assert.ok(entry?.shortDef && entry.shortDef.length > 5, `Term "${term}" must have meaningful shortDef`);
    assert.ok(entry?.detailedDef && entry.detailedDef.length > 10, `Term "${term}" must have meaningful detailedDef`);
    assert.strictEqual(entry?.category, "forecastph", `Term "${term}" must have category "forecastph"`);
  }
});

test("Core Educational Concepts - Structured dictionary accessibility", () => {
  // Foundations
  const { foundations, modelsAndForecasting, metrics } = CORE_EDUCATIONAL_CONCEPTS;

  assert.ok(foundations.stock, "stock concept must be present");
  assert.ok(foundations.share, "share concept must be present");
  assert.ok(foundations.shareholder, "shareholder concept must be present");
  assert.ok(foundations.stockholder, "stockholder concept must be present");
  assert.ok(foundations.dividend, "dividend concept must be present");
  assert.ok(foundations.cashDividend, "cashDividend concept must be present");
  assert.ok(foundations.stockDividend, "stockDividend concept must be present");
  assert.ok(foundations.commonStock, "commonStock concept must be present");
  assert.ok(foundations.preferredStock, "preferredStock concept must be present");
  assert.ok(foundations.dividendYield, "dividendYield concept must be present");
  assert.ok(foundations.capitalGain, "capitalGain concept must be present");
  assert.ok(foundations.capitalLoss, "capitalLoss concept must be present");
  assert.ok(foundations.marketCapitalization, "marketCapitalization concept must be present");

  // Models & Forecasting
  assert.ok(modelsAndForecasting.forecastedClose, "forecastedClose concept must be present");
  assert.ok(modelsAndForecasting.backtesting, "backtesting concept must be present");
  assert.ok(modelsAndForecasting.lagInformedRegression, "lagInformedRegression concept must be present");
  assert.ok(modelsAndForecasting.arima, "arima concept must be present");
  assert.ok(modelsAndForecasting.lstm, "lstm concept must be present");
  assert.ok(modelsAndForecasting.naiveBenchmark, "naiveBenchmark concept must be present");

  // Metrics
  assert.ok(metrics.rmse, "rmse metric concept must be present");
  assert.ok(metrics.mae, "mae metric concept must be present");
  assert.ok(metrics.mase, "mase metric concept must be present");
  assert.ok(metrics.holdoutR2, "holdoutR2 metric concept must be present");
});

test("Required 12 Educational Questions - Grounding mapping verification", () => {
  const targetQuestions = [
    { q: "what are dividends?", key: "dividend", category: "foundations" },
    { q: "ano ang dividends?", key: "dividend", category: "foundations" },
    { q: "what is a stock?", key: "stock", category: "foundations" },
    { q: "ano ang stock?", key: "stock", category: "foundations" },
    { q: "what is a shareholder?", key: "shareholder", category: "foundations" },
    { q: "primary stockholders?", key: "stockholder", category: "foundations" },
    { q: "what is dividend yield?", key: "dividendYield", category: "foundations" },
    { q: "what is ARIMA?", key: "arima", category: "modelsAndForecasting" },
    { q: "what is LSTM?", key: "lstm", category: "modelsAndForecasting" },
    { q: "what is RMSE?", key: "rmse", category: "metrics" },
    { q: "what is MASE?", key: "mase", category: "metrics" },
    { q: "what is backtesting?", key: "backtesting", category: "modelsAndForecasting" },
  ];

  for (const item of targetQuestions) {
    const conceptDict = (CORE_EDUCATIONAL_CONCEPTS as Record<string, Record<string, string>>)[item.category];
    assert.ok(conceptDict && conceptDict[item.key], `Query "${item.q}" must map to concept key "${item.key}"`);
    assert.ok(conceptDict[item.key].length > 20, `Definition for "${item.key}" must be detailed and educational`);
  }
});

test("System Prompt Grounding - Rules classification and fallback semantics", () => {
  const dummyContext = JSON.stringify({
    page: "test",
    sharedEducationalConcepts: CORE_EDUCATIONAL_CONCEPTS,
  });
  const prompt = buildSystemPrompt(dummyContext);

  // 1. Rule 1: General Educational Questions rule
  assert.ok(
    prompt.includes("1. GENERAL EDUCATIONAL QUESTIONS:"),
    "Prompt must include rule for General Educational Questions",
  );
  assert.ok(
    prompt.includes("Do NOT respond with \"That value is not available in the current PSE Pulse data.\" for general educational questions"),
    "Prompt must forbid false-negative fallback on general educational questions",
  );
  assert.ok(
    prompt.includes("primary stockholders?"),
    "Prompt must explicitly classify generic queries like 'primary stockholders?' as educational",
  );
  assert.ok(
    prompt.includes("ano ang dividends?"),
    "Prompt must support Filipino/Taglish queries like 'ano ang dividends?'",
  );

  // 2. Rule 2: Current PSE Pulse Operational Facts rule
  assert.ok(
    prompt.includes("2. CURRENT PSE PULSE OPERATIONAL FACTS:"),
    "Prompt must include rule for Current PSE Pulse Operational Facts",
  );

  // 3. Rule 3: Refusal on Unsupported Company-Specific Facts
  assert.ok(
    prompt.includes("3. UNSUPPORTED COMPANY-SPECIFIC FACTS:"),
    "Prompt must include rule for Unsupported Company-Specific Facts",
  );
  assert.ok(
    prompt.includes("That value is not available in the current PSE Pulse data."),
    "Prompt must contain exact required refusal string for missing company-specific facts",
  );
  assert.ok(
    prompt.includes("What is BPI's latest dividend?"),
    "Prompt must explicitly cite company dividend question example",
  );
  assert.ok(
    prompt.includes("Who are ALI's current major shareholders?"),
    "Prompt must explicitly cite company shareholder question example",
  );
  assert.ok(
    prompt.includes("What is GLO's dividend yield?"),
    "Prompt must explicitly cite company dividend yield question example",
  );
  assert.ok(
    prompt.includes("What is JFC's P/E ratio?"),
    "Prompt must explicitly cite company P/E ratio question example",
  );

  // 4. Model evaluations and metrics definitions
  assert.ok(prompt.includes("Lag-Informed Regression"), "Prompt must mention Lag-Informed Regression");
  assert.ok(prompt.includes("ARIMA"), "Prompt must mention ARIMA");
  assert.ok(prompt.includes("LSTM"), "Prompt must mention LSTM");
  assert.ok(prompt.includes("Naive benchmark"), "Prompt must mention Naive benchmark");
  assert.ok(prompt.includes("RMSE"), "Prompt must mention RMSE");
  assert.ok(prompt.includes("MASE"), "Prompt must mention MASE");
});

test("Website Site Content Modules - Valid and non-empty", () => {
  assert.ok(HOME_SECTOR_CARDS.length >= 5, "Home sector cards must be populated");
  assert.ok(HOME_BEGINNER_GUIDE_CARDS.length === 3, "Home beginner guide cards must have 3 steps");
  assert.ok(COMPANY_FIELD_EXPLANATIONS.predictedClose, "Company field explanations must exist");
  assert.ok(COMPANY_DETAIL_CHART_EXPLANATIONS.historicalOhlcv, "Company chart explanations must exist");
  assert.ok(WATCHLIST_EXPLANATIONS.purpose, "Watchlist explanations must exist");
  assert.ok(COMPARE_EXPLANATIONS.rules, "Compare explanations must exist");
  assert.ok(ABOUT_EXPLANATIONS.projectTitle, "About explanations must exist");
  assert.ok(LEARNING_PATH_STEPS.length === 4, "Learning path steps must have 4 steps");
  assert.ok(BROKER_DIRECTORY.length >= 6, "Broker directory must have entries");
  assert.ok(PSE_MARKET_SCHEDULE.length >= 6, "Market schedule must have phases");
});

test("Route Context Generation - All 7 routes contain operational facts and educational concepts", async () => {
  // 1. Home route (/)
  const homeContextStr = await buildHomeContext();
  const homeParsed = JSON.parse(homeContextStr);
  assert.strictEqual(homeParsed.page, "home");
  assert.ok(homeParsed.sharedEducationalConcepts.foundations.stock, "Home must include shared educational concepts");
  assert.ok(homeParsed.pageInformationalContent.supportedSectors, "Home must include pageInformationalContent supportedSectors");
  assert.ok(homeParsed.pageInformationalContent.beginnerGuideSteps, "Home must include beginnerGuideSteps");
  assert.ok(homeParsed.operationalData.trackedCompanyCount, "Home must include operational data trackedCompanyCount");

  // 2. Companies route (/companies)
  const companiesContextStr = await buildCompaniesContext();
  const companiesParsed = JSON.parse(companiesContextStr);
  assert.strictEqual(companiesParsed.page, "companies");
  assert.ok(companiesParsed.sharedEducationalConcepts.foundations.dividend, "Companies must include shared educational concepts");
  assert.ok(companiesParsed.pageInformationalContent.fieldExplanations, "Companies must include field explanations");

  // 3. Company Detail route (/companies/BPI)
  const companyContextStr = await buildCompanyContext("BPI");
  const companyParsed = JSON.parse(companyContextStr);
  assert.strictEqual(companyParsed.page, "company");
  assert.strictEqual(companyParsed.operationalData.company.ticker, "BPI");
  assert.ok(companyParsed.operationalData.company.description, "Company detail must include company description");
  assert.ok(companyParsed.sharedEducationalConcepts.modelsAndForecasting.arima, "Company detail must include shared educational concepts");
  assert.ok(companyParsed.pageInformationalContent.chartExplanations, "Company detail must include chart explanations");

  // 4. Watchlist route (/watchlist)
  const watchlistContextStr = await buildWatchlistContext(["BPI", "ALI"]);
  const watchlistParsed = JSON.parse(watchlistContextStr);
  assert.strictEqual(watchlistParsed.page, "watchlist");
  assert.ok(watchlistParsed.sharedEducationalConcepts.foundations.marketCapitalization, "Watchlist must include educational concepts");
  assert.ok(watchlistParsed.pageInformationalContent.watchlistGuide.purpose, "Watchlist must include pageInformationalContent");

  // 5. Compare route (/compare)
  const compareContextStr = await buildCompareContext();
  const compareParsed = JSON.parse(compareContextStr);
  assert.strictEqual(compareParsed.page, "compare");
  assert.ok(compareParsed.sharedEducationalConcepts.metrics.mase, "Compare must include shared educational concepts");
  assert.ok(compareParsed.pageInformationalContent.rulesExplained, "Compare must include rulesExplained");

  // 6. Learn Stocks route (/learn-stocks)
  const learnContextStr = await buildLearnStocksContext();
  const learnParsed = JSON.parse(learnContextStr);
  assert.strictEqual(learnParsed.page, "learn-stocks");
  assert.ok(learnParsed.pageInformationalContent.glossary, "Learn Stocks must include glossary object");
  assert.ok(Object.keys(learnParsed.pageInformationalContent.glossary).length >= 25, "Learn Stocks must have comprehensive glossary terms");
  assert.ok(learnParsed.sharedEducationalConcepts.foundations.shareholder, "Learn Stocks must include shared educational concepts");

  // 7. About route (/about)
  const aboutContextStr = await buildAboutContext();
  const aboutParsed = JSON.parse(aboutContextStr);
  assert.strictEqual(aboutParsed.page, "about");
  assert.ok(aboutParsed.sharedEducationalConcepts.modelsAndForecasting.lstm, "About must include shared educational concepts");
  assert.ok(aboutParsed.pageInformationalContent.lifecyclePipeline, "About must include lifecycle pipeline");
  assert.ok(aboutParsed.pageInformationalContent.limitations, "About must include limitations");

  // General Context fallback
  const generalContextStr = await buildGeneralContext();
  const generalParsed = JSON.parse(generalContextStr);
  assert.strictEqual(generalParsed.page, "general");
  assert.ok(generalParsed.sharedEducationalConcepts.foundations.stock, "General must include shared educational concepts");

  // buildContextForRequest router test
  const routedHome = await buildContextForRequest({ route: "/" });
  assert.strictEqual(JSON.parse(routedHome).page, "home");

  const routedBPI = await buildContextForRequest({ route: "/companies/BPI", symbol: "BPI" });
  assert.strictEqual(JSON.parse(routedBPI).page, "company");

  const routedCompare = await buildContextForRequest({ route: "/compare" });
  assert.strictEqual(JSON.parse(routedCompare).page, "compare");

  const routedLearn = await buildContextForRequest({ route: "/learn-stocks" });
  assert.strictEqual(JSON.parse(routedLearn).page, "learn-stocks");
});

test("Context Backwards Compatibility - Preserves facts property alongside operationalData", async () => {
  const homeContext = await buildHomeContext();
  const parsed = JSON.parse(homeContext);

  assert.ok(parsed.facts, "Must preserve legacy .facts property for backward compatibility");
  assert.ok(parsed.operationalData, "Must provide .operationalData property");
  assert.ok(parsed.pageInformationalContent, "Must provide .pageInformationalContent property");
  assert.ok(parsed.sharedEducationalConcepts, "Must provide .sharedEducationalConcepts property");
  assert.deepStrictEqual(parsed.facts, parsed.operationalData, ".facts and .operationalData must reference same operational payload");
});

test("Real Route Prompt Generation - Successfully generates full prompts for all routes", async () => {
  const testRoutes = ["/", "/companies", "/companies/BPI", "/watchlist", "/compare", "/learn-stocks", "/about"];

  for (const route of testRoutes) {
    const context = await buildContextForRequest({ route, symbol: route.includes("/companies/") ? "BPI" : undefined });
    const prompt = buildSystemPrompt(context);

    assert.ok(prompt.length > 500, `Generated prompt for route "${route}" must be substantial in length`);
    assert.ok(prompt.includes("You are PSE Pulse Ask AI"), `Prompt for "${route}" must include role definition`);
    assert.ok(prompt.includes("QUESTION CLASSIFICATION & GROUNDING RULES:"), `Prompt for "${route}" must include grounding rules`);
    assert.ok(prompt.includes("That value is not available in the current PSE Pulse data."), `Prompt for "${route}" must include safety refusal`);
    assert.ok(prompt.includes(context), `Prompt for "${route}" must include raw route context`);
  }
});

