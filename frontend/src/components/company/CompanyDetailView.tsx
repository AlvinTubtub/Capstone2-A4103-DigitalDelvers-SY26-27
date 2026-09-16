"use client";

import { useState, useEffect, useRef } from "react";
import HistoryChart from "@/components/charts/HistoryChart";
import NextDayPredictionChart from "@/components/charts/NextDayPredictionChart";
import PredictionChart from "@/components/charts/PredictionChart";
import ErrorChart from "@/components/charts/ErrorChart";
import ChangeBadge from "@/components/ChangeBadge";
import CompanyLogo from "@/components/CompanyLogo";
import StatCard from "@/components/StatCard";
import WatchlistStar from "@/components/watchlist/WatchlistStar";
import { getCompanyProfile } from "@/lib/companyProfiles";
import { formatDate, formatNum, formatPeso } from "@/lib/format";
import { resolveCompanyModelReporting } from "@/lib/modelReporting";
import type { CompanyDetail } from "@/lib/types";

interface CompanyDetailViewProps {
  company: CompanyDetail;
}

type ViewMode = "beginner" | "advanced";

const STORAGE_KEY = "forecastph_view_mode";

export default function CompanyDetailView({ company }: CompanyDetailViewProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("beginner");
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const beginnerBtnRef = useRef<HTMLButtonElement>(null);
  const advancedBtnRef = useRef<HTMLButtonElement>(null);

  // Sync mode with localStorage on client mount & listen for storage changes
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "advanced" || saved === "beginner") {
        setViewMode(saved);
      }
    } catch {
      // localStorage may be unavailable in private browsing modes
    }

    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && (e.newValue === "beginner" || e.newValue === "advanced")) {
        setViewMode(e.newValue);
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const handleModeChange = (mode: ViewMode) => {
    setViewMode(mode);
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // ignore
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, currentMode: ViewMode) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      handleModeChange("advanced");
      advancedBtnRef.current?.focus();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      handleModeChange("beginner");
      beginnerBtnRef.current?.focus();
    }
  };

  const profile = getCompanyProfile(company.symbol);

  const modelOrder = ["lag_reg", "arima", "lstm", "naive"];
  const modelLabels: Record<string, string> = {
    lag_reg: "Lag-Informed Regression",
    arima: "ARIMA",
    lstm: "LSTM",
    naive: "Naive baseline",
  };

  const selectedModelKey =
    Object.keys(modelLabels).find((key) => modelLabels[key] === company.model) || "arima";
  const selectedMetrics = company.metrics[selectedModelKey] || {
    rmse: "--",
    mae: "--",
    mase: "--",
    r2: "--",
  };

  const maseVal = parseFloat(String(selectedMetrics.mase));
  const selectedRmse = parseFloat(String(selectedMetrics.rmse));
  const naiveRmse = parseFloat(String(company.metrics.naive?.rmse));
  const maseBelowDevelopmentScale = !isNaN(maseVal) && maseVal < 1.0;
  const reporting = resolveCompanyModelReporting({
    metrics: company.metrics,
    bestModel: company.model,
    bestPrincipalModel: company.bestPrincipalModel,
    bestEvaluatedMethod: company.bestEvaluatedMethod,
    bestPrincipalBeatsNaive: company.bestPrincipalBeatsNaive,
    allPrincipalsWorseThanNaive: company.allPrincipalsWorseThanNaive,
  });
  const beatsNaive = reporting?.bestPrincipalBeatsNaive
    ?? (!isNaN(selectedRmse) && !isNaN(naiveRmse) && selectedRmse < naiveRmse);
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
  const chartActual = [...company.backtestActual, ...verifiedProductionActual];
  const chartSources = [
    ...auditedDates.map(() => "formal_evaluation" as const),
    ...(hasRealizedProductionHistory
      ? productionProvenance.map((point) => point.source)
      : []),
  ];
  const chartByModel = Object.fromEntries(
    Object.entries(company.backtestByModel).map(([model, values]) => [
      model,
      hasRealizedProductionHistory && productionByModel[model]
        ? [...values, ...productionByModel[model]]
        : values,
    ])
  );

  return (
    <div className="space-y-8">
      {/* 1. Header & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <a
            href="/companies"
            className="text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors uppercase tracking-wider mb-1 inline-block"
          >
            ← Back to Companies
          </a>
          <div className="flex items-start gap-3.5">
            <CompanyLogo symbol={company.symbol} name={company.name} size="lg" />
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-bold text-white tracking-tight">{company.symbol}</h1>
                <span className="text-xs px-2.5 py-1 rounded-md bg-dark-bg border border-dark-border text-slate-300 font-medium">
                  {company.sector}
                </span>
                <WatchlistStar symbol={company.symbol} showLabel size="md" />
              </div>
              <p className="text-sm text-slate-400 mt-0.5">{company.name}</p>

              {/* Compact Company Profile expand button directly below company name and sector label */}
              <button
                type="button"
                onClick={() => setIsProfileOpen((prev) => !prev)}
                aria-expanded={isProfileOpen}
                aria-controls="company-profile-panel"
                className="mt-2.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-dark-card hover:bg-slate-800/80 border border-dark-border hover:border-slate-600 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-500 shadow-2xs group"
              >
                <svg
                  className="w-3.5 h-3.5 text-brand-400 shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span>About {company.name}</span>
                <svg
                  className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ease-out ${
                    isProfileOpen ? "rotate-180 text-brand-400" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Upper-right metadata area: Date context & Beginner / Advanced view toggle */}
        <div className="flex flex-col sm:items-end gap-2.5">
          {/* Date context */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 bg-dark-card border border-dark-border px-3.5 py-2 rounded-xl">
            {company.dataAsOf && (
              <div>
                <span className="text-slate-500">Data as of: </span>
                <strong className="text-slate-300 font-medium">{formatDate(company.dataAsOf)}</strong>
              </div>
            )}
            {company.dataAsOf && company.forecastDate && <span>&middot;</span>}
            {company.forecastDate && (
              <div>
                <span className="text-slate-500">Forecast for: </span>
                <strong className="text-brand-300 font-semibold">
                  {formatDate(company.forecastDate)}
                </strong>
              </div>
            )}
          </div>

          {/* Accessible Beginner / Advanced Segmented Control */}
          <div
            role="radiogroup"
            aria-label="Detail view mode"
            className="inline-flex items-center p-1 rounded-xl bg-dark-card border border-dark-border shadow-xs"
          >
            <button
              ref={beginnerBtnRef}
              type="button"
              role="radio"
              aria-checked={viewMode === "beginner"}
              tabIndex={viewMode === "beginner" ? 0 : -1}
              onClick={() => handleModeChange("beginner")}
              onKeyDown={(e) => handleKeyDown(e, "beginner")}
              className={`relative px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                viewMode === "beginner"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              }`}
            >
              Beginner
            </button>
            <button
              ref={advancedBtnRef}
              type="button"
              role="radio"
              aria-checked={viewMode === "advanced"}
              tabIndex={viewMode === "advanced" ? 0 : -1}
              onClick={() => handleModeChange("advanced")}
              onKeyDown={(e) => handleKeyDown(e, "advanced")}
              className={`relative px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                viewMode === "advanced"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              }`}
            >
              Advanced
            </button>
          </div>
        </div>
      </div>

      {/* In-place collapsible Company Profile Panel */}
      <div
        id="company-profile-panel"
        className={`grid transition-all duration-200 ease-out ${
          isProfileOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0 pointer-events-none"
        }`}
        aria-hidden={!isProfileOpen}
      >
        <div className="overflow-hidden">
          <div className="bg-dark-card border border-dark-border rounded-xl p-4 sm:p-5 shadow-sm space-y-3">
            {profile?.description && (
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                {profile.description}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-2 border-t border-dark-border/60 text-xs">
              {company.sector && (
                <div>
                  <span className="text-slate-400">Sector: </span>
                  <span className="text-white font-medium">{company.sector}</span>
                </div>
              )}
              {profile?.industry && (
                <div>
                  <span className="text-slate-400">Industry: </span>
                  <span className="text-white font-medium">{profile.industry}</span>
                </div>
              )}
              {profile?.website && (
                <div>
                  <span className="text-slate-400">Official Website: </span>
                  <a
                    href={profile.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-brand-400 hover:text-brand-300 font-medium hover:underline ml-1"
                  >
                    <span>{profile.website.replace(/^https?:\/\/(www\.)?/, "")}</span>
                    <svg
                      className="w-3 h-3"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                      />
                    </svg>
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Top Stats Grid */}
      <section
        className={`grid grid-cols-1 sm:grid-cols-2 ${
          viewMode === "advanced" ? "lg:grid-cols-4" : "lg:grid-cols-3"
        } gap-4`}
      >
        {/* Item 1: Previous Close (Shown in Beginner & Advanced) */}
        <StatCard label="Previous Close" value={formatPeso(company.previousClose)} />

        {/* Item 2: Forecasted Close (Shown in Beginner & Advanced) */}
        <StatCard
          label="Forecasted Close"
          value={formatPeso(company.predictedClose)}
          accent="text-white"
        />

        {/* Item 3: Expected Change (Shown in Beginner & Advanced) */}
        <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Expected Change</p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">{formatPeso(company.pesoChange)}</span>
            <ChangeBadge pctChange={company.pctChange} />
          </div>
        </div>

        {/* Item 4: Best Principal Model Card (Hidden in Beginner, Shown in Advanced) */}
        {viewMode === "advanced" && (
          <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">Best Principal Model</p>
            <p className="text-base font-bold text-white truncate" title={company.model}>
              {company.model}
            </p>
            <p className="text-[11px] text-brand-400 mt-0.5">Lowest evaluation RMSE</p>
          </div>
        )}
      </section>

      {/* 3. Best Principal Model Summary Panel (Hidden in Beginner, Shown in Advanced) */}
      {viewMode === "advanced" && (
        <section className="bg-dark-card border border-dark-border rounded-xl p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4 pb-3 border-b border-dark-border/60">
            <div>
              <h2 className="text-lg font-semibold text-white">
                Best Principal Model Summary: {company.model}
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Metrics calculated strictly for this company&apos;s out-of-sample test split.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                  beatsNaive
                    ? "bg-green-500/10 text-green-400 border-green-500/30"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                }`}
              >
                {beatsNaive
                  ? "✓ Lower held-out RMSE than Naive"
                  : "⚠ Did not beat Naive held-out RMSE"}
              </span>
              {reporting && (
                <span className="text-xs px-2.5 py-1 rounded-full font-semibold border border-slate-600 bg-slate-800/70 text-slate-200">
                  Best evaluated: {reporting.bestEvaluatedMethod}
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-dark-bg border border-dark-border rounded-lg p-3.5">
              <p className="text-xs text-slate-400 mb-0.5">Test RMSE</p>
              <p className="text-lg font-bold text-white font-mono">
                {formatNum(selectedMetrics.rmse, 4)}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">Scale-dependent error</p>
            </div>
            <div className="bg-dark-bg border border-dark-border rounded-lg p-3.5">
              <p className="text-xs text-slate-400 mb-0.5">Test MAE</p>
              <p className="text-lg font-bold text-white font-mono">
                {formatNum(selectedMetrics.mae, 4)}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">Mean absolute error</p>
            </div>
            <div className="bg-dark-bg border border-dark-border rounded-lg p-3.5">
              <p className="text-xs text-slate-400 mb-0.5">MASE</p>
              <p
                className={`text-lg font-bold font-mono ${
                  maseBelowDevelopmentScale ? "text-green-400" : "text-amber-400"
                }`}
              >
                {formatNum(selectedMetrics.mase, 4)}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">Compared with development scale</p>
            </div>
            <div className="bg-dark-bg border border-dark-border rounded-lg p-3.5">
              <p className="text-xs text-slate-400 mb-0.5">Holdout R² — supplementary</p>
              <p className="text-lg font-bold text-white font-mono">
                {formatNum(selectedMetrics.r2, 4)}
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">Compared with the holdout mean</p>
            </div>
          </div>

          <p className="text-xs text-slate-400 mt-3.5 leading-relaxed">
            <strong className="text-slate-300">Note: </strong>
            MASE below 1.0 means evaluation MAE is below the development-series one-step
            scale; it does not by itself show that the selected model beat Naive on held-out
            dates. R² can be negative and is supplementary—not percentage accuracy or a
            forecast confidence probability.
          </p>
        </section>
      )}

      {reporting?.allPrincipalsWorseThanNaive && (
        <section role="status" className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          <strong>Naive benchmark warning:</strong> all three principal models had higher
          RMSE than Naive during this evaluation period. {reporting.bestPrincipalModel} is
          still the best principal model, while {reporting.bestEvaluatedMethod} is the best
          evaluated method.
        </section>
      )}

      {/* 4. Historical OHLCV (Shown in Beginner & Advanced) */}
      <section className="bg-dark-card border border-dark-border rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Historical OHLCV</h2>
        <HistoryChart data={company.ohlcv} />
      </section>

      {/* 5. Next-Day Prediction (Shown in Beginner & Advanced) */}
      <section className="bg-dark-card border border-dark-border rounded-xl p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-1">
          <h2 className="text-lg font-semibold text-white">Next-Day Prediction</h2>
        </div>
        <p className="text-sm text-slate-400 mb-4">
          Latest actual close with model predictions for the next trading session.
        </p>
        <NextDayPredictionChart
          ohlcv={company.ohlcv}
          previousClose={company.previousClose}
          nextClose={company.nextClose}
          forecastDate={company.forecastDate}
          dataAsOf={company.dataAsOf}
          hideModelBreakdown={viewMode === "beginner"}
        />
      </section>

      {/* 6. Backtest: Predicted vs. Actual (Shown in Beginner & Advanced) */}
      <section className="bg-dark-card border border-dark-border rounded-xl p-6">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h2 className="text-lg font-semibold text-white">
            Predicted vs. Actual — Formal Evaluation + Post-Formal Monitoring
          </h2>
          <span className="rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
            Chronological evaluation
          </span>
          {hasRealizedProductionHistory && (
            <span className="rounded-md border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
              Post-formal monitoring
            </span>
          )}
        </div>
        <p className="text-sm text-slate-400 mb-4">
          {company.evaluationMetadata ? (
            <>
              Displays the latest {company.evaluationMetadata.displayedSessionCount} sessions from
              the frozen {company.evaluationMetadata.fullSessionCount}-session formal evaluation
              followed by {verifiedProductionDates.length} realized post-formal
              {verifiedProductionDates.length === 1 ? " session" : " sessions"}. Full formal
              evaluation: {formatDate(company.evaluationMetadata.fullStartDate)} –{" "}
              {formatDate(company.evaluationMetadata.fullEndDate)}. Formal metrics and statistical
              tests continue to use only the complete frozen evaluation.
            </>
          ) : (
            <>
              This previously published payload contains the latest {auditedDates.length}
              evaluation sessions. Full evaluation count and range will appear after the next
              fresh export; they are not inferred from the display window.
            </>
          )}{" "}
          {" "}{company.evaluationMetadata?.displayedSessionCount ?? auditedDates.length} formal
          evaluation sessions + {verifiedProductionDates.length} post-formal
          {verifiedProductionDates.length === 1 ? " session" : " sessions"} are displayed.
        </p>
        <PredictionChart
          dates={chartDates}
          actual={chartActual}
          byModel={chartByModel}
          selectedModel={company.model}
          sources={chartSources}
          formalBoundaryDate={company.evaluationMetadata?.fullEndDate}
        />
      </section>

      {/* 7. Forecast Error Over Time (Hidden in Beginner, Shown in Advanced) */}
      {viewMode === "advanced" && (
        <section className="bg-dark-card border border-dark-border rounded-xl p-6">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h2 className="text-lg font-semibold text-white">
              Forecast Error Over Time — Formal Evaluation + Post-Formal Monitoring
            </h2>
            <span className="rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
              Chronological evaluation
            </span>
            {hasRealizedProductionHistory && (
              <span className="rounded-md border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                Post-formal monitoring
              </span>
            )}
          </div>
          <p className="text-sm text-slate-400 mb-4">
            Displays errors for the latest {company.evaluationMetadata?.displayedSessionCount ?? auditedDates.length}
            {" "}sessions from the frozen formal evaluation followed by {verifiedProductionDates.length}
            {" "}realized post-formal {verifiedProductionDates.length === 1 ? "session" : "sessions"}.
            The fixed boundary marks the formal evaluation end date. Formal metrics and statistical
            tests exclude production history. Error is predicted close minus actual close (₱).
          </p>
          <ErrorChart
            dates={chartDates}
            actual={chartActual}
            byModel={chartByModel}
            selectedModel={company.model}
            sources={chartSources}
            formalBoundaryDate={company.evaluationMetadata?.fullEndDate}
          />
        </section>
      )}

      {/* 8. Model Performance Table (Hidden in Beginner, Shown in Advanced) */}
      {viewMode === "advanced" && (
        <section className="bg-dark-card border border-dark-border rounded-xl p-6 overflow-x-auto">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-white mb-1">
              Model Performance for {company.symbol}
            </h2>
            <p className="text-xs text-slate-400">
              Current chronological-evaluation metrics across all forecasting models and the naive
              baseline.
            </p>
          </div>

          <table className="w-full text-sm">
            <thead className="text-xs text-slate-400 uppercase bg-dark-bg/80 border-b border-dark-border">
              <tr>
                <th className="text-left py-2 px-3">Model</th>
                <th className="text-right py-2 px-3">RMSE (₱)</th>
                <th className="text-right py-2 px-3">MAE (₱)</th>
                <th className="text-right py-2 px-3">MASE</th>
                <th className="text-right py-2 px-3">Holdout R² (supp.)</th>
              </tr>
            </thead>
            <tbody>
              {modelOrder
                .filter((m) => company.metrics[m])
                .map((m) => (
                  <tr
                    key={m}
                    className={`border-b border-dark-border/50 ${
                      modelLabels[m] === company.model ? "bg-brand-500/5" : ""
                    }`}
                  >
                    <td className="py-2.5 px-3 font-medium text-white">
                      {modelLabels[m]}
                      {modelLabels[m] === company.model && (
                        <span className="ml-2 text-[10px] uppercase text-brand-400 border border-brand-500/40 rounded px-1.5 py-0.5">
                          Selected
                        </span>
                      )}
                      {m === "naive" && (
                        <span className="ml-2 text-[10px] uppercase text-slate-400 border border-slate-600 rounded px-1.5 py-0.5">
                          Benchmark
                        </span>
                      )}
                    </td>
                    <td className="text-right py-2.5 px-3 font-mono">
                      {formatNum(company.metrics[m].rmse)}
                    </td>
                    <td className="text-right py-2.5 px-3 font-mono">
                      {formatNum(company.metrics[m].mae)}
                    </td>
                    <td className="text-right py-2.5 px-3 font-mono">
                      {formatNum(company.metrics[m].mase)}
                    </td>
                    <td className="text-right py-2.5 px-3 font-mono">
                      {formatNum(company.metrics[m].r2)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>

          <div className="mt-4 pt-3 border-t border-dark-border/60 text-xs text-slate-400 space-y-1">
            <p>
              &bull; <strong className="text-slate-300">Model Selection: </strong>
              The best principal model is the lowest-RMSE result among LIR, ARIMA, and LSTM in the latest chronological
              evaluation. Current cross-company rankings are available on the Models page.
            </p>
            <p>
              &bull; <strong className="text-slate-300">MASE Benchmark: </strong>
              MASE divides evaluation MAE by the development-series one-step error scale.
              Compare held-out RMSE directly with Naive to determine which evaluated method
              performed better.
            </p>
            <p>
              &bull; <strong className="text-slate-300">R² Interpretation: </strong>
              R² is supplementary, can be negative, and is neither percentage accuracy nor a
              forecast confidence probability. It does not select the winning model.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
