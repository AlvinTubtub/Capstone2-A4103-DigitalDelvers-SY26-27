"use client";

import React, { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartGestureControls, { ChartResetButton } from "@/components/charts/ChartGestureControls";
import { useChartInteractions } from "@/hooks/useChartTouchGestures";
import {
  alignSectorChartData,
  type AlignedChartRow,
} from "@/lib/sectorComparison";
import { formatPeso } from "@/lib/format";
import type { CompanyDetail } from "@/lib/types";

interface SectorComparisonChartProps {
  companies: CompanyDetail[];
}

export default function SectorComparisonChart({ companies }: SectorComparisonChartProps) {
  const [displayMode, setDisplayMode] = useState<"price" | "indexed">("price");

  const { data, commonSessionCount, totalAvailableSessions, companiesMeta } = useMemo(
    () => alignSectorChartData(companies, displayMode),
    [companies, displayMode]
  );

  const gestures = useChartInteractions({
    totalPoints: data.length,
    minWindow: 5,
    resetKey: `${displayMode}:${data.length}:${data[0]?.step ?? ""}:${data[data.length - 1]?.step ?? ""}`,
  });

  const visibleData = useMemo(
    () => data.slice(gestures.viewport.startIndex, gestures.viewport.endIndex + 1),
    [data, gestures.viewport.endIndex, gestures.viewport.startIndex]
  );

  if (data.length === 0) {
    return (
      <div className="flex h-[360px] items-center justify-center rounded-xl border border-dashed border-dark-border bg-dark-bg/40 px-6 text-center">
        <p className="text-sm text-slate-400">
          No aligned historical sessions available across the selected sector companies.
        </p>
      </div>
    );
  }

  const renderTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;
    const point: AlignedChartRow = payload[0]?.payload;
    const headerDate = point?.fullDate || point?.displayDate || point?.step;
    const rawMap = point?.raw ?? {};

    return (
      <div className="bg-dark-card border border-dark-border rounded-xl p-3.5 shadow-2xl text-xs space-y-3 min-w-[240px] max-w-[320px]">
        <div className="border-b border-dark-border pb-1.5 flex items-center justify-between">
          <p className="font-bold text-white text-xs">{headerDate}</p>
          {displayMode === "indexed" && (
            <span className="text-[10px] font-semibold text-brand-400 uppercase tracking-wide">
              Indexed (Base 100)
            </span>
          )}
        </div>

        <div className="space-y-2.5">
          {companiesMeta.map((comp) => {
            const raw = rawMap[comp.symbol];
            if (!raw) return null;

            const isDiffPositive = raw.diff > 0;
            const diffSign = raw.diff > 0 ? "+" : "";

            return (
              <div key={comp.symbol} className="space-y-1">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full inline-block shrink-0"
                    style={{ backgroundColor: comp.color }}
                  />
                  <span className="font-bold text-white text-xs">{comp.symbol}</span>
                  <span className="text-[11px] text-slate-400 truncate">({comp.name})</span>
                </div>

                <div className="pl-4 space-y-0.5 text-[11px]">
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-2.5 border-t-2 border-solid" style={{ borderColor: comp.color }} />
                      <span>Actual:</span>
                    </span>
                    <span className="font-mono text-white font-medium">
                      {formatPeso(raw.actualPrice)}
                      {displayMode === "indexed" && (
                        <span className="text-slate-400 text-[10px] ml-1">
                          ({raw.actualVal.toFixed(1)})
                        </span>
                      )}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-slate-300">
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-2.5 border-t-2 border-dashed" style={{ borderColor: comp.color }} />
                      <span className="truncate max-w-[130px]">{raw.modelName}:</span>
                    </span>
                    <span className="font-mono text-white font-medium">
                      {formatPeso(raw.predPrice)}
                      {displayMode === "indexed" && (
                        <span className="text-slate-400 text-[10px] ml-1">
                          ({raw.predVal.toFixed(1)})
                        </span>
                      )}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-slate-400 pt-0.5 border-t border-dark-border/40">
                    <span>Difference:</span>
                    <span
                      className={`font-mono font-medium ${
                        isDiffPositive
                          ? "text-emerald-400"
                          : raw.diff < 0
                          ? "text-rose-400"
                          : "text-slate-300"
                      }`}
                    >
                      {diffSign}
                      {formatPeso(raw.diff)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4 rounded-2xl border border-dark-border bg-dark-card p-5 sm:p-6 shadow-sm">
      {/* Header and Toggle Controls */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div>
          <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight">
            Actual vs Selected Model
          </h3>
          <p className="text-xs sm:text-sm text-slate-400 mt-0.5 leading-relaxed">
            Historical actual closing prices versus each company&apos;s selected principal-model predictions.
          </p>
        </div>

        {/* Price / Indexed Display Toggle */}
        <div className="flex flex-col sm:items-end gap-1.5 shrink-0">
          <div
            role="radiogroup"
            aria-label="Chart price display mode"
            className="inline-flex rounded-lg bg-dark-bg p-1 border border-dark-border"
          >
            <button
              type="button"
              role="radio"
              aria-checked={displayMode === "price"}
              onClick={() => setDisplayMode("price")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                displayMode === "price"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Price (₱)
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={displayMode === "indexed"}
              onClick={() => setDisplayMode("indexed")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                displayMode === "indexed"
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Indexed
            </button>
          </div>

          {displayMode === "indexed" && (
            <span className="text-[11px] font-medium text-brand-400 tracking-wide">
              Indexed — first visible actual close = 100
            </span>
          )}
        </div>
      </div>

      {/* Chart Metadata and Gesture Instructions */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400 pt-1">
        <span>
          Showing {visibleData.length} of {data.length} common trading sessions
          {totalAvailableSessions > 60 && ` (latest 60 of ${totalAvailableSessions} total)`}
          &nbsp;&middot;&nbsp;Hover points to inspect prices
        </span>
      </div>

      {/* Gesture Controls (Zoom In / Out) */}
      <ChartGestureControls {...gestures} />

      {/* Recharts Canvas */}
      <div
        ref={gestures.surfaceRef}
        className={`relative w-full touch-pan-y select-none ${
          gestures.isDragging ? "cursor-grabbing" : "cursor-grab"
        }`}
        style={{ touchAction: "pan-y" }}
        {...gestures.handlers}
      >
        <ChartResetButton visible={gestures.isViewportModified} onReset={gestures.reset} />
        <ResponsiveContainer width="100%" height={380}>
          <LineChart
            data={visibleData}
            margin={{ top: 10, right: 15, left: 10, bottom: 5 }}
          >
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
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
              tickFormatter={(val) =>
                displayMode === "price"
                  ? `₱${Number(val).toLocaleString()}`
                  : Number(val).toFixed(0)
              }
              label={{
                value: displayMode === "price" ? "Price (₱)" : "Index (Base = 100)",
                angle: -90,
                position: "insideLeft",
                fill: "#64748b",
                fontSize: 11,
              }}
            />
            <Tooltip content={renderTooltip} />
            <Legend
              wrapperStyle={{ fontSize: 12, paddingTop: 14 }}
              formatter={(value, entry: any) => {
                const isDashed = Boolean(entry.payload?.strokeDasharray);
                return (
                  <span className="text-slate-300 font-medium text-xs">
                    {value}
                    <span className="text-[10px] text-slate-500 ml-1">
                      {isDashed ? "(Model)" : "(Actual)"}
                    </span>
                  </span>
                );
              }}
            />

            {/* 6 Rendered Series (3 Company Pairs) */}
            {companiesMeta.map((comp) => (
              <React.Fragment key={comp.symbol}>
                {/* 1. Actual (Solid Line) */}
                <Line
                  type="monotone"
                  dataKey={`actual_${comp.symbol}`}
                  name={`${comp.symbol} — Actual`}
                  stroke={comp.color}
                  strokeWidth={2.5}
                  dot={visibleData.length === 1 ? { r: 4 } : false}
                  activeDot={{ r: 4.5 }}
                />

                {/* 2. Selected Model (Dashed Line) */}
                <Line
                  type="monotone"
                  dataKey={`pred_${comp.symbol}`}
                  name={`${comp.symbol} — ${comp.selectedModelLabel}`}
                  stroke={comp.color}
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={visibleData.length === 1 ? { r: 4 } : false}
                  activeDot={{ r: 4.5 }}
                />
              </React.Fragment>
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
