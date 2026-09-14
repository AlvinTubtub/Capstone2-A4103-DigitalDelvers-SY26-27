import type { CompanyEvaluationMetrics, ModelMetric } from "./types";

export const PRINCIPAL_MODEL_IDS = ["lag_reg", "arima", "lstm"] as const;
export const EVALUATION_MODEL_IDS = [...PRINCIPAL_MODEL_IDS, "naive"] as const;

export type PrincipalModelId = (typeof PRINCIPAL_MODEL_IDS)[number];
export type EvaluationModelId = (typeof EVALUATION_MODEL_IDS)[number];

export const MODEL_LABELS: Record<EvaluationModelId, string> = {
  lag_reg: "Lag-Informed Regression",
  arima: "ARIMA",
  lstm: "LSTM",
  naive: "Naive baseline",
};

function finiteRmse(metric: ModelMetric | undefined): number | null {
  const parsed = Number(metric?.rmse);
  return Number.isFinite(parsed) ? parsed : null;
}

function winner(
  metrics: Record<string, ModelMetric>,
  candidates: readonly EvaluationModelId[],
): EvaluationModelId | null {
  const complete = candidates.map((id) => ({ id, rmse: finiteRmse(metrics[id]) }));
  if (complete.some(({ rmse }) => rmse === null)) return null;
  return complete.reduce((best, candidate) =>
    Number(candidate.rmse) < Number(best.rmse) ? candidate : best,
  ).id;
}

export interface CompanyModelReporting {
  bestPrincipalModel: string;
  bestEvaluatedMethod: string;
  bestPrincipalBeatsNaive: boolean;
  allPrincipalsWorseThanNaive: boolean;
}

/** Resolve additive fields, falling back to the documented canonical RMSE tie order. */
export function resolveCompanyModelReporting(
  company: CompanyEvaluationMetrics | Pick<CompanyEvaluationMetrics, "metrics">,
): CompanyModelReporting | null {
  const principal = winner(company.metrics, PRINCIPAL_MODEL_IDS);
  const evaluated = winner(company.metrics, EVALUATION_MODEL_IDS);
  const naiveRmse = finiteRmse(company.metrics.naive);
  if (!principal || !evaluated || naiveRmse === null) return null;
  const principalRmse = finiteRmse(company.metrics[principal]);
  if (principalRmse === null) return null;
  return {
    bestPrincipalModel:
      "bestPrincipalModel" in company && company.bestPrincipalModel
        ? company.bestPrincipalModel
        : MODEL_LABELS[principal],
    bestEvaluatedMethod:
      "bestEvaluatedMethod" in company && company.bestEvaluatedMethod
        ? company.bestEvaluatedMethod
        : MODEL_LABELS[evaluated],
    bestPrincipalBeatsNaive:
      "bestPrincipalBeatsNaive" in company
      && typeof company.bestPrincipalBeatsNaive === "boolean"
        ? company.bestPrincipalBeatsNaive
        : principalRmse < naiveRmse,
    allPrincipalsWorseThanNaive:
      "allPrincipalsWorseThanNaive" in company
      && typeof company.allPrincipalsWorseThanNaive === "boolean"
        ? company.allPrincipalsWorseThanNaive
        : PRINCIPAL_MODEL_IDS.every(
            (id) => Number(finiteRmse(company.metrics[id])) > naiveRmse,
          ),
  };
}
