import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  COMPANY_TOOLTIPS,
  type CompanyTooltipId,
} from "@/lib/tooltipContent";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SRC_DIR = path.resolve(__dirname, "../..");

const REMOVED_COMPANY_LIST_TOOLTIP_IDS = [
  "filter-sector",
  "card-ticker",
  "card-change-badge",
  "card-forecasted-close",
  "card-forecast-date",
  "card-sector-tag",
  "card-watchlist",
] as const;

const EXPECTED_DETAIL_TOOLTIP_IDS: CompanyTooltipId[] = [
  // /companies/[ticker] (29)
  // Header / Controls (3)
  "detail-data-asof",
  "detail-forecast-for",
  "detail-view-mode",
  // Stat cards (4)
  "metric-prev-close",
  "metric-forecast-close",
  "metric-expected-change",
  "metric-best-model",
  // Model forecast cards (3)
  "forecast-arima",
  "forecast-lagreg",
  "forecast-lstm",
  // Historical OHLCV (4)
  "chart-ohlcv-title",
  "chart-ohlcv-period",
  "chart-ohlcv-series",
  "chart-ohlcv-legend",
  // Next-day prediction (3)
  "chart-nextday-title",
  "chart-nextday-presets",
  "chart-nextday-legend",
  // Predicted vs actual (3)
  "chart-pva-badges",
  "chart-pva-banner",
  "chart-pva-info",
  // Leaderboard (7)
  "lb-title",
  "lb-rmse",
  "lb-mae",
  "lb-mase",
  "lb-rsquared",
  "lb-selected",
  "lb-benchmark",
  // Error charts (2)
  "chart-error-time",
  "chart-error-dist",
];

test("Tooltip Registry - Exactly 29 unique active IDs are present and registered", () => {
  const registeredKeys = Object.keys(COMPANY_TOOLTIPS);
  assert.strictEqual(
    registeredKeys.length,
    29,
    `Expected exactly 29 active tooltips in registry, found ${registeredKeys.length}`
  );

  for (const id of EXPECTED_DETAIL_TOOLTIP_IDS) {
    assert.ok(
      id in COMPANY_TOOLTIPS,
      `Expected detail tooltip ID "${id}" is missing from COMPANY_TOOLTIPS`
    );
  }
});

test("Tooltip Registry - All 7 removed Company List tooltips are absent from registry", () => {
  for (const id of REMOVED_COMPANY_LIST_TOOLTIP_IDS) {
    assert.ok(
      !(id in COMPANY_TOOLTIPS),
      `Removed tooltip ID "${id}" must NOT be present in COMPANY_TOOLTIPS registry`
    );
  }
});

test("Company List Cleanup - Zero tooltips rendered in CompanyGrid and CompanyCard", () => {
  const companyListFiles = [
    path.join(SRC_DIR, "components/CompanyGrid.tsx"),
    path.join(SRC_DIR, "components/CompanyCard.tsx"),
  ];

  let combinedCompanyListContent = "";
  for (const filePath of companyListFiles) {
    assert.ok(fs.existsSync(filePath), `File must exist: ${filePath}`);
    const content = fs.readFileSync(filePath, "utf-8");
    combinedCompanyListContent += "\n" + content;

    // Must not import or instantiate InfoTooltip
    assert.ok(
      !content.includes("InfoTooltip"),
      `File ${path.basename(filePath)} must not reference or render InfoTooltip`
    );
  }

  // Ensure none of the 7 removed IDs appear anywhere in company list rendering
  for (const id of REMOVED_COMPANY_LIST_TOOLTIP_IDS) {
    assert.ok(
      !combinedCompanyListContent.includes(`"${id}"`) &&
        !combinedCompanyListContent.includes(`'${id}'`),
      `Removed tooltip ID "${id}" must not exist in Company List component code`
    );
  }
});

