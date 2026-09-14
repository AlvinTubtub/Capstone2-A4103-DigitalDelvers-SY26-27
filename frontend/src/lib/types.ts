export type Direction = "bullish" | "bearish";

export interface CompanySummary {
  symbol: string;
  name: string;
  sector: string;
  latestClose: number;
  predictedClose: number;
  pctChange: number;
  direction: Direction;
  bestModel: string;
  confidence?: number;
  forecastDate?: string;
}

export interface OhlcvPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ModelMetric {
  rmse: string | number;
  mae: string | number;
  mase: string | number;
  r2: string | number;
  ljung_box_pvalue?: string | number;
}

export interface EvaluationMetadata {
  fullSessionCount: number;
  fullStartDate: string;
  fullEndDate: string;
  displayedSessionCount: number;
  displayedStartDate: string;
  displayedEndDate: string;
  displayWindowLimit: 60;
  metricsScope: "complete_aligned_evaluation";
  statisticalTestsScope: "complete_aligned_evaluation";
}

export interface CompanyEvaluationMetrics {
  metrics: Record<string, ModelMetric>;
  bestModel: string;
  bestPrincipalModel?: string;
  bestEvaluatedMethod?: string;
  bestPrincipalBeatsNaive?: boolean;
  allPrincipalsWorseThanNaive?: boolean;
  evaluationMetadata?: EvaluationMetadata;
}

export interface CompanyDetail {
  symbol: string;
  name: string;
  sector: string;
  previousClose: number;
  predictedClose: number;
  pesoChange: number;
  pctChange: number;
  direction: Direction;
  model: string;
  confidence?: number;
  metrics: Record<string, ModelMetric>;
  nextClose: Record<string, number>;
  ohlcv: OhlcvPoint[];
  backtestDates?: string[];
  backtestActual: number[];
  backtestByModel: Record<string, number[]>;
  productionBacktestDates?: string[];
  productionBacktestActual?: number[];
  productionBacktestByModel?: Record<string, number[]>;
  forecastDate?: string;
  dataAsOf?: string | null;
  inferenceAt?: string | null;
  evaluationMetadata?: EvaluationMetadata;
  bestPrincipalModel?: string;
  bestEvaluatedMethod?: string;
  bestPrincipalBeatsNaive?: boolean;
  allPrincipalsWorseThanNaive?: boolean;
}

export interface DashboardData {
  generatedAt: string;
  forecastDate: string;
  lastRunAt: string | null;
  status: string;
  totalCompanies: number;
  missingCompanies: string[];
  sectors: { name: string; count: number }[];
  marketSummary: { gainers: number; losers: number; unchanged: number };
  topGainer: CompanySummary | null;
  topLoser: CompanySummary | null;
}

export interface MetricsData {
  generatedAt: string;
  forecastDate?: string;
  lastRunAt?: string | null;
  status?: string;
  aggregate: Record<string, { rmse: number; mae: number; mase: number; r2: number }>;
  aggregateStatistic?: "median";
  crossCompany?: {
    companyCount: number;
    selectionBasis: string;
    tiePolicy: string;
    bestEvaluatedMethod: string;
    worstEvaluatedMethod: string;
    methods: Record<string, {
      medianMase: number;
      medianRmseRank: number;
      principalWinCount: number;
      evaluatedWinCount: number;
      beatsNaiveCount: number;
    }>;
  };
  bestModel: string;
  worstModel: string;
  perCompany: Record<string, CompanyEvaluationMetrics>;
  statisticalTests: Record<string, unknown>;
}

export interface LatestData {
  generatedAt: string;
  forecastDate: string;
  lastRunAt: string | null;
  status: string;
}
