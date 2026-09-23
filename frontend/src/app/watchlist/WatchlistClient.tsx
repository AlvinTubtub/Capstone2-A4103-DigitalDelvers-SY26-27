"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import CompanyLogo from "@/components/CompanyLogo";
import ChangeBadge from "@/components/ChangeBadge";
import StockComparisonChart from "@/components/comparison/StockComparisonChart";
import StockMetricsComparison from "@/components/comparison/StockMetricsComparison";
import { useWatchlist } from "@/context/WatchlistContext";
import { formatDate, formatPeso } from "@/lib/format";
import { resolveCompanyModelReporting } from "@/lib/modelReporting";
import type { CompanyDetail, CompanySummary, MetricsData } from "@/lib/types";

type ComparisonRow = CompanySummary & {
  pesoChange: number;
  rmse?: string | number;
  mase?: string | number;
  bestPrincipalModel: string;
  bestEvaluatedMethod: string;
  bestPrincipalBeatsNaive: boolean;
  allPrincipalsWorseThanNaive: boolean;
};

export default function WatchlistClient({
  allCompanies,
  metrics,
}: {
  allCompanies: CompanySummary[];
  metrics: MetricsData | null;
}) {
  const { watchlist, removeFromWatchlist, clearWatchlist, maxLimit } = useWatchlist();

  // Match symbols in watchlist with company summary details
  const watchedCompanies = useMemo(() => {
    const companyMap = new Map(allCompanies.map((c) => [c.symbol.toUpperCase(), c]));
    return watchlist
      .map((sym) => companyMap.get(sym.toUpperCase()))
      .filter((c): c is CompanySummary => Boolean(c));
  }, [watchlist, allCompanies]);

  const comparisonRows = useMemo(
    () =>
      watchedCompanies.map((company) => {
        const companyMetrics = metrics?.perCompany[company.symbol];
        const reporting = companyMetrics
          ? resolveCompanyModelReporting(companyMetrics)
          : null;
        const modelKey = Object.entries(companyMetrics?.metrics ?? {}).find(
          ([key]) =>
            ({
              lag_reg: "Lag-Informed Regression",
              arima: "ARIMA",
              lstm: "LSTM",
              naive: "Naive baseline",
            }[key] === (reporting?.bestPrincipalModel ?? company.bestModel))
        )?.[0];
        const selectedMetrics = modelKey ? companyMetrics?.metrics[modelKey] : undefined;

        return {
          ...company,
          pesoChange: company.predictedClose - company.latestClose,
          rmse: selectedMetrics?.rmse,
          mase: selectedMetrics?.mase,
          bestPrincipalModel: reporting?.bestPrincipalModel ?? company.bestModel,
          bestEvaluatedMethod: reporting?.bestEvaluatedMethod ?? "--",
          bestPrincipalBeatsNaive: reporting?.bestPrincipalBeatsNaive ?? false,
          allPrincipalsWorseThanNaive: reporting?.allPrincipalsWorseThanNaive ?? false,
        };
      }),
    [metrics, watchedCompanies]
  );

  // Lazy-load detailed CompanyDetail data only for watched companies
  const [details, setDetails] = useState<CompanyDetail[]>([]);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);

  const watchedSymbolsKey = useMemo(
    () => watchedCompanies.map((c) => c.symbol.toUpperCase()).join(","),
    [watchedCompanies]
  );

  useEffect(() => {
    if (watchedCompanies.length === 0) {
      setDetails([]);
      setLoadingDetails(false);
      setDetailsError(null);
      return;
    }

    const controller = new AbortController();
    setLoadingDetails(true);
    setDetailsError(null);

    const symbols = watchedCompanies.map((c) => c.symbol.toUpperCase());

    Promise.all(
      symbols.map(async (sym) => {
        const res = await fetch(`/forecasts/company/${sym}.json`, {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!res.ok) {
          throw new Error(`Failed to load ${sym}`);
        }
        return (await res.json()) as CompanyDetail;
      })
    )
      .then((results) => {
        setDetails(results);
        setLoadingDetails(false);
        setDetailsError(null);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setDetailsError("Watchlist comparison is temporarily unavailable.");
        setLoadingDetails(false);
      });

    return () => {
      controller.abort();
    };
  }, [watchedSymbolsKey, watchedCompanies]);

  return (
    <div className="space-y-8 animate-[fadeIn_0.3s_ease-out]">
      {/* 1. Header Section */}
      <div className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-full">
                ★ Saved on this device
              </span>
            </div>
            <h1 className="text-2xl sm:text-4xl font-bold text-white tracking-tight">
              My Watchlist
            </h1>
            <p className="text-slate-300 text-sm sm:text-base mt-2">
              Watching{" "}
              <span className="font-semibold text-white">
                {watchedCompanies.length} of {maxLimit}
              </span>{" "}
              companies
            </p>
          </div>

          {watchedCompanies.length > 0 && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={clearWatchlist}
                className="text-xs font-medium text-slate-400 hover:text-red-400 px-3 py-2 rounded-lg border border-dark-border bg-dark-bg hover:border-red-500/40 transition-colors cursor-pointer"
              >
                Clear Watchlist
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 2. Content: Watched List or Empty State */}
      {watchedCompanies.length === 0 ? (
        <div className="bg-dark-card border border-dark-border rounded-2xl p-8 sm:p-12 text-center max-w-2xl mx-auto space-y-4">
          <div className="w-14 h-14 mx-auto rounded-full bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-2xl text-slate-400">
            ☆
          </div>
          <h2 className="text-xl font-bold text-white">No companies in your watchlist yet</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Add up to 5 companies to quickly monitor their latest PSE Pulse predictions.
          </p>
          <div className="pt-2">
            <Link
              href="/companies"
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold shadow-lg shadow-brand-500/20 transition-all"
            >
              Explore Companies →
            </Link>
          </div>
        </div>
      ) : (
        <>
          {comparisonRows.some((company) => company.allPrincipalsWorseThanNaive) && (
            <section
              role="status"
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
            >
              <strong>Naive benchmark warning:</strong> for one or more watched companies,
              all three principal models had higher RMSE than Naive during the evaluation
              period. See the comparison table for each best evaluated method.
            </section>
          )}

          {/* Contextual Help & Privacy Note */}
          <div className="p-4 bg-dark-bg/70 border border-dark-border/70 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-400">
            <p>
              <span className="font-semibold text-slate-300">Device Storage: </span>
              Your watchlist is saved only on this browser and device.
            </p>
            <div className="flex items-center gap-1.5 shrink-0">
              <span>Not sure how to interpret these forecasts?</span>
              <Link
                href="/learn-stocks"
                className="text-brand-400 hover:text-brand-300 font-medium underline underline-offset-2"
              >
                Learn Stock Trading Basics
              </Link>
            </div>
          </div>

          {/* Watched Company Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {watchedCompanies.map((company) => (
              <div
                key={company.symbol}
                className="bg-dark-card border border-dark-border rounded-xl p-5 hover:border-brand-500/40 transition-all shadow-sm flex flex-col justify-between space-y-4"
              >
                <div className="space-y-3">
                  {/* Header Row */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <CompanyLogo symbol={company.symbol} name={company.name} size="md" />
                      <div className="min-w-0">
                        <Link
                          href={`/companies/${company.symbol}`}
                          className="font-bold text-white text-lg hover:text-brand-400 transition-colors leading-tight block"
                        >
                          {company.symbol}
                        </Link>
                        <p className="text-xs text-slate-400 truncate max-w-[12rem]">
                          {company.name}
                        </p>
                      </div>
                    </div>
                    <ChangeBadge pctChange={company.pctChange} />
                  </div>

                  {/* Details Grid */}
                  <div className="pt-3 border-t border-dark-border/60 grid grid-cols-2 gap-2 text-left">
                    <div>
                      <p className="text-[11px] text-slate-400">Forecasted Close</p>
                      <p className="text-base font-semibold text-white">
                        {formatPeso(company.predictedClose)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[11px] text-slate-400">Best Principal Model</p>
                      <p className="text-xs font-medium text-brand-400 truncate">
                        {company.bestModel}
                      </p>
                    </div>
                  </div>

                  {/* Metadata Row */}
                  <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                    {company.forecastDate ? (
                      <span className="text-[11px] text-slate-400">
                        Forecast for {formatDate(company.forecastDate)}
                      </span>
                    ) : (
                      <span />
                    )}
                    <span className="text-[10px] px-2 py-0.5 rounded bg-dark-bg border border-dark-border text-slate-400">
                      {company.sector}
                    </span>
                  </div>
                </div>

                {/* Action Footer */}
                <div className="pt-3 border-t border-dark-border/50 flex items-center justify-between gap-2">
                  <Link
                    href={`/companies/${company.symbol}`}
                    className="text-xs font-medium text-brand-400 hover:text-brand-300 transition-colors"
                  >
                    View Details →
                  </Link>
                  <button
                    type="button"
                    onClick={() => removeFromWatchlist(company.symbol)}
                    className="text-xs text-slate-400 hover:text-red-400 px-2.5 py-1 rounded border border-transparent hover:border-red-500/30 hover:bg-red-500/10 transition-colors cursor-pointer"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* 3. Comparison Section (Lazy-Loaded Detailed History & Metrics) */}
          {loadingDetails ? (
            <div className="rounded-2xl border border-dark-border bg-dark-card/60 p-6 flex flex-col items-center justify-center min-h-[220px] text-center space-y-3">
              <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
              <p className="text-sm font-medium text-slate-300">
                Loading watchlist comparison...
              </p>
              <p className="text-xs text-slate-500">
                Retrieving historical series and evaluation metrics for{" "}
                {watchedCompanies.map((c) => c.symbol).join(", ")}
              </p>
            </div>
          ) : detailsError ? (
            <div className="rounded-xl border border-dark-border bg-dark-card p-5 text-center space-y-2">
              <p className="text-sm font-semibold text-slate-300">{detailsError}</p>
              <p className="text-xs text-slate-500">
                Your watched company cards above remain fully accessible.
              </p>
            </div>
          ) : details.length > 0 ? (
            <>
              {/* Actual vs Selected Model Chart */}
              <StockComparisonChart
                companies={details}
                title="Actual vs Selected Model"
                subtitle="Historical actual closing prices versus each watched company's selected principal-model predictions."
                emptyMessage="No aligned historical sessions available across your watched companies."
              />

              {/* Side-by-Side Stock Metrics (Summary / Advanced) */}
              <StockMetricsComparison
                companies={details}
                title="Side-by-Side Stock Metrics"
                subtitle="Compare current forecast values and evaluation information for your watched companies."
              />
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
