"use client";

import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import ChartGestureControls, { ChartResetButton } from "./ChartGestureControls";
import { useChartInteractions } from "@/hooks/useChartTouchGestures";
import type { ForecastEvidenceSource } from "@/lib/types";

const MODEL_COLORS: Record<string, string> = {
  Actual: "#22c55e",
  ARIMA: "#f59e0b",
  "Lag-Informed Regression": "#3b82f6",
  LSTM: "#a855f7",
  "Naive baseline": "#64748b",
  "Naive Baseline": "#64748b",
};

function formatShortDate(dateStr: string): string {
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

function formatFullDate(dateStr: string): string {
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

export interface PredictionChartProps {
  dates?: string[];
  actual: number[];
  byModel: Record<string, number[]>;
  selectedModel?: string;
  sources?: ForecastEvidenceSource[];
  formalBoundaryDate?: string;
}

export default function PredictionChart({
  dates,
  actual,
  byModel,
  selectedModel,
  sources,
  formalBoundaryDate,
}: PredictionChartProps) {
  const data = useMemo(() => actual.map((value, i) => {
    const rawDate = dates?.[i] || `Day ${i + 1}`;
    const row: Record<string, any> = {
      step: rawDate,
      displayDate: dates?.[i] ? formatShortDate(rawDate) : `Day ${i + 1}`,
      fullDate: dates?.[i] ? formatFullDate(rawDate) : `Day ${i + 1}`,
      source: sources?.[i] ?? "formal_evaluation",
      Actual: value,
    };
    for (const [model, series] of Object.entries(byModel)) {
      if (series[i] !== undefined) row[model] = series[i];
    }
    return row;
  }), [actual, byModel, dates, sources]);

  const gestures = useChartInteractions({
    totalPoints: data.length,
    minWindow: 5,
    resetKey: `${data.length}:${data[0]?.step ?? ""}:${data[data.length - 1]?.step ?? ""}`,
  });
  const visibleData = useMemo(
    () => data.slice(gestures.viewport.startIndex, gestures.viewport.endIndex + 1),
    [data, gestures.viewport.endIndex, gestures.viewport.startIndex],
  );

  const seriesNames = ["Actual", ...Object.keys(byModel)];

  if (data.length === 0) {
    return (
      <div className="flex h-[360px] items-center justify-center rounded-lg border border-dashed border-dark-border bg-dark-bg/40 px-6 text-center">
        <div className="max-w-md space-y-2">
          <p className="text-sm font-medium text-slate-200">Waiting for the first realized production forecast</p>
          <p className="text-xs leading-relaxed text-slate-400">
            PSE Pulse will add a point here after a forecast is issued and the corresponding trading
            session&apos;s closing price becomes available. Historical research backtests are kept separate.
          </p>
        </div>
      </div>
    );
  }

  const renderTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;
    const point = payload[0]?.payload;
    const headerDate = point?.fullDate || point?.displayDate || point?.step;
    const sourceLabel = point?.source === "prospective"
      ? "Verified prospective"
      : point?.source === "post_formal_backfill"
      ? "Post-formal backfill"
      : "Formal evaluation";

    return (
      <div className="bg-dark-card border border-dark-border rounded-xl p-3 shadow-xl text-xs space-y-1.5 min-w-[210px]">
        <p className="font-semibold text-white border-b border-dark-border pb-1.5 mb-1.5">
          {headerDate}
        </p>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
          {sourceLabel}
        </p>
        {payload.map((entry: any) => {
          const isActual = entry.dataKey === "Actual";
          const isSelected = selectedModel && entry.dataKey === selectedModel;
          const isNaive =
            entry.dataKey === "Naive baseline" || entry.dataKey === "Naive Baseline";
          const label = isNaive ? "Naive Baseline" : entry.dataKey;

          return (
            <div key={entry.dataKey} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-full inline-block shrink-0"
                  style={{ backgroundColor: entry.color }}
                />
                <span
                  className={`font-medium ${
                    isActual
                      ? "text-green-400 font-semibold"
                      : isSelected
                      ? "text-brand-400 font-semibold"
                      : "text-slate-300"
                  }`}
                >
                  {label}
                  {isSelected && (
                    <span className="ml-1 text-[10px] text-brand-400 uppercase font-semibold">
                      (Selected)
                    </span>
                  )}
                </span>
              </div>
              <span className="font-mono text-white font-semibold">
                ₱
                {Number(entry.value).toLocaleString("en-PH", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="w-full select-none space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
        <span className="text-slate-400">
          Showing {visibleData.length} of {data.length} trading sessions &middot; Hover points to inspect prices
        </span>
        {formalBoundaryDate && (
          <span className="inline-flex items-center gap-1.5 rounded-md border border-teal-600/40 bg-teal-50 px-2 py-1 font-semibold text-teal-700 dark:border-teal-400/40 dark:bg-teal-400/10 dark:text-teal-100">
            <span className="h-3 border-l-2 border-dashed border-teal-600 dark:border-teal-300" aria-hidden="true" />
            Formal evaluation ends {formatShortDate(formalBoundaryDate)}
          </span>
        )}
      </div>

      <ChartGestureControls {...gestures} />

      <div
        ref={gestures.surfaceRef}
        className={`relative w-full touch-pan-y select-none ${gestures.isDragging ? "cursor-grabbing" : "cursor-grab"}`}
        style={{ touchAction: "pan-y" }}
        {...gestures.handlers}
      >
        <ChartResetButton visible={gestures.isViewportModified} onReset={gestures.reset} />
        <ResponsiveContainer width="100%" height={360}>
          <LineChart
            data={visibleData}
            margin={{ top: 10, right: 15, left: 10, bottom: 5 }}
          >
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
            {formalBoundaryDate && (
              <ReferenceLine
                x={formalBoundaryDate}
                stroke="#2dd4bf"
                strokeWidth={2.5}
                strokeDasharray="7 4"
              />
            )}
            <XAxis
              dataKey="step"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              tickFormatter={(val) => {
                const item = visibleData.find((d) => d.step === val);
                return item ? item.displayDate : val;
              }}
              minTickGap={35}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              domain={["auto", "auto"]}
              tickFormatter={(val) => `₱${Number(val).toLocaleString()}`}
              label={{
                value: "Price (₱)",
                angle: -90,
                position: "insideLeft",
                fill: "#64748b",
                fontSize: 11,
              }}
            />
            <Tooltip content={renderTooltip} />
            <Legend
              wrapperStyle={{ fontSize: 12, paddingTop: 10 }}
              formatter={(value) => {
                const isSelected = selectedModel && value === selectedModel;
                const isNaive = value === "Naive baseline" || value === "Naive Baseline";
                const displayLabel = isNaive ? "Naive Baseline" : value;
                return (
                  <span className={isSelected ? "font-bold text-white" : "text-slate-300"}>
                    {displayLabel}
                    {isSelected && " (Selected)"}
                  </span>
                );
              }}
            />

            {seriesNames.map((name) => {
              const isActual = name === "Actual";
              const isSelected = selectedModel && name === selectedModel;
              const isNaive = name === "Naive baseline" || name === "Naive Baseline";

              return (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={MODEL_COLORS[name] ?? "#94a3b8"}
                  strokeWidth={isActual ? 2.5 : isSelected ? 2.5 : 1.5}
                  strokeDasharray={isNaive ? "4 4" : undefined}
                  dot={visibleData.length === 1 ? { r: 4 } : false}
                  activeDot={{ r: 4 }}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
