"use client";

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import CompanyLogo from "@/components/CompanyLogo";
import {
  getCompanyMetricsRowData,
  type CompanyMetricsRowItem,
} from "@/lib/sectorComparison";
import { formatDate, formatNum, formatPeso, formatPct } from "@/lib/format";
import type { CompanyDetail } from "@/lib/types";

export interface StockMetricsComparisonProps {
  companies: CompanyDetail[];
  title?: string;
  subtitle?: string;
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

interface ActiveTooltipState {
  key: string;
  triggerId: string;
  rect: DOMRect;
  coords: { top: number; left: number };
}

function computeTooltipPosition(
  btnRect: DOMRect,
  tooltipWidth: number,
  tooltipHeight: number
): { top: number; left: number } {
  const vw = typeof window !== "undefined" ? window.innerWidth : 1024;
  const vh = typeof window !== "undefined" ? window.innerHeight : 768;
  const padding = 10;
  const gap = 6;

  const spaceOnRight = vw - (btnRect.right + gap) >= tooltipWidth + padding;
  const spaceBelow = vh - (btnRect.bottom + gap) >= tooltipHeight + padding;

  let left: number;
  let top: number;

  if (spaceOnRight) {
    // Desktop preference: place to the right of the button, vertically centered
    left = btnRect.right + gap;
    top = btnRect.top + btnRect.height / 2 - tooltipHeight / 2;
  } else {
    // Insufficient room on the right (e.g. mobile or near viewport edge): place below or above
    left = btnRect.left;
    if (spaceBelow) {
      top = btnRect.bottom + gap;
    } else {
      top = btnRect.top - tooltipHeight - gap;
    }
  }

  // Viewport bounds collision clamping
  if (left + tooltipWidth > vw - padding) {
    left = vw - padding - tooltipWidth;
  }
  if (left < padding) {
    left = padding;
  }

  if (top + tooltipHeight > vh - padding) {
    top = vh - padding - tooltipHeight;
  }
  if (top < padding) {
    top = padding;
  }

  return { top, left };
}

export default function StockMetricsComparison({
  companies,
  title = "Side-by-Side Stock Metrics",
  subtitle = "Compare current forecast values and evaluation information for the selected companies.",
}: StockMetricsComparisonProps) {
  const [mode, setMode] = useState<"summary" | "advanced">("summary");
  const [activeTooltip, setActiveTooltip] = useState<ActiveTooltipState | null>(null);
  const [mounted, setMounted] = useState<boolean>(false);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const rowsData: CompanyMetricsRowItem[] = companies.map(getCompanyMetricsRowData);

  const toggleTooltip = (key: string, triggerId: string, buttonEl: HTMLButtonElement) => {
    if (activeTooltip?.triggerId === triggerId) {
      setActiveTooltip(null);
    } else {
      const rect = buttonEl.getBoundingClientRect();
      const coords = computeTooltipPosition(rect, 240, 90);
      setActiveTooltip({ key, triggerId, rect, coords });
    }
  };

  // Refine coordinates after DOM measurement
  useLayoutEffect(() => {
    if (!activeTooltip || !tooltipRef.current) return;
    const el = tooltipRef.current;
    const rect = el.getBoundingClientRect();
    if (rect.width && rect.height) {
      const refined = computeTooltipPosition(activeTooltip.rect, rect.width, rect.height);
      if (
        Math.abs(refined.top - activeTooltip.coords.top) > 1 ||
        Math.abs(refined.left - activeTooltip.coords.left) > 1
      ) {
        setActiveTooltip((prev) => (prev ? { ...prev, coords: refined } : null));
      }
    }
  }, [activeTooltip?.key, activeTooltip?.triggerId]);

  // Handle outside clicks, Escape key, scroll, and viewport resize
  useEffect(() => {
    if (!activeTooltip) return;

    const handleDismiss = () => {
      setActiveTooltip(null);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setActiveTooltip(null);
      }
    };

    const handlePointerDown = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (tooltipRef.current && tooltipRef.current.contains(target)) return;
      const triggerEl = document.getElementById(activeTooltip.triggerId);
      if (triggerEl && triggerEl.contains(target)) return;
      setActiveTooltip(null);
    };

    window.addEventListener("scroll", handleDismiss, true);
    window.addEventListener("resize", handleDismiss);
    window.addEventListener("keydown", handleKeyDown);
    document.addEventListener("pointerdown", handlePointerDown);

    return () => {
      window.removeEventListener("scroll", handleDismiss, true);
      window.removeEventListener("resize", handleDismiss);
      window.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [activeTooltip]);

  const renderMetricLabelWithTooltip = (
    key: string,
    defaultLabel: string,
    scope: string = "desktop"
  ) => {
    const tip = ADVANCED_METRIC_TOOLTIPS[key];
    if (!tip) return <span>{defaultLabel}</span>;

    const buttonId = `metric-help-${scope}-${key}`;
    const isOpen = activeTooltip?.triggerId === buttonId;
    const tooltipId = "advanced-metric-floating-tooltip";

    return (
      <div className="inline-flex items-center gap-1.5">
        <span>{defaultLabel}</span>
        <button
          type="button"
          id={buttonId}
          onClick={(e) => toggleTooltip(key, buttonId, e.currentTarget)}
          aria-label={`About ${defaultLabel}`}
          aria-expanded={isOpen}
          aria-describedby={isOpen ? tooltipId : undefined}
          className={`inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-brand-400 cursor-pointer ${
            isOpen
              ? "text-brand-500 bg-brand-500/15 border border-brand-500"
              : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white bg-slate-100 dark:bg-dark-bg border border-slate-300 dark:border-dark-border/60 hover:border-brand-500 dark:hover:border-brand-500"
          }`}
        >
          ⓘ
        </button>
      </div>
    );
  };

  return (
    <div className="space-y-4 rounded-2xl border border-dark-border bg-dark-card p-5 sm:p-6 shadow-sm">
      {/* Section Header & View Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            {title}
          </h3>
          <p className="text-xs sm:text-sm text-slate-400 mt-0.5 leading-relaxed">
            {subtitle}
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
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
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
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
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
        <table className="w-full text-left text-sm border-collapse min-w-[640px]">
          <thead>
            <tr className="border-b border-dark-border">
              <th
                scope="col"
                className="py-3 px-3 text-xs font-semibold text-slate-400 uppercase tracking-wider min-w-[170px] sticky left-0 bg-dark-card z-10"
              >
                Metric
              </th>
              {rowsData.map((c) => (
                <th key={c.symbol} scope="col" className="py-3 px-4 min-w-[150px]">
                  <Link
                    href={`/companies/${c.symbol}`}
                    className="flex items-center gap-2 group hover:opacity-90 transition-opacity"
                  >
                    <CompanyLogo symbol={c.symbol} name={c.name} size="sm" />
                    <div className="min-w-0">
                      <span className="font-bold text-white text-base leading-tight block group-hover:text-brand-400 transition-colors">
                        {c.symbol}
                      </span>
                      <span className="text-[11px] text-slate-400 font-normal truncate max-w-[130px] block">
                        {c.name}
                      </span>
                    </div>
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-border/40 text-slate-300">
            {/* --- Summary Rows (Always Visible) --- */}
            <tr>
              <th
                scope="row"
                className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
              >
                Previous Close
              </th>
              {rowsData.map((c) => (
                <td key={c.symbol} className="py-2.5 px-4 font-mono font-semibold text-white">
                  {formatPeso(c.previousClose)}
                </td>
              ))}
            </tr>

            <tr>
              <th
                scope="row"
                className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
              >
                Forecasted Close
              </th>
              {rowsData.map((c) => (
                <td key={c.symbol} className="py-2.5 px-4 font-mono font-semibold text-white">
                  {formatPeso(c.predictedClose)}
                </td>
              ))}
            </tr>

            <tr>
              <th
                scope="row"
                className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
              >
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
              <th
                scope="row"
                className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
              >
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
                    colSpan={rowsData.length + 1}
                    className="py-2 px-3 text-xs font-bold uppercase tracking-wider text-brand-400"
                  >
                    Advanced Evaluation
                  </td>
                </tr>

                <tr>
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
                    Selected Model
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-semibold text-brand-300">
                      {c.selectedModel}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
                    Best Evaluated Method
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-medium text-slate-200">
                      {c.bestEvaluatedMethod}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
                    {renderMetricLabelWithTooltip("rmse", "RMSE (₱)", "desktop")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.rmse, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
                    {renderMetricLabelWithTooltip("mae", "MAE (₱)", "desktop")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.mae, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
                    {renderMetricLabelWithTooltip("mase", "MASE", "desktop")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.mase, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
                    {renderMetricLabelWithTooltip("r2", "R²", "desktop")}
                  </th>
                  {rowsData.map((c) => (
                    <td key={c.symbol} className="py-2.5 px-4 font-mono text-slate-200">
                      {formatNum(c.r2, 4)}
                    </td>
                  ))}
                </tr>

                <tr>
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
                    {renderMetricLabelWithTooltip("beatsNaive", "Beats Naive?", "desktop")}
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
                  <th
                    scope="row"
                    className="py-2.5 px-3 font-medium text-slate-400 sticky left-0 bg-dark-card z-10"
                  >
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
                  <Link
                    href={`/companies/${c.symbol}`}
                    className="font-bold text-white text-base leading-tight hover:text-brand-400 transition-colors block"
                  >
                    {c.symbol}
                  </Link>
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
                    {renderMetricLabelWithTooltip("rmse", "RMSE (₱)", `mobile-${c.symbol}`)}
                    <span className="font-mono text-slate-200">{formatNum(c.rmse, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    {renderMetricLabelWithTooltip("mae", "MAE (₱)", `mobile-${c.symbol}`)}
                    <span className="font-mono text-slate-200">{formatNum(c.mae, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    {renderMetricLabelWithTooltip("mase", "MASE", `mobile-${c.symbol}`)}
                    <span className="font-mono text-slate-200">{formatNum(c.mase, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    {renderMetricLabelWithTooltip("r2", "R²", `mobile-${c.symbol}`)}
                    <span className="font-mono text-slate-200">{formatNum(c.r2, 4)}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    {renderMetricLabelWithTooltip("beatsNaive", "Beats Naive?", `mobile-${c.symbol}`)}
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

      {/* =========================================================================
          3. VIEWPORT-LEVEL FLOATING TOOLTIP PORTAL (Escapes Overflow/Stacking Contexts)
      ========================================================================= */}
      {mounted && activeTooltip && ADVANCED_METRIC_TOOLTIPS[activeTooltip.key] && (
        createPortal(
          <div
            ref={tooltipRef}
            id="advanced-metric-floating-tooltip"
            role="tooltip"
            aria-live="polite"
            style={{
              position: "fixed",
              top: `${activeTooltip.coords.top}px`,
              left: `${activeTooltip.coords.left}px`,
            }}
            className="z-[100] w-[240px] max-w-[calc(100vw-20px)] rounded-xl border p-3 text-xs leading-relaxed shadow-2xl animate-[fadeIn_0.15s_ease-out] bg-white text-slate-800 border-slate-200 shadow-slate-900/10 dark:bg-slate-900 dark:text-slate-200 dark:border-slate-700 dark:shadow-black/60"
          >
            <div className="font-bold text-slate-900 dark:text-white mb-1">
              {ADVANCED_METRIC_TOOLTIPS[activeTooltip.key].label}
            </div>
            <p className="text-slate-600 dark:text-slate-300">
              {ADVANCED_METRIC_TOOLTIPS[activeTooltip.key].explanation}
            </p>
          </div>,
          document.body
        )
      )}
    </div>
  );
}
