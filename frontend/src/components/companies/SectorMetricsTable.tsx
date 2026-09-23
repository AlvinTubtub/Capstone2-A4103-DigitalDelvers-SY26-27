"use client";

import React, { useState } from "react";
import CompanyLogo from "@/components/CompanyLogo";
import {
  getCompanyMetricsRowData,
  type CompanyMetricsRowItem,
} from "@/lib/sectorComparison";
import { formatDate, formatNum, formatPeso, formatPct } from "@/lib/format";
import type { CompanyDetail } from "@/lib/types";

interface SectorMetricsTableProps {
  companies: CompanyDetail[];
}

interface MetricTooltipInfo {
  label: string;
  explanation: string;
}

const ADVANCED_METRIC_TOOLTIPS: Record<string, MetricTooltipInfo> = {
  rmse: {
    label: "RMSE (₱)",
    explanation:
      "Typical prediction error with larger errors weighted more heavily. Lower is better.",
  },
  mae: {
    label: "MAE (₱)",
    explanation:
      "Average absolute difference between predicted and actual closing prices. Lower is better.",
  },
  mase: {
    label: "MASE",
    explanation:
      "Scale-free forecast error relative to the declared development scaling benchmark. Lower is better.",
  },
  r2: {
    label: "R²",
    explanation:
      "Supporting measure of how closely predictions follow variation in actual prices. It is not an accuracy percentage.",
  },
  beatsNaive: {
    label: "Beats Naive?",
    explanation:
      "Whether the selected principal model had lower held-out RMSE than the Naive benchmark.",
  },
};

