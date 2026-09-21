import ModelsDashboard, {
  type ModelPerformanceRow,
  type OperationalModelId,
} from "./ModelsDashboard";
import { getCompanies, getMetrics } from "@/lib/data";
import { resolveCompanyModelReporting } from "@/lib/modelReporting";

const PRINCIPAL_MODELS: OperationalModelId[] = ["lag_reg", "arima", "lstm"];
const ALL_MODELS: OperationalModelId[] = [...PRINCIPAL_MODELS, "naive"];

function numericMetric(value: string | number | undefined): number | null {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export default async function ComparePage() {
  const [companies, metrics] = await Promise.all([getCompanies(), getMetrics()]);

  if (!metrics || companies.length === 0) {
    return <UnavailableState />;
  }

  const rows: ModelPerformanceRow[] = [];
  const evaluationCounts = new Set<number>();
  const evaluationStarts = new Set<string>();
  const evaluationEnds = new Set<string>();
  let evaluationForecasts = 0;
  let completeEvaluationMetadata = true;

  for (const company of companies) {
    const companyEvaluation = metrics.perCompany[company.symbol];
    const companyMetrics = companyEvaluation?.metrics;
    const reporting = companyEvaluation
      ? resolveCompanyModelReporting(companyEvaluation)
      : null;
    if (!companyMetrics || !reporting) return <UnavailableState />;

    const parsedMetrics = Object.fromEntries(
      ALL_MODELS.map((model) => [
        model,
        {
          rmse: numericMetric(companyMetrics[model]?.rmse),
          mae: numericMetric(companyMetrics[model]?.mae),
          mase: numericMetric(companyMetrics[model]?.mase),
          r2: numericMetric(companyMetrics[model]?.r2),
        },
      ]),
    ) as Record<OperationalModelId, Record<"rmse" | "mae" | "mase" | "r2", number | null>>;

    if (ALL_MODELS.some((model) => Object.values(parsedMetrics[model]).some((value) => value === null))) {
      return <UnavailableState />;
    }

    const evaluationMetadata = companyEvaluation.evaluationMetadata;
    if (evaluationMetadata) {
      evaluationCounts.add(evaluationMetadata.fullSessionCount);
      evaluationStarts.add(evaluationMetadata.fullStartDate);
      evaluationEnds.add(evaluationMetadata.fullEndDate);
      evaluationForecasts += evaluationMetadata.fullSessionCount * ALL_MODELS.length;
    } else {
      completeEvaluationMetadata = false;
    }

    rows.push({
      symbol: company.symbol,
      name: company.name,
      metrics: parsedMetrics as ModelPerformanceRow["metrics"],
      ...reporting,
    });
  }

  const commonEvaluationWindow = completeEvaluationMetadata
    && evaluationCounts.size === 1
    && evaluationStarts.size === 1
    && evaluationEnds.size === 1;

  return (
    <ModelsDashboard
      rows={rows.sort((a, b) => a.symbol.localeCompare(b.symbol))}
      evaluationForecasts={completeEvaluationMetadata ? evaluationForecasts : null}
      evaluationCount={commonEvaluationWindow ? [...evaluationCounts][0] : null}
      evaluationStart={commonEvaluationWindow ? [...evaluationStarts][0] : null}
      evaluationEnd={commonEvaluationWindow ? [...evaluationEnds][0] : null}
      evaluationMetadataAvailable={completeEvaluationMetadata}
    />
  );
}

function UnavailableState() {
  return (
    <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
      <h1 className="text-2xl font-bold text-white">Models</h1>
      <p className="mt-2 text-sm text-slate-400">
        Model-performance data is unavailable or incomplete. PSE Pulse will display this
        dashboard after the next successful fresh training run.
      </p>
    </div>
  );
}
