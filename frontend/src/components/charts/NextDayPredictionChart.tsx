"use client";

import React, { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import ChartGestureControls, { ChartResetButton } from "./ChartGestureControls";
import { useChartInteractions } from "@/hooks/useChartTouchGestures";
import type { OhlcvPoint } from "@/lib/types";
import { formatDate, formatPeso } from "@/lib/format";

export interface NextDayPredictionChartProps {
  ohlcv: OhlcvPoint[];
  previousClose: number;
  nextClose: {
    lag?: number;
    arima?: number;
    lstm?: number;
    [key: string]: number | undefined;
  };
  forecastDate?: string;
  dataAsOf?: string | null;
  hideModelBreakdown?: boolean;
  selectedPrincipalModelId?: "lag_reg" | "arima" | "lstm";
  selectedPrincipalModel?: string;
}

function formatShortDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [y, m, d] = dateStr.split("-").map(Number);
      const dt = new Date(y, m - 1, d);
      return dt.toLocaleDateString("en-US", { day: "2-digit", month: "short" });
    }
    const dt = new Date(dateStr);
    return dt.toLocaleDateString("en-US", { day: "2-digit", month: "short" });
  } catch {
    return dateStr;
  }
}

export default function NextDayPredictionChart({
  ohlcv,
  previousClose,
  nextClose,
  forecastDate,
  dataAsOf,
  hideModelBreakdown = false,
  selectedPrincipalModelId,
  selectedPrincipalModel,
}: NextDayPredictionChartProps) {
  const [windowSize, setWindowSize] = useState<number>(25);

  const selectedNextVal = useMemo(() => {
    if (selectedPrincipalModelId === "lag_reg") return nextClose.lag;
    if (selectedPrincipalModelId === "arima") return nextClose.arima;
    if (selectedPrincipalModelId === "lstm") return nextClose.lstm;

    if (selectedPrincipalModel === "Lag-Informed Regression") return nextClose.lag;
    if (selectedPrincipalModel === "ARIMA") return nextClose.arima;
    if (selectedPrincipalModel === "LSTM") return nextClose.lstm;

    return nextClose.arima ?? nextClose.lag ?? nextClose.lstm;
  }, [selectedPrincipalModelId, selectedPrincipalModel, nextClose]);

  const fullChartData = useMemo(() => {
    if (!ohlcv || ohlcv.length === 0) return [];

    const historicalSlice = ohlcv.slice(-windowSize);
    const n = historicalSlice.length;

    const items = historicalSlice.map((pt, i) => {
      const isLatestActual = i === n - 1;
      return {
        dateKey: pt.date,
        displayDate: formatShortDate(pt.date),
        fullDate: formatDate(pt.date),
        actualClose: pt.close,
        isForecastPoint: false,
        isLatestActual,
        // Start dashed prediction branch from the latest actual close point
        predictedClose: hideModelBreakdown && isLatestActual ? pt.close : null,
        arimaNext: !hideModelBreakdown && isLatestActual ? pt.close : null,
        lagNext: !hideModelBreakdown && isLatestActual ? pt.close : null,
        lstmNext: !hideModelBreakdown && isLatestActual ? pt.close : null,
      };
    });

    // Append the next-day forecast point
    const nextDateStr = forecastDate || "Next Day";
    const shortNextDate = forecastDate ? formatShortDate(forecastDate) : "Next Day";

    items.push({
      dateKey: nextDateStr,
      displayDate: `${shortNextDate}\n(Next Day)`,
      fullDate: `${formatDate(forecastDate)} (Next Trading Session)`,
      actualClose: null as any,
      isForecastPoint: true,
      isLatestActual: false,
      predictedClose: hideModelBreakdown ? (selectedNextVal ?? null) : null,
      arimaNext: !hideModelBreakdown ? (nextClose.arima ?? (null as any)) : (null as any),
      lagNext: !hideModelBreakdown ? (nextClose.lag ?? (null as any)) : (null as any),
      lstmNext: !hideModelBreakdown ? (nextClose.lstm ?? (null as any)) : (null as any),
    });

    return items;
  }, [ohlcv, windowSize, forecastDate, nextClose, hideModelBreakdown, selectedNextVal]);

  const gestures = useChartInteractions({
    totalPoints: fullChartData.length,
    minWindow: Math.min(6, fullChartData.length),
    resetKey: `${windowSize}:${fullChartData[0]?.dateKey ?? ""}:${fullChartData[fullChartData.length - 1]?.dateKey ?? ""}`,
  });
  const chartData = useMemo(
    () => fullChartData.slice(gestures.viewport.startIndex, gestures.viewport.endIndex + 1),
    [fullChartData, gestures.viewport.endIndex, gestures.viewport.startIndex],
  );

  // Compute dynamic Y-axis domain
  const yDomain = useMemo(() => {
    const values: number[] = [];
    chartData.forEach((d: any) => {
      if (typeof d.actualClose === "number") values.push(d.actualClose);
      if (hideModelBreakdown) {
        if (typeof d.predictedClose === "number") values.push(d.predictedClose);
      } else {
        if (typeof d.arimaNext === "number") values.push(d.arimaNext);
        if (typeof d.lagNext === "number") values.push(d.lagNext);
        if (typeof d.lstmNext === "number") values.push(d.lstmNext);
      }
    });

    if (values.length === 0) return ["auto", "auto"];
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal;
    const padding = Math.max(range * 0.12, 1);

    return [
      Math.max(0, Math.floor((minVal - padding) * 10) / 10),
      Math.ceil((maxVal + padding) * 10) / 10,
    ];
  }, [chartData, hideModelBreakdown]);

  const renderTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;
    const point = payload[0]?.payload;
    if (!point) return null;

    if (point.isForecastPoint) {
      if (hideModelBreakdown) {
        return (
          <div className="bg-dark-card border border-dark-border rounded-xl p-3.5 shadow-xl text-xs space-y-2 min-w-[220px]">
            <div className="font-semibold text-white border-b border-dark-border pb-1.5 mb-1.5 flex items-center justify-between">
              <span>{point.fullDate}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-400 font-normal">
                Forecast
              </span>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-slate-300 pb-1">
                <span className="text-slate-400">Latest Actual Close:</span>
                <span className="font-mono font-medium text-white">{formatPeso(previousClose)}</span>
              </div>
              <div className="border-t border-dark-border/60 pt-1.5 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-brand-500" />
                  <span className="text-slate-300">Predicted Close:</span>
                </div>
                <span className="font-mono font-semibold text-brand-400">
                  {selectedNextVal !== undefined ? formatPeso(selectedNextVal) : "--"}
                </span>
              </div>
            </div>
          </div>
        );
      }

      return (
        <div className="bg-dark-card border border-dark-border rounded-xl p-3.5 shadow-xl text-xs space-y-2 min-w-[240px]">
          <div className="font-semibold text-white border-b border-dark-border pb-1.5 mb-1.5 flex items-center justify-between">
            <span>{point.fullDate}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-400 font-normal">
              Forecast
            </span>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-300 pb-1">
              <span className="text-slate-400">Latest Actual Close:</span>
              <span className="font-mono font-medium text-white">{formatPeso(previousClose)}</span>
            </div>
            <div className="border-t border-dark-border/60 pt-1.5 space-y-1.5">
              {nextClose.arima !== undefined && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#a855f7]" />
                    <span className="text-slate-300">ARIMA:</span>
                  </div>
                  <span className="font-mono font-semibold text-[#c084fc]">
                    {formatPeso(nextClose.arima)}
                  </span>
                </div>
              )}
              {nextClose.lag !== undefined && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#38bdf8]" />
                    <span className="text-slate-300">Lag-Informed Regression:</span>
                  </div>
                  <span className="font-mono font-semibold text-[#38bdf8]">
                    {formatPeso(nextClose.lag)}
                  </span>
                </div>
              )}
              {nextClose.lstm !== undefined && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#f97316]" />
                    <span className="text-slate-300">LSTM:</span>
                  </div>
                  <span className="font-mono font-semibold text-[#fb923c]">
                    {formatPeso(nextClose.lstm)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="bg-dark-card border border-dark-border rounded-xl p-3 shadow-xl text-xs space-y-1 min-w-[180px]">
        <p className="font-semibold text-white border-b border-dark-border pb-1 mb-1">
          {point.fullDate}
        </p>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-slate-400 dark:bg-white" />
            <span className="text-slate-300">
              {point.isLatestActual
                ? (hideModelBreakdown ? "Actual Close:" : "Latest Actual Close:")
                : "Actual Close:"}
            </span>
          </div>
          <span className="font-mono font-semibold text-white">
            {formatPeso(point.actualClose)}
          </span>
        </div>
      </div>
    );
  };

  const renderActualDot = (props: any) => {
    const { cx, cy, index, payload } = props;
    if (payload?.isForecastPoint || typeof payload?.actualClose !== "number") {
      return <React.Fragment key={index} />;
    }
    const isLatest = payload?.isLatestActual;

    return (
      <circle
        key={index}
        cx={cx}
        cy={cy}
        r={isLatest ? 5.5 : 3.5}
        fill={isLatest ? "#38bdf8" : "var(--chart-actual-dot-fill)"}
        stroke={isLatest ? "var(--chart-actual-line)" : "var(--chart-actual-dot-stroke)"}
        strokeWidth={isLatest ? 2 : 1}
      />
    );
  };

  const renderPredictionDot = (color: string) => (props: any) => {
    const { cx, cy, index, payload } = props;
    if (!payload?.isForecastPoint) return <React.Fragment key={index} />;

    return (
      <circle
        key={index}
        cx={cx}
        cy={cy}
        r={5}
        fill={color}
        stroke="#ffffff"
        strokeWidth={1.5}
      />
    );
  };

  return (
    <div className="w-full space-y-4 select-none">
      {/* 1. Header Legend & Range Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-dark-border/60">
        {hideModelBreakdown ? (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0.5 bg-slate-900 dark:bg-white inline-block rounded-full"></span>
              <span className="w-2 h-2 rounded-full bg-slate-900 dark:bg-white inline-block -ml-2.5"></span>
              <span className="font-medium text-slate-800 dark:text-slate-200">
                Actual Close
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0 border-t-2 border-dashed border-brand-500 inline-block"></span>
              <span className="w-2 h-2 rounded-full bg-brand-500 inline-block -ml-2.5"></span>
              <span className="font-medium text-slate-800 dark:text-slate-200">
                Predicted Close
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0.5 bg-slate-900 dark:bg-white inline-block rounded-full"></span>
              <span className="w-2 h-2 rounded-full bg-slate-900 dark:bg-white inline-block -ml-2.5"></span>
              <span className="font-medium text-slate-800 dark:text-slate-200">
                Actual close (latest)
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0 border-t-2 border-dashed border-[#a855f7] inline-block"></span>
              <span className="w-2 h-2 rounded-full bg-[#a855f7] inline-block -ml-2.5"></span>
              <span className="font-medium text-slate-800 dark:text-slate-200">ARIMA (next day)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0 border-t-2 border-dashed border-[#38bdf8] inline-block"></span>
              <span className="w-2 h-2 rounded-full bg-[#38bdf8] inline-block -ml-2.5"></span>
              <span className="font-medium text-slate-800 dark:text-slate-200">
                Lag-Informed Regression (next day)
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0 border-t-2 border-dashed border-[#f97316] inline-block"></span>
              <span className="w-2 h-2 rounded-full bg-[#f97316] inline-block -ml-2.5"></span>
              <span className="font-medium text-slate-800 dark:text-slate-200">LSTM (next day)</span>
            </div>
          </div>
        )}

        {/* Range Buttons */}
        <div className="flex items-center gap-1 self-end sm:self-auto bg-dark-bg border border-dark-border rounded-lg p-0.5 text-xs">
          {[15, 25, 40, 60].map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => setWindowSize(size)}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                windowSize === size
                  ? "bg-brand-600 text-white font-medium shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {size}d
            </button>
          ))}
        </div>
      </div>

      <ChartGestureControls {...gestures} />

      {/* 2. Chart Canvas */}
      <div
        ref={gestures.surfaceRef}
        className={`relative w-full touch-pan-y select-none ${gestures.isDragging ? "cursor-grabbing" : "cursor-grab"}`}
        style={{ touchAction: "pan-y" }}
        {...gestures.handlers}
      >
        <ChartResetButton visible={gestures.isViewportModified} onReset={gestures.reset} />
        <ResponsiveContainer width="100%" height={380}>
          <LineChart
            data={chartData}
            margin={{ top: 15, right: 30, left: 10, bottom: 15 }}
          >
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="dateKey"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              tickFormatter={(val) => {
                const item = chartData.find((d) => d.dateKey === val);
                return item ? item.displayDate : val;
              }}
              minTickGap={25}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              domain={yDomain}
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

            {/* Continuous Solid Line for Historical Actual Close */}
            <Line
              type="linear"
              dataKey="actualClose"
              name={hideModelBreakdown ? "Actual Close" : "Actual close (latest)"}
              stroke="var(--chart-actual-line)"
              strokeWidth={2.5}
              dot={renderActualDot}
              activeDot={{ r: 5 }}
              connectNulls={false}
            />

            {hideModelBreakdown ? (
              /* Single Dashed Branch for Selected Model Prediction in Beginner Mode */
              <Line
                type="linear"
                dataKey="predictedClose"
                name="Predicted Close"
                stroke="#3b82f6"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={renderPredictionDot("#3b82f6")}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />
            ) : (
              /* 3 Model Branches in Advanced Mode */
              <>
                {/* Dashed Branch for ARIMA Next Day */}
                <Line
                  type="linear"
                  dataKey="arimaNext"
                  name="ARIMA (next day)"
                  stroke="#a855f7"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={renderPredictionDot("#a855f7")}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                />

                {/* Dashed Branch for Lag-Informed Regression Next Day */}
                <Line
                  type="linear"
                  dataKey="lagNext"
                  name="Lag-Informed Regression (next day)"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={renderPredictionDot("#38bdf8")}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                />

                {/* Dashed Branch for LSTM Next Day */}
                <Line
                  type="linear"
                  dataKey="lstmNext"
                  name="LSTM (next day)"
                  stroke="#f97316"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={renderPredictionDot("#f97316")}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 3. Prediction Values Quick Cards & Notes (Hidden in Beginner mode) */}
      {!hideModelBreakdown && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
            <div className="bg-dark-bg border border-dark-border rounded-lg p-2.5 text-center">
              <p className="text-[11px] text-slate-400 uppercase tracking-wider">Latest Actual Close</p>
              <p className="text-sm sm:text-base font-bold text-white mt-0.5">
                {formatPeso(previousClose)}
              </p>
              <p className="text-[10px] text-slate-500">{dataAsOf ? `as of ${formatDate(dataAsOf)}` : ""}</p>
            </div>
            <div className="bg-dark-bg border border-[#a855f7]/30 rounded-lg p-2.5 text-center">
              <p className="text-[11px] text-[#c084fc] font-medium uppercase tracking-wider">
                ARIMA Forecast
              </p>
              <p className="text-sm sm:text-base font-bold text-[#c084fc] mt-0.5">
                {nextClose.arima !== undefined ? formatPeso(nextClose.arima) : "--"}
              </p>
              <p className="text-[10px] text-slate-500">
                {nextClose.arima !== undefined && previousClose
                  ? `${nextClose.arima >= previousClose ? "+" : ""}${((nextClose.arima - previousClose) / previousClose * 100).toFixed(2)}%`
                  : ""}
              </p>
            </div>
            <div className="bg-dark-bg border border-[#38bdf8]/30 rounded-lg p-2.5 text-center">
              <p className="text-[11px] text-[#38bdf8] font-medium uppercase tracking-wider">
                Lag-Reg Forecast
              </p>
              <p className="text-sm sm:text-base font-bold text-[#38bdf8] mt-0.5">
                {nextClose.lag !== undefined ? formatPeso(nextClose.lag) : "--"}
              </p>
              <p className="text-[10px] text-slate-500">
                {nextClose.lag !== undefined && previousClose
                  ? `${nextClose.lag >= previousClose ? "+" : ""}${((nextClose.lag - previousClose) / previousClose * 100).toFixed(2)}%`
                  : ""}
              </p>
            </div>
            <div className="bg-dark-bg border border-[#f97316]/30 rounded-lg p-2.5 text-center">
              <p className="text-[11px] text-[#fb923c] font-medium uppercase tracking-wider">
                LSTM Forecast
              </p>
              <p className="text-sm sm:text-base font-bold text-[#fb923c] mt-0.5">
                {nextClose.lstm !== undefined ? formatPeso(nextClose.lstm) : "--"}
              </p>
              <p className="text-[10px] text-slate-500">
                {nextClose.lstm !== undefined && previousClose
                  ? `${nextClose.lstm >= previousClose ? "+" : ""}${((nextClose.lstm - previousClose) / previousClose * 100).toFixed(2)}%`
                  : ""}
              </p>
            </div>
          </div>

          {/* 4. Notes and Methodology Footer */}
          <div className="pt-3 border-t border-dark-border/60 text-xs text-slate-400 space-y-1 leading-relaxed">
            <p>
              <strong className="text-slate-300 font-medium">Notes: </strong>
              Broken lines represent next-day predictions for{" "}
              <strong className="text-slate-300">{formatDate(forecastDate)}</strong> (the next trading
              session).
            </p>
            <p className="text-[11px] text-slate-500">
              ARIMA = AutoRegressive Integrated Moving Average &middot; Lag-Informed Regression =
              Lag-Informed Regression &middot; LSTM = Long Short-Term Memory.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