test("Tooltip Registry - All 29 active entries have non-empty concise title and body", () => {
  for (const [id, item] of Object.entries(COMPANY_TOOLTIPS)) {
    assert.ok(item.title, `Tooltip "${id}" must have a title`);
    assert.ok(item.body, `Tooltip "${id}" must have a body`);

    assert.ok(
      item.title.trim().length > 0,
      `Tooltip "${id}" title should not be whitespace only`
    );
    assert.ok(
      item.body.trim().length > 0,
      `Tooltip "${id}" body should not be whitespace only`
    );

    // Verify concise lengths: titles under 50 chars, body under 250 chars (1-2 sentences)
    assert.ok(
      item.title.length <= 50,
      `Tooltip "${id}" title too long (${item.title.length} chars): "${item.title}"`
    );
    assert.ok(
      item.body.length <= 250,
      `Tooltip "${id}" body too long (${item.body.length} chars): "${item.body}"`
    );
  }
});

test("Methodological Correctness - MASE definition guardrails", () => {
  const mase = COMPANY_TOOLTIPS["lb-mase"];
  assert.ok(mase, "lb-mase must be present");
  const body = mase.body.toLowerCase();

  // Must reference development-series one-step scale
  assert.ok(
    body.includes("development-series") || body.includes("one-step"),
    "MASE tooltip must reference development-series one-step error scale"
  );

  // Must explicitly state that below 1 does not automatically mean beating the evaluated Naive benchmark on holdout
  assert.ok(
    body.includes("does not automatically mean") && body.includes("naive"),
    "MASE tooltip must note that values < 1 do not automatically mean beating the evaluated Naive benchmark"
  );
});

test("Methodological Correctness - Holdout R² definition guardrails", () => {
  const rsquared = COMPANY_TOOLTIPS["lb-rsquared"];
  assert.ok(rsquared, "lb-rsquared must be present");
  const body = rsquared.body.toLowerCase();

  // Must note that it is not percentage accuracy
  assert.ok(
    body.includes("not percentage accuracy"),
    "Holdout R² tooltip must clarify that it is not percentage accuracy"
  );

  // Must note that it can be negative
  assert.ok(
    body.includes("can be negative"),
    "Holdout R² tooltip must clarify that it can be negative"
  );
});

test("Methodological Correctness - Naive benchmark definition guardrails", () => {
  const naive = COMPANY_TOOLTIPS["lb-benchmark"];
  assert.ok(naive, "lb-benchmark must be present");
  const body = naive.body.toLowerCase();

  // Must clarify it is a benchmark and not a fourth principal production model
  assert.ok(
    body.includes("benchmark") && body.includes("not a"),
    "Naive tooltip must clarify it is a benchmark, not a principal production model"
  );
});

test("Methodological Correctness - Principal model selection criteria", () => {
  const bestModel = COMPANY_TOOLTIPS["metric-best-model"];
  const lbSelected = COMPANY_TOOLTIPS["lb-selected"];
  assert.ok(bestModel, "metric-best-model must be present");
  assert.ok(lbSelected, "lb-selected must be present");

  assert.ok(
    bestModel.body.includes("RMSE") && bestModel.body.includes("lowest"),
    "metric-best-model must mention lowest RMSE"
  );
  assert.ok(
    lbSelected.body.includes("RMSE") && lbSelected.body.includes("lowest"),
    "lb-selected must mention lowest RMSE"
  );
});

test("Frontend Integration - All 29 detail tooltip IDs are integrated on company detail view", () => {
  const detailFiles = [
    path.join(SRC_DIR, "components/StatCard.tsx"),
    path.join(SRC_DIR, "components/charts/HistoryChart.tsx"),
    path.join(SRC_DIR, "components/charts/NextDayPredictionChart.tsx"),
    path.join(SRC_DIR, "components/company/CompanyDetailView.tsx"),
  ];

  let combinedContent = "";
  for (const filePath of detailFiles) {
    assert.ok(fs.existsSync(filePath), `Component file must exist: ${filePath}`);
    combinedContent += "\n" + fs.readFileSync(filePath, "utf-8");
  }

  for (const id of EXPECTED_DETAIL_TOOLTIP_IDS) {
    const hasLiteralReference =
      combinedContent.includes(`"${id}"`) || combinedContent.includes(`'${id}'`);
    assert.ok(
      hasLiteralReference,
      `Detail tooltip ID "${id}" is not rendered in any company detail component!`
    );
  }
});
