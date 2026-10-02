"use client";

import { useState, useMemo, useEffect } from "react";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import ChartGestureControls, { ChartResetButton } from "./ChartGestureControls";
import InfoTooltip from "@/components/InfoTooltip";
import { useChartInteractions } from "@/hooks/useChartTouchGestures";
import type { OhlcvPoint } from "@/lib/types";

/**
 * Calendar-aware subtraction of months from a YYYY-MM-DD date string.
 * Accurately handles variable month lengths (e.g. Feb 28/29, 30 vs 31 days)
 * and clamps to the last valid day of the target month.
 */
function subtractMonths(dateStr: string, months: number): string {
  if (!dateStr) return "";
  const parts = dateStr.split("-").map(Number);
  if (parts.length !== 3 || parts.some(isNaN)) return dateStr;
  const [y, m, d] = parts;
  const totalMonths = y * 12 + (m - 1) - months;
  const targetYear = Math.floor(totalMonths / 12);
  const targetMonth = ((totalMonths % 12) + 12) % 12; // 0-indexed (0=Jan, 11=Dec)
  const maxDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();
  const targetDay = Math.min(d, maxDay);
  const mm = String(targetMonth + 1).padStart(2, "0");
  const dd = String(targetDay).padStart(2, "0");
  return `${targetYear}-${mm}-${dd}`;
}

/**
 * Calendar-aware subtraction of years from a YYYY-MM-DD date string.
 */
function subtractYears(dateStr: string, years: number): string {
  return subtractMonths(dateStr, years * 12);
}

