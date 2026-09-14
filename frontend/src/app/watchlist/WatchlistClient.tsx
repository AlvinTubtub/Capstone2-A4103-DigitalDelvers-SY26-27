"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import CompanyLogo from "@/components/CompanyLogo";
import ChangeBadge from "@/components/ChangeBadge";
import { useWatchlist } from "@/context/WatchlistContext";
import { formatDate, formatNum, formatPeso, formatPct } from "@/lib/format";
import type { CompanySummary, MetricsData } from "@/lib/types";

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
    () => watchedCompanies.map((company) => {
      const companyMetrics = metrics?.perCompany[company.symbol];
      const modelKey = Object.entries(companyMetrics?.metrics ?? {}).find(
        ([key]) => ({ lag_reg: "Lag-Informed Regression", arima: "ARIMA", lstm: "LSTM", naive: "Naive baseline" }[key] === company.bestModel)
      )?.[0];
      const selectedMetrics = modelKey ? companyMetrics?.metrics[modelKey] : undefined;
      const selectedRmse = Number(selectedMetrics?.rmse);
      const naiveRmse = Number(companyMetrics?.metrics.naive?.rmse);

      return {
        ...company,
        pesoChange: company.predictedClose - company.latestClose,
        rmse: selectedMetrics?.rmse,
        mase: selectedMetrics?.mase,
        bestPrincipalBeatsNaive:
          Number.isFinite(selectedRmse)
          && Number.isFinite(naiveRmse)
          && selectedRmse < naiveRmse,
      };
    }),
    [metrics, watchedCompanies]
  );

  return (
    <div className="space-y-8 animate-[fadeIn_0.3s_ease-out]">
      {/* 1. Header Section */}
      <div className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-full">
                ★ Client-Side Watchlist
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
            Add up to 5 companies to quickly monitor their latest ForecastPH predictions.
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
                    <p className="text-[11px] text-slate-400">Selected Model</p>
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

          <section className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2 mb-5 pb-4 border-b border-dark-border/70">
              <div>
                <h2 className="text-base font-bold text-white">Expected Change (%) Comparison</h2>
                <p className="text-xs text-slate-400 mt-1">Next-session forecast movement across your watched companies.</p>
              </div>
              <span className="text-[11px] text-slate-300">Forecast horizon: next session</span>
            </div>
            <div className="h-64 sm:h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={comparisonRows} margin={{ top: 10, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="symbol" tick={{ fill: "#f1f5f9", fontSize: 12, fontWeight: 600 }} axisLine={{ stroke: "#64748b" }} tickLine={false} />
                  <YAxis tick={{ fill: "#cbd5e1", fontSize: 11 }} tickFormatter={(value) => `${value}%`} axisLine={{ stroke: "#64748b" }} tickLine={false} />
                  <Tooltip
                    cursor={{ fill: "rgba(148, 163, 184, 0.08)" }}
                    contentStyle={{ background: "#0f172a", border: "1px solid #64748b", borderRadius: 10, color: "#f8fafc", fontSize: 12 }}
                    labelStyle={{ color: "#f8fafc", fontWeight: 700 }}
                    itemStyle={{ color: "#e2e8f0" }}
                    formatter={(value: number) => [formatPct(value), "Expected Change"]}
                  />
                  <Bar dataKey="pctChange" radius={[5, 5, 0, 0]} maxBarSize={70}>
                    {comparisonRows.map((company) => (
                      <Cell key={company.symbol} fill={company.pctChange >= 0 ? "#22c55e" : "#f87171"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 shadow-sm">
            <div className="mb-5 pb-4 border-b border-dark-border/70">
              <h2 className="text-base font-bold text-white">Side-by-Side Stock Metrics</h2>
              <p className="text-xs text-slate-400 mt-1">Compare current forecast values and selected-model evaluation metrics.</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-dark-border/70 text-left">
                    <th className="px-3 py-3 text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Metric</th>
                    {comparisonRows.map((company) => (
                      <th key={company.symbol} className="px-3 py-3 min-w-[155px]">
                        <Link href={`/companies/${company.symbol}`} className="text-brand-400 hover:text-brand-300 font-bold">{company.symbol} →</Link>
                        <p className="mt-1 text-[11px] font-normal text-slate-400 truncate max-w-[170px]">{company.name}</p>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-border/70">
                  <MetricRow label="Sector" companies={comparisonRows} render={(company) => <span className="inline-block rounded border border-dark-border bg-dark-bg px-2 py-0.5 text-[11px] text-slate-300">{company.sector}</span>} />
                  <MetricRow label="Previous Close" companies={comparisonRows} render={(company) => formatPeso(company.latestClose)} />
                  <MetricRow label="Forecasted Close" companies={comparisonRows} render={(company) => <span className="font-semibold text-white">{formatPeso(company.predictedClose)}</span>} />
                  <MetricRow label="Expected Change" companies={comparisonRows} render={(company) => <span className={company.pctChange >= 0 ? "text-green-400 font-semibold" : "text-red-400 font-semibold"}>{formatPeso(company.pesoChange)} ({formatPct(company.pctChange)})</span>} />
                  <MetricRow label="Selected Model" companies={comparisonRows} render={(company) => company.bestModel} />
                  <MetricRow label="Test RMSE (₱)" companies={comparisonRows} render={(company) => company.rmse === undefined ? "--" : formatNum(company.rmse)} />
                  <MetricRow label="MASE (Development-Scaled)" companies={comparisonRows} render={(company) => company.mase === undefined ? "--" : formatNum(company.mase)} />
                  <MetricRow label="Beats Naive on Held-Out RMSE?" companies={comparisonRows} render={(company) => company.rmse === undefined ? "--" : company.bestPrincipalBeatsNaive ? <span className="text-green-400">✓ Yes</span> : <span className="text-amber-400">△ No</span>} />
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function MetricRow({
  label,
  companies,
  render,
}: {
  label: string;
  companies: Array<CompanySummary & { pesoChange: number; rmse?: string | number; mase?: string | number; bestPrincipalBeatsNaive: boolean }>;
  render: (company: CompanySummary & { pesoChange: number; rmse?: string | number; mase?: string | number; bestPrincipalBeatsNaive: boolean }) => React.ReactNode;
}) {
  return (
    <tr>
      <th scope="row" className="px-3 py-3 text-left text-xs font-medium text-slate-400">{label}</th>
      {companies.map((company) => <td key={company.symbol} className="px-3 py-3 text-xs text-slate-200">{render(company)}</td>)}
    </tr>
  );
}
