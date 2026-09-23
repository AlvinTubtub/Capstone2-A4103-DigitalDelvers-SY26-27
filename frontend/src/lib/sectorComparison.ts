import { formatNum, formatPeso, formatPct, formatDate } from "./format";
import { resolveCompanyModelReporting, MODEL_LABELS } from "./modelReporting";
import type { CompanyDetail } from "./types";

export const SECTOR_COMPANY_COLORS = [
  { solid: "#3b82f6", name: "Blue" },    // Blue
  { solid: "#f59e0b", name: "Amber" },   // Amber
  { solid: "#8b5cf6", name: "Purple" },  // Purple
];

export interface ReconciledHistory {
  symbol: string;
  name: string;
  selectedModelLabel: string;
  dateMap: Map<string, { actual: number; prediction: number }>;
}

export function reconcileCompanyHistory(company: CompanyDetail): ReconciledHistory {
  const productionDates = company.productionBacktestDates ?? [];
  const productionActual = company.productionBacktestActual ?? [];
  const productionByModel = company.productionBacktestByModel ?? {};
  const productionProvenance = company.productionBacktestProvenance ?? [];

  const hasRealizedProductionHistory =
    productionDates.length > 0 &&
    productionDates.length === productionActual.length &&
    productionDates.length === productionProvenance.length &&
    Object.keys(productionByModel).length === Object.keys(company.backtestByModel).length &&
    Object.values(productionByModel).every(
      (values) => values.length === productionDates.length
    );

  const auditedDates = company.backtestDates ?? [];
  const verifiedProductionDates = hasRealizedProductionHistory ? productionDates : [];
  const verifiedProductionActual = hasRealizedProductionHistory ? productionActual : [];

  const chartDates = [...auditedDates, ...verifiedProductionDates];
  const chartActual = [...(company.backtestActual ?? []), ...verifiedProductionActual];

  const chartByModel = Object.fromEntries(
    Object.entries(company.backtestByModel).map(([model, values]) => [
      model,
      hasRealizedProductionHistory && productionByModel[model]
        ? [...values, ...productionByModel[model]]
        : values,
    ])
  );

  const reporting = resolveCompanyModelReporting({
    metrics: company.metrics,
    bestModel: company.model,
    bestPrincipalModel: company.bestPrincipalModel,
    bestEvaluatedMethod: company.bestEvaluatedMethod,
    bestPrincipalBeatsNaive: company.bestPrincipalBeatsNaive,
    allPrincipalsWorseThanNaive: company.allPrincipalsWorseThanNaive,
  });

  const selectedModelLabel =
    reporting?.bestPrincipalModel ?? company.bestPrincipalModel ?? company.model;

  const predictions = chartByModel[selectedModelLabel] ?? [];

  const dateMap = new Map<string, { actual: number; prediction: number }>();
  chartDates.forEach((date, i) => {
    const act = chartActual[i];
    const pred = predictions[i];
    if (
      date &&
      typeof act === "number" &&
      !isNaN(act) &&
      typeof pred === "number" &&
      !isNaN(pred)
    ) {
      dateMap.set(date, { actual: act, prediction: pred });
    }
  });

  return {
    symbol: company.symbol,
    name: company.name,
    selectedModelLabel,
    dateMap,
  };
}

export function formatShortDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [y, m, d] = dateStr.split("-").map(Number);
      const dt = new Date(y, m - 1, d);
      return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    }
    const dt = new Date(dateStr);
    return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

export function formatFullDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [y, m, d] = dateStr.split("-").map(Number);
      const dt = new Date(y, m - 1, d);
      return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }
    const dt = new Date(dateStr);
    return dt.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return dateStr;
  }
}

export interface AlignedChartRow {
  step: string;
  displayDate: string;
  fullDate: string;
  [key: string]: any;
}

export interface SectorChartDataResult {
  data: AlignedChartRow[];
  commonSessionCount: number;
  totalAvailableSessions: number;
  companiesMeta: Array<{
    symbol: string;
    name: string;
    selectedModelLabel: string;
    color: string;
    firstVisibleActual: number | null;
  }>;
}