export default function HistoryChart({ data }: { data: OhlcvPoint[] }) {
  const earliestAvailableDate = data[0]?.date ?? "";
  const latestAvailableDate = data[data.length - 1]?.date ?? "";

  // Calculate default start date (approx 1 year earlier or earliest available)
  const defaultStartDate = useMemo(() => {
    if (!latestAvailableDate) return "";
    const oneYearAgo = subtractYears(latestAvailableDate, 1);
    return oneYearAgo < earliestAvailableDate ? earliestAvailableDate : oneYearAgo;
  }, [latestAvailableDate, earliestAvailableDate]);

  // Applied date filters for the chart.
  const [appliedStartDate, setAppliedStartDate] = useState<string>(defaultStartDate);
  const [appliedEndDate, setAppliedEndDate] = useState<string>(latestAvailableDate);

  // Controlled input fields for start and end date
  const [startDateInput, setStartDateInput] = useState<string>(defaultStartDate);
  const [endDateInput, setEndDateInput] = useState<string>(latestAvailableDate);
  const [dateError, setDateError] = useState<string | null>(null);
  const [activeQuickRange, setActiveQuickRange] = useState<string>("1Y");

  // Sync inputs if data changes
  useEffect(() => {
    if (data.length > 0) {
      const latest = data[data.length - 1]?.date ?? "";
      const earliest = data[0]?.date ?? "";
      const oneYear = subtractYears(latest, 1);
      const start = oneYear < earliest ? earliest : oneYear;
      setAppliedStartDate(start);
      setAppliedEndDate(latest);
      setStartDateInput(start);
      setEndDateInput(latest);
      setActiveQuickRange("1Y");
      setDateError(null);
    }
  }, [data]);

  // Quick range helper
  const handleQuickRange = (type: "1M" | "3M" | "6M" | "1Y") => {
    if (!latestAvailableDate) return;
    const baseEnd = endDateInput || latestAvailableDate;
    let newStart = "";

    switch (type) {
      case "1M":
        newStart = subtractMonths(baseEnd, 1);
        break;
      case "3M":
        newStart = subtractMonths(baseEnd, 3);
        break;
      case "6M":
        newStart = subtractMonths(baseEnd, 6);
        break;
      case "1Y":
        newStart = subtractYears(baseEnd, 1);
        break;
    }

    if (newStart < earliestAvailableDate) {
      newStart = earliestAvailableDate;
    }

    setStartDateInput(newStart);
    setEndDateInput(baseEnd);
    setAppliedStartDate(newStart);
    setAppliedEndDate(baseEnd);
    setActiveQuickRange(type);
    setDateError(null);
  };

  const handleApplyDateRange = () => {
    if (!startDateInput || !endDateInput) {
      setDateError("Please enter both start and end dates.");
      return;
    }
    if (startDateInput > endDateInput) {
      setDateError("Start date must be on or before end date.");
      return;
    }
    setDateError(null);
    setActiveQuickRange("");
    setAppliedStartDate(startDateInput);
    setAppliedEndDate(endDateInput);
  };

  // Base filtered dataset for the selected date period
  const filteredData = useMemo(() => {
    if (!data || data.length === 0) return [];
    return data.filter((p) => p.date >= appliedStartDate && p.date <= appliedEndDate);
  }, [data, appliedStartDate, appliedEndDate]);

  const gestures = useChartInteractions({
    totalPoints: filteredData.length,
    minWindow: 8,
    resetKey: `${appliedStartDate}:${appliedEndDate}`,
  });
  const chartData = useMemo(
    () => filteredData.slice(gestures.viewport.startIndex, gestures.viewport.endIndex + 1),
    [filteredData, gestures.viewport.endIndex, gestures.viewport.startIndex],
  );

  const [visibleSeries, setVisibleSeries] = useState({
    open: true,
    high: true,
    low: true,
    close: true,
    volume: true,
  });

  const toggleSeries = (key: keyof typeof visibleSeries) => {
    setVisibleSeries((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const visibleStartDate = chartData[0]?.date;
  const visibleEndDate = chartData[chartData.length - 1]?.date;

  return (
    <div className="w-full select-none space-y-3.5">
      {/* 1. PSE EDGE-Style Period & Date Range Control Bar */}
      <div className="bg-dark-card/60 backdrop-blur border border-dark-border rounded-xl p-3 shadow-sm flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-1.5 font-semibold text-slate-200">
            <svg
              className="w-4 h-4 text-brand-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <span>Period:</span>
            <InfoTooltip id="chart-ohlcv-period" />
          </div>

          {/* Date Pickers */}
          <div className="flex items-center gap-1.5">
            <input
              type="date"
              value={startDateInput}
              min={earliestAvailableDate}
              max={endDateInput || latestAvailableDate}
              onChange={(e) => {
                setStartDateInput(e.target.value);
                setActiveQuickRange("");
              }}
              className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-slate-900 dark:text-slate-100 font-medium text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 transition-colors shadow-xs"
              aria-label="Start Date"
            />
            <span className="text-slate-500 font-medium">–</span>
            <input
              type="date"
              value={endDateInput}
              min={startDateInput || earliestAvailableDate}
              max={latestAvailableDate}
              onChange={(e) => {
                setEndDateInput(e.target.value);
                setActiveQuickRange("");
              }}
              className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-slate-900 dark:text-slate-100 font-medium text-xs focus:outline-none focus:ring-1 focus:ring-brand-500 transition-colors shadow-xs"
              aria-label="End Date"
            />
          </div>

          {/* Quick Range Buttons */}
          <div className="flex items-center gap-1 bg-dark-bg/50 border border-dark-border/60 rounded-lg p-0.5">
            {(
              [
                { label: "1 Month", key: "1M" },
                { label: "3 Months", key: "3M" },
                { label: "6 Months", key: "6M" },
                { label: "1 Year", key: "1Y" },
              ] as const
            ).map((btn) => (
              <button
                key={btn.key}
                type="button"
                onClick={() => handleQuickRange(btn.key)}
                className={`px-2.5 py-0.5 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                  activeQuickRange === btn.key
                    ? "bg-brand-600 text-white shadow-xs font-semibold"
                    : "text-slate-400 hover:text-slate-200 hover:bg-dark-card/80"
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>

          {/* Update Chart Button */}
          <button
            type="button"
            onClick={handleApplyDateRange}
            className="px-3 py-1 bg-brand-600 hover:bg-brand-500 text-white font-semibold rounded-lg shadow-xs transition-colors cursor-pointer text-xs flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M5 13l4 4L19 7" />
            </svg>
            Update Chart
          </button>
        </div>

        {/* Info label: Points in current view */}
        <div className="text-slate-400 text-[11px] font-mono whitespace-nowrap ml-auto">
          {visibleStartDate && visibleEndDate ? `${visibleStartDate} – ${visibleEndDate}` : null}{" "}
          <span className="text-slate-500">
            ({chartData.length.toLocaleString()} of {filteredData.length.toLocaleString()} pts)
          </span>
        </div>
      </div>

      {/* Date Validation Error Message */}
      {dateError && (
        <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-lg px-3 py-1.5 flex items-center gap-1.5">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0115.357-6.357" />
          </svg>
          <span>{dateError}</span>
        </div>
      )}

      {/* 2. Series Toggles */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="flex items-center gap-1">
            <span className="text-slate-400 font-medium">Series:</span>
            <InfoTooltip id="chart-ohlcv-series" />
          </div>
          <button
            type="button"
            onClick={() => toggleSeries("open")}
            className={`px-2 py-0.5 rounded border transition-colors cursor-pointer ${
              visibleSeries.open
                ? "bg-amber-500/10 border-amber-500/50 text-amber-400 font-medium"
                : "bg-slate-800/50 border-slate-700 text-slate-500 line-through"
            }`}
          >
            Open
          </button>
          <button
            type="button"
            onClick={() => toggleSeries("high")}
            className={`px-2 py-0.5 rounded border transition-colors cursor-pointer ${
              visibleSeries.high
                ? "bg-green-500/10 border-green-500/50 text-green-400 font-medium"
                : "bg-slate-800/50 border-slate-700 text-slate-500 line-through"
            }`}
          >
            High
          </button>
          <button
            type="button"
            onClick={() => toggleSeries("low")}
            className={`px-2 py-0.5 rounded border transition-colors cursor-pointer ${
              visibleSeries.low
                ? "bg-red-500/10 border-red-500/50 text-red-400 font-medium"
                : "bg-slate-800/50 border-slate-700 text-slate-500 line-through"
            }`}
          >
            Low
          </button>
          <button
            type="button"
            onClick={() => toggleSeries("close")}
            className={`px-2 py-0.5 rounded border transition-colors cursor-pointer ${
              visibleSeries.close
                ? "bg-blue-500/10 border-blue-500/50 text-blue-400 font-medium"
                : "bg-slate-800/50 border-slate-700 text-slate-500 line-through"
            }`}
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => toggleSeries("volume")}
            className={`px-2 py-0.5 rounded border transition-colors cursor-pointer ${
              visibleSeries.volume
                ? "bg-sky-500/10 border-sky-500/50 text-sky-400 font-medium"
                : "bg-slate-800/50 border-slate-700 text-slate-500 line-through"
            }`}
          >
            Volume
          </button>
        </div>

        <div className="flex items-center gap-1 text-slate-400">
          <span>Legend</span>
          <InfoTooltip id="chart-ohlcv-legend" align="right" />
        </div>
      </div>

      {/* 3. Main Chart or Empty State */}
      {filteredData.length === 0 ? (
        <div className="w-full py-16 text-center text-slate-400 bg-dark-card/40 rounded-xl border border-dark-border px-4">
          <svg className="w-8 h-8 text-slate-500 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <p className="text-sm font-medium text-slate-300">
            No trading sessions found for the period {appliedStartDate} to {appliedEndDate}.
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Please adjust your date range or choose a quick range button above.
          </p>
        </div>
      ) : (
        <div className="w-full space-y-2">
          <ChartGestureControls {...gestures} />
          <div
            ref={gestures.surfaceRef}
            className={`relative w-full touch-pan-y select-none ${gestures.isDragging ? "cursor-grabbing" : "cursor-grab"}`}
            style={{ touchAction: "pan-y" }}
            {...gestures.handlers}
          >
          <ChartResetButton visible={gestures.isViewportModified} onReset={gestures.reset} />
          <ResponsiveContainer width="100%" height={430}>
            <ComposedChart
              data={chartData}
              margin={{ top: 15, right: 10, left: 0, bottom: 0 }}
            >
              <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} minTickGap={35} />
              <YAxis
                yAxisId="price"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                domain={["auto", "auto"]}
                tickFormatter={(val) => `₱${val}`}
              />
              <YAxis yAxisId="volume" orientation="right" tick={{ fill: "#94a3b8", fontSize: 11 }} hide />
              <Tooltip
                contentStyle={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  fontSize: 12,
                  boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
                }}
                labelStyle={{ color: "#f8fafc", fontWeight: 600, marginBottom: 4 }}
                formatter={(value: any, name: any) => {
                  const num = Number(value);
                  if (isNaN(num)) return [value, name];
                  if (name === "Volume") {
                    return [num.toLocaleString(), "Volume"];
                  }
                  return [`₱${num.toFixed(2)}`, name];
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 6 }} />

              {/* Volume Area */}
              {visibleSeries.volume && (
                <Area
                  yAxisId="volume"
                  type="monotone"
                  dataKey="volume"
                  name="Volume"
                  fill="#3b82f6"
                  stroke="none"
                  fillOpacity={0.15}
                />
              )}

              {/* OHLC Lines */}
              {visibleSeries.open && (
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="open"
                  name="Open"
                  stroke="#f59e0b"
                  dot={false}
                  strokeWidth={1.2}
                />
              )}
              {visibleSeries.high && (
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="high"
                  name="High"
                  stroke="#22c55e"
                  dot={false}
                  strokeWidth={1.2}
                />
              )}
              {visibleSeries.low && (
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="low"
                  name="Low"
                  stroke="#ef4444"
                  dot={false}
                  strokeWidth={1.2}
                />
              )}
              {visibleSeries.close && (
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="close"
                  name="Close"
                  stroke="#60a5fa"
                  dot={false}
                  strokeWidth={2}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