export default function SectorMetricsTable({ companies }: SectorMetricsTableProps) {
  const [mode, setMode] = useState<"summary" | "advanced">("summary");
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);

  const rowsData: CompanyMetricsRowItem[] = companies.map(getCompanyMetricsRowData);

  const toggleTooltip = (key: string) => {
    setActiveTooltip((prev) => (prev === key ? null : key));
  };

  const renderMetricLabelWithTooltip = (key: string, defaultLabel: string) => {
    const tip = ADVANCED_METRIC_TOOLTIPS[key];
    if (!tip) return <span>{defaultLabel}</span>;

    const isOpen = activeTooltip === key;

    return (
      <div className="relative inline-flex items-center gap-1.5 group">
        <span>{defaultLabel}</span>
        <button
          type="button"
          onClick={() => toggleTooltip(key)}
          aria-label={`About ${defaultLabel}`}
          className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] text-slate-400 hover:text-white bg-dark-bg border border-dark-border/60 hover:border-brand-500 transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-brand-400"
        >
          ⓘ
        </button>
        {isOpen && (
          <div
            role="tooltip"
            className="absolute left-0 top-6 z-30 w-56 p-2 text-xs font-normal text-slate-200 bg-dark-card border border-dark-border rounded-lg shadow-xl"
          >
            <p className="leading-snug">{tip.explanation}</p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4 rounded-2xl border border-dark-border bg-dark-card p-5 sm:p-6 shadow-sm">
      {/* Section Header & View Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            Side-by-Side Stock Metrics
          </h3>
          <p className="text-xs sm:text-sm text-slate-400 mt-0.5 leading-relaxed">
            Compare current forecast values and evaluation information for the three selected companies.
          </p>
        </div>

        {/* Accessible Segmented Control */}
        <div
          role="radiogroup"
          aria-label="Stock metrics detail level"
          className="inline-flex rounded-lg bg-dark-bg p-1 border border-dark-border shrink-0 self-start sm:self-auto"
        >
          <button
            type="button"
            role="radio"
            aria-checked={mode === "summary"}
            onClick={() => setMode("summary")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-all ${
              mode === "summary"
                ? "bg-brand-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Summary
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={mode === "advanced"}
            onClick={() => setMode("advanced")}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-all ${
              mode === "advanced"
                ? "bg-brand-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Advanced
          </button>
        </div>
      </div>

      {/* =========================================================================
          1. DESKTOP / TABLET: SIDE-BY-SIDE COMPARISON TABLE
      ========================================================================= */}
      <div className="hidden sm:block overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-dark-border">
              <th scope="col" className="py-3 px-3 text-xs font-semibold text-slate-400 uppercase tracking-wider w-1/4">
                Metric
              </th>
              {rowsData.map((c) => (
                <th key={c.symbol} scope="col" className="py-3 px-4 w-1/4">
                  <div className="flex items-center gap-2">
                    <CompanyLogo symbol={c.symbol} name={c.name} size="sm" />
                    <div>
                      <span className="font-bold text-white text-base leading-tight block">
                        {c.symbol}
                      </span>
                      <span className="text-[11px] text-slate-400 font-normal truncate max-w-[130px] block">
                        {c.name}
                      </span>
                    </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-border/40 text-slate-300">
            {/* --- Summary Rows (Always Visible) --- */}
            <tr>
              <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                Previous Close
              </th>
              {rowsData.map((c) => (
                <td key={c.symbol} className="py-2.5 px-4 font-mono font-semibold text-white">
                  {formatPeso(c.previousClose)}
                </td>
              ))}
            </tr>

            <tr>
              <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                Forecasted Close
              </th>
              {rowsData.map((c) => (
                <td key={c.symbol} className="py-2.5 px-4 font-mono font-semibold text-white">
                  {formatPeso(c.predictedClose)}
                </td>
              ))}
            </tr>

            <tr>
              <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                Expected Change
              </th>
              {rowsData.map((c) => {
                const isPos = c.expectedChange > 0;
                const isNeg = c.expectedChange < 0;
                const sign = isPos ? "+" : "";
                return (
                  <td
                    key={c.symbol}
                    className={`py-2.5 px-4 font-mono font-semibold ${
                      isPos ? "text-emerald-400" : isNeg ? "text-rose-400" : "text-slate-300"
                    }`}
                  >
                    {sign}
                    {formatPeso(c.expectedChange)}
                  </td>
                );
              })}
            </tr>

            <tr>
              <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                Expected Change (%)
              </th>
              {rowsData.map((c) => {
                const isPos = c.expectedChangePct > 0;
                const isNeg = c.expectedChangePct < 0;
                return (
                  <td key={c.symbol} className="py-2.5 px-4">
                    <span
                      className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-xs font-bold ${
                        isPos
                          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                          : isNeg
                          ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                          : "bg-slate-700/30 text-slate-300 border border-slate-600/30"
                      }`}
                    >
                      {formatPct(c.expectedChangePct)}
                    </span>
                  </td>
                );
              })}
            </tr>

            {/* --- Advanced Evaluation Rows (Visible only in Advanced Mode) --- */}
            {mode === "advanced" && (
              <>
                <tr className="bg-dark-bg/60 border-t-2 border-dark-border">
                  <td
                    colSpan={4}
                    className="py-2 px-3 text-xs font-bold uppercase tracking-wider text-brand-400"
                  >
                    Advanced Evaluation
                  </td>
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    Selected Model
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-semibold text-brand-300">
                      {c.selectedModel}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    Best Evaluated Method
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-medium text-slate-200">
                      {c.bestEvaluatedMethod}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    {renderMetricLabelWithTooltip("rmse", "RMSE (₱)")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.rmse, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    {renderMetricLabelWithTooltip("mae", "MAE (₱)")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.mae, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    {renderMetricLabelWithTooltip("mase", "MASE")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.mase, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    {renderMetricLabelWithTooltip("r2", "R²")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.r2, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    {renderMetricLabelWithTooltip("beatsNaive", "Beats Naive?")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4">
                      {c.beatsNaive ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold text-xs">
                          ✓ Yes
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-400 font-medium text-xs">
                          △ No
                        </span>
                      )}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th scope="row" className="py-2.5 px-3 font-medium text-slate-400">
                    Forecast Date
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 text-xs text-slate-300">
                      {formatDate(c.forecastDate)}
                    </td>
                  ))}
                </tr>
              </>
            )}
          </tbody>
        </table>
      </div>

      {/* =========================================================================
          2. MOBILE: STACKED COMPARISON CARDS
      ========================================================================= */}
      <div className="block sm:hidden space-y-3.5">
        {rowsData.map((c) => {
          const isPos = c.expectedChange > 0;
          const isNeg = c.expectedChange < 0;
          const sign = isPos ? "+" : "";

          return (
            <div
              key={c.symbol}
              className="rounded-xl border border-dark-border bg-dark-bg p-4 space-y-3 shadow-xs"
            >
              {/* Card Header */}
              <div className="flex items-center gap-2.5 border-b border-dark-border/60 pb-2.5">
                <CompanyLogo symbol={c.symbol} name={c.name} size="sm" />
                <div className="min-w-0">
                  <h4 className="font-bold text-white text-base leading-tight">
                    {c.symbol}
                  </h4>
                  <p className="text-xs text-slate-400 truncate">{c.name}</p>
                </div>
              </div>

              {/* Summary Metrics */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-400 block text-[11px]">Previous Close</span>
                  <span className="font-mono font-semibold text-white">
                    {formatPeso(c.previousClose)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Forecasted Close</span>
                  <span className="font-mono font-semibold text-white">
                    {formatPeso(c.predictedClose)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Expected Change</span>
                  <span
                    className={`font-mono font-semibold ${
                      isPos ? "text-emerald-400" : isNeg ? "text-rose-400" : "text-slate-300"
                    }`}
                  >
                    {sign}
                    {formatPeso(c.expectedChange)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Expected Change (%)</span>
                  <span
                    className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold ${
                      isPos
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                        : isNeg
                        ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                        : "bg-slate-700/30 text-slate-300"
                    }`}
                  >
                    {formatPct(c.expectedChangePct)}
                  </span>
                </div>
              </div>

              {/* Advanced Metrics (Mobile Expand) */}
              {mode === "advanced" && (
                <div className="border-t border-dark-border/60 pt-2.5 space-y-2 text-xs">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-brand-400">
                    Advanced Evaluation
                  </p>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Selected Model</span>
                    <span className="font-semibold text-brand-300">{c.selectedModel}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Best Evaluated Method</span>
                    <span className="font-medium text-slate-200">{c.bestEvaluatedMethod}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">RMSE (₱)</span>
                    <span className="font-mono text-slate-200">{formatNum(c.rmse, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">MAE (₱)</span>
                    <span className="font-mono text-slate-200">{formatNum(c.mae, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">MASE</span>
                    <span className="font-mono text-slate-200">{formatNum(c.mase, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">R²</span>
                    <span className="font-mono text-slate-200">{formatNum(c.r2, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Beats Naive?</span>
                    <span>
                      {c.beatsNaive ? (
                        <span className="text-emerald-400 font-semibold">✓ Yes</span>
                      ) : (
                        <span className="text-amber-400 font-medium">△ No</span>
                      )}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Forecast Date</span>
                    <span className="text-slate-300">{formatDate(c.forecastDate)}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