export function alignSectorChartData(
  companies: CompanyDetail[],
  mode: "price" | "indexed" = "price"
): SectorChartDataResult {
  if (!companies || companies.length === 0) {
    return { data: [], commonSessionCount: 0, totalAvailableSessions: 0, companiesMeta: [] };
  }

  const reconciledList = companies.map(reconcileCompanyHistory);

  // Find intersecting dates present across all companies
  const first = reconciledList[0];
  const otherHistories = reconciledList.slice(1);

  const intersectingDates: string[] = [];
  first.dateMap.forEach((_, date) => {
    if (otherHistories.every((h) => h.dateMap.has(date))) {
      intersectingDates.push(date);
    }
  });

  intersectingDates.sort(); // YYYY-MM-DD strings sort chronologically
  const totalAvailableSessions = intersectingDates.length;
  // Take latest 60 common sessions
  const alignedDates = intersectingDates.slice(-60);

  // Determine each company's first visible actual price
  const companiesMeta = reconciledList.map((rec, idx) => {
    const firstDate = alignedDates[0];
    const firstPoint = firstDate ? rec.dateMap.get(firstDate) : undefined;
    const firstVisibleActual = firstPoint ? firstPoint.actual : null;
    const color = SECTOR_COMPANY_COLORS[idx % SECTOR_COMPANY_COLORS.length].solid;
    return {
      symbol: rec.symbol,
      name: rec.name,
      selectedModelLabel: rec.selectedModelLabel,
      color,
      firstVisibleActual,
    };
  });

  const data: AlignedChartRow[] = alignedDates.map((date) => {
    const row: AlignedChartRow = {
      step: date,
      displayDate: formatShortDate(date),
      fullDate: formatFullDate(date),
      raw: {},
    };

    reconciledList.forEach((rec, idx) => {
      const meta = companiesMeta[idx];
      const point = rec.dateMap.get(date)!;
      const basePrice = meta.firstVisibleActual;

      const actualPrice = point.actual;
      const predPrice = point.prediction;

      const actualVal =
        mode === "indexed" && basePrice && basePrice > 0
          ? (actualPrice / basePrice) * 100
          : actualPrice;

      const predVal =
        mode === "indexed" && basePrice && basePrice > 0
          ? (predPrice / basePrice) * 100
          : predPrice;

      row[`actual_${rec.symbol}`] = actualVal;
      row[`pred_${rec.symbol}`] = predVal;

      row.raw[rec.symbol] = {
        actualPrice,
        predPrice,
        diff: predPrice - actualPrice,
        actualVal,
        predVal,
        modelName: rec.selectedModelLabel,
      };
    });

    return row;
  });

  return {
    data,
    commonSessionCount: alignedDates.length,
    totalAvailableSessions,
    companiesMeta,
  };
}

export interface SectorSnapshotData {
  selectedCount: number;
  largestMove: {
    symbol: string;
    pctChange: number;
    pesoChange: number;
    direction: "bullish" | "bearish";
  } | null;
  beatingNaiveCount: number;
}

export function computeSectorSnapshot(companies: CompanyDetail[]): SectorSnapshotData {
  if (!companies || companies.length === 0) {
    return { selectedCount: 0, largestMove: null, beatingNaiveCount: 0 };
  }

  let maxAbs = -1;
  let largestMove: SectorSnapshotData["largestMove"] = null;
  let beatingCount = 0;

  companies.forEach((c) => {
    const abs = Math.abs(c.pctChange ?? 0);
    if (abs > maxAbs) {
      maxAbs = abs;
      largestMove = {
        symbol: c.symbol,
        pctChange: c.pctChange ?? 0,
        pesoChange: c.pesoChange ?? (c.predictedClose - c.previousClose),
        direction: c.direction ?? (c.pctChange >= 0 ? "bullish" : "bearish"),
      };
    }

    const reporting = resolveCompanyModelReporting({
      metrics: c.metrics,
      bestModel: c.model,
      bestPrincipalModel: c.bestPrincipalModel,
      bestEvaluatedMethod: c.bestEvaluatedMethod,
      bestPrincipalBeatsNaive: c.bestPrincipalBeatsNaive,
      allPrincipalsWorseThanNaive: c.allPrincipalsWorseThanNaive,
    });

    const beatsNaive =
      reporting?.bestPrincipalBeatsNaive ??
      c.bestPrincipalBeatsNaive ??
      false;

    if (beatsNaive) {
      beatingCount++;
    }
  });

  return {
    selectedCount: companies.length,
    largestMove,
    beatingNaiveCount: beatingCount,
  };
}

export interface CompanyMetricsRowItem {
  symbol: string;
  name: string;
  previousClose: number;
  predictedClose: number;
  expectedChange: number;
  expectedChangePct: number;
  selectedModel: string;
  bestEvaluatedMethod: string;
  rmse: string | number;
  mae: string | number;
  mase: string | number;
  r2: string | number;
  beatsNaive: boolean;
  forecastDate?: string;
}

export function getCompanyMetricsRowData(company: CompanyDetail): CompanyMetricsRowItem {
  const reporting = resolveCompanyModelReporting({
    metrics: company.metrics,
    bestModel: company.model,
    bestPrincipalModel: company.bestPrincipalModel,
    bestEvaluatedMethod: company.bestEvaluatedMethod,
    bestPrincipalBeatsNaive: company.bestPrincipalBeatsNaive,
    allPrincipalsWorseThanNaive: company.allPrincipalsWorseThanNaive,
  });

  const selectedModel =
    reporting?.bestPrincipalModel ?? company.bestPrincipalModel ?? company.model;

  const modelId =
    Object.entries(MODEL_LABELS).find(([_, label]) => label === selectedModel)?.[0] ?? "arima";

  const metrics = company.metrics?.[modelId] ?? {
    rmse: "--",
    mae: "--",
    mase: "--",
    r2: "--",
  };

  const beatsNaive =
    reporting?.bestPrincipalBeatsNaive ?? company.bestPrincipalBeatsNaive ?? false;

  const previousClose = company.previousClose;
  const predictedClose = company.predictedClose;
  const expectedChange = company.pesoChange ?? (predictedClose - previousClose);
  const expectedChangePct = company.pctChange;

  return {
    symbol: company.symbol,
    name: company.name,
    previousClose,
    predictedClose,
    expectedChange,
    expectedChangePct,
    selectedModel,
    bestEvaluatedMethod: reporting?.bestEvaluatedMethod ?? company.bestEvaluatedMethod ?? "--",
    rmse: metrics.rmse,
    mae: metrics.mae,
    mase: metrics.mase,
    r2: metrics.r2,
    beatsNaive,
    forecastDate: company.forecastDate,
  };
}
