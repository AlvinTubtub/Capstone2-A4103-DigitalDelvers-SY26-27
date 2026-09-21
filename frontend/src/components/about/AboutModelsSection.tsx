import ModelsDashboard, {
  type ModelPerformanceRow,
  type OperationalModelId,
} from "@/app/compare/ModelsDashboard";
import { getCompanies, getMetrics } from "@/lib/data";
import { resolveCompanyModelReporting } from "@/lib/modelReporting";

const PRINCIPAL_MODELS: OperationalModelId[] = ["lag_reg", "arima", "lstm"];
const ALL_MODELS: OperationalModelId[] = [...PRINCIPAL_MODELS, "naive"];

function numericMetric(value: string | number | undefined): number | null {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export default async function AboutModelsSection() {
  const [companies, metrics] = await Promise.all([getCompanies(), getMetrics()]);

  if (!metrics || companies.length === 0) {
    return (
      <section id="model-performance" className="space-y-8 sm:space-y-10 pt-2 sm:pt-4 scroll-mt-24">
        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Historical Evaluation
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Model Performance & Comparison
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed max-w-3xl">
            Compare the historical chronological out-of-sample performance of
            Lag-Informed Regression, ARIMA, LSTM, and the Naive benchmark across the
            tracked PSE companies.
          </p>
        </div>
        <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
          <h3 className="text-xl font-bold text-white">Models</h3>
          <p className="mt-2 text-sm text-slate-400">
            Model-performance data is unavailable or incomplete. PSE Pulse will display this
            dashboard after the next successful fresh training run.
          </p>
        </div>
      </section>
    );
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
    if (!companyMetrics || !reporting) {
      return (
        <section id="model-performance" className="space-y-8 sm:space-y-10 pt-2 sm:pt-4 scroll-mt-24">
          <div className="space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
              Historical Evaluation
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Model Performance & Comparison
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed max-w-3xl">
              Compare the historical chronological out-of-sample performance of
              Lag-Informed Regression, ARIMA, LSTM, and the Naive benchmark across the
              tracked PSE companies.
            </p>
          </div>
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h3 className="text-xl font-bold text-white">Models</h3>
            <p className="mt-2 text-sm text-slate-400">
              Model-performance data is unavailable or incomplete. PSE Pulse will display this
              dashboard after the next successful fresh training run.
            </p>
          </div>
        </section>
      );
    }

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

    if (
      ALL_MODELS.some((model) =>
        Object.values(parsedMetrics[model]).some((value) => value === null),
      )
    ) {
      return (
        <section id="model-performance" className="space-y-8 sm:space-y-10 pt-2 sm:pt-4 scroll-mt-24">
          <div className="space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
              Historical Evaluation
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Model Performance & Comparison
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed max-w-3xl">
              Compare the historical chronological out-of-sample performance of
              Lag-Informed Regression, ARIMA, LSTM, and the Naive benchmark across the
              tracked PSE companies.
            </p>
          </div>
          <div className="rounded-2xl border border-dark-border bg-dark-card p-6">
            <h3 className="text-xl font-bold text-white">Models</h3>
            <p className="mt-2 text-sm text-slate-400">
              Model-performance data is unavailable or incomplete. PSE Pulse will display this
              dashboard after the next successful fresh training run.
            </p>
          </div>
        </section>
      );
    }

    const evaluationMetadata = companyEvaluation.evaluationMetadata;
    if (evaluationMetadata) {
      evaluationCounts.add(evaluationMetadata.fullSessionCount);
      evaluationStarts.add(evaluationMetadata.fullStartDate);
      evaluationEnds.add(evaluationMetadata.fullEndDate);
      evaluationForecasts +=
        evaluationMetadata.fullSessionCount * ALL_MODELS.length;
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

  const commonEvaluationWindow =
    completeEvaluationMetadata &&
    evaluationCounts.size === 1 &&
    evaluationStarts.size === 1 &&
    evaluationEnds.size === 1;

  return (
    <section id="model-performance" className="space-y-8 sm:space-y-10 pt-2 sm:pt-4 scroll-mt-24">
      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
          Historical Evaluation
        </span>
        <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          Model Performance & Comparison
        </h2>
        <p className="text-sm text-slate-400 leading-relaxed max-w-3xl">
          Compare the historical chronological out-of-sample performance of
          Lag-Informed Regression, ARIMA, LSTM, and the Naive benchmark across the
          tracked PSE companies.
        </p>
      </div>

      <div className="rounded-2xl border border-dark-border bg-dark-card/60 p-4 sm:p-6 lg:p-8 shadow-sm backdrop-blur-xs">
        <ModelsDashboard
          rows={rows.sort((a, b) => a.symbol.localeCompare(b.symbol))}
          evaluationForecasts={
            completeEvaluationMetadata ? evaluationForecasts : null
          }
          evaluationCount={
            commonEvaluationWindow ? [...evaluationCounts][0] : null
          }
          evaluationStart={
            commonEvaluationWindow ? [...evaluationStarts][0] : null
          }
          evaluationEnd={commonEvaluationWindow ? [...evaluationEnds][0] : null}
          evaluationMetadataAvailable={completeEvaluationMetadata}
        />
      </div>
    </section>
  );
}
