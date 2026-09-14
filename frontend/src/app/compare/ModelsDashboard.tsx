"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import CompanyLogo from "@/components/CompanyLogo";
import StatCard from "@/components/StatCard";
import { formatDate, formatNum } from "@/lib/format";

export type OperationalModelId = "lag_reg" | "arima" | "lstm" | "naive";
type PrincipalModelId = Exclude<OperationalModelId, "naive">;
type MetricId = "rmse" | "mae" | "mase" | "r2";
type WinnerFilter = "all" | PrincipalModelId;
type SortKey = "symbol" | "winner" | "evaluatedWinner" | MetricId | "vsNaive";
type MetricValues = Record<MetricId, number>;

export interface ModelPerformanceRow {
  symbol: string;
  name: string;
  metrics: Record<OperationalModelId, MetricValues>;
  bestPrincipalModel: string;
  bestEvaluatedMethod: string;
  bestPrincipalBeatsNaive: boolean;
  allPrincipalsWorseThanNaive: boolean;
}

interface ModelsDashboardProps {
  rows: ModelPerformanceRow[];
  evaluationForecasts: number | null;
  evaluationCount: number | null;
  evaluationStart: string | null;
  evaluationEnd: string | null;
  evaluationMetadataAvailable: boolean;
}

const PRINCIPAL_MODELS: PrincipalModelId[] = ["lag_reg", "arima", "lstm"];
const ALL_MODELS: OperationalModelId[] = [...PRINCIPAL_MODELS, "naive"];
const MODEL_LABELS: Record<OperationalModelId, string> = {
  lag_reg: "Lag-Informed Regression", arima: "ARIMA", lstm: "LSTM", naive: "Naive",
};
const MODEL_COLORS: Record<OperationalModelId, string> = {
  lag_reg: "#3b82f6", arima: "#f59e0b", lstm: "#a855f7", naive: "#64748b",
};
const METRIC_COPY: Record<MetricId, { label: string; direction: string }> = {
  rmse: { label: "RMSE", direction: "Lower is better" },
  mae: { label: "MAE", direction: "Lower is better" },
  mase: { label: "MASE", direction: "Lower is better" },
  r2: { label: "Holdout R²", direction: "Supplementary; higher is generally better" },
};

function principalWinner(row: ModelPerformanceRow): PrincipalModelId {
  return PRINCIPAL_MODELS.reduce((best, model) =>
    row.metrics[model].rmse < row.metrics[best].rmse ? model : best,
  );
}

function allPrincipalsWorseThanNaive(row: ModelPerformanceRow): boolean {
  return row.allPrincipalsWorseThanNaive;
}

function median(values: number[]): number {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function improvementVsNaive(row: ModelPerformanceRow): number {
  const winner = principalWinner(row);
  const naive = row.metrics.naive.rmse;
  return ((naive - row.metrics[winner].rmse) / naive) * 100;
}

function MetricTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { label: string; value: number } }> }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return <div className="rounded-lg border border-dark-border bg-dark-bg px-3 py-2 shadow-xl"><p className="text-xs font-semibold text-white">{item.label}</p><p className="mt-1 font-mono text-sm text-brand-400">{formatNum(item.value, 6)}</p></div>;
}

function WinsTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { label: string; wins: number; percentage: number } }> }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return <div className="rounded-lg border border-dark-border bg-dark-bg px-3 py-2 shadow-xl"><p className="text-xs font-semibold text-white">{item.label}</p><p className="mt-1 text-sm text-brand-400">{item.wins} companies ({item.percentage.toFixed(1)}%)</p></div>;
}

export default function ModelsDashboard({ rows, evaluationForecasts, evaluationCount, evaluationStart, evaluationEnd, evaluationMetadataAvailable }: ModelsDashboardProps) {
  const [company, setCompany] = useState("all");
  const [metric, setMetric] = useState<MetricId>("mase");
  const [winnerFilter, setWinnerFilter] = useState<WinnerFilter>("all");
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: "symbol", ascending: true });

  const wins = useMemo(() => {
    const counts: Record<PrincipalModelId, number> = { lag_reg: 0, arima: 0, lstm: 0 };
    rows.forEach((row) => { counts[principalWinner(row)] += 1; });
    return PRINCIPAL_MODELS.map((model) => ({ model, label: MODEL_LABELS[model], wins: counts[model], percentage: (counts[model] / rows.length) * 100 }));
  }, [rows]);

  const comparisonData = useMemo(() => ALL_MODELS.map((model) => {
    const selected = company === "all" ? rows : rows.filter((row) => row.symbol === company);
    const value = company === "all" ? median(selected.map((row) => row.metrics[model][metric])) : selected[0].metrics[model][metric];
    return { model, label: MODEL_LABELS[model], value };
  }), [company, metric, rows]);

  const leaderboard = useMemo(() => {
    const filtered = winnerFilter === "all" ? rows : rows.filter((row) => principalWinner(row) === winnerFilter);
    return [...filtered].sort((left, right) => {
      const leftWinner = principalWinner(left);
      const rightWinner = principalWinner(right);
      const leftValue = sort.key === "symbol" ? left.symbol : sort.key === "winner" ? left.bestPrincipalModel : sort.key === "evaluatedWinner" ? left.bestEvaluatedMethod : sort.key === "vsNaive" ? improvementVsNaive(left) : left.metrics[leftWinner][sort.key];
      const rightValue = sort.key === "symbol" ? right.symbol : sort.key === "winner" ? right.bestPrincipalModel : sort.key === "evaluatedWinner" ? right.bestEvaluatedMethod : sort.key === "vsNaive" ? improvementVsNaive(right) : right.metrics[rightWinner][sort.key];
      const result = typeof leftValue === "string" ? leftValue.localeCompare(String(rightValue)) : leftValue - Number(rightValue);
      return sort.ascending ? result : -result;
    });
  }, [rows, sort, winnerFilter]);

  const updateSort = (key: SortKey) => setSort((current) => ({ key, ascending: current.key === key ? !current.ascending : true }));
  const productionModels = PRINCIPAL_MODELS.length * rows.length;
  const naiveOutperformsAllCount = rows.filter(allPrincipalsWorseThanNaive).length;
  const comparisonDescription = company !== "all"
    ? `Current evaluation metrics for ${company}.`
    : metric === "mase"
      ? "Median MASE across companies is scale-independent."
      : "Select one company to inspect scale-dependent or supplementary metrics.";

  return (
    <div className="space-y-8 sm:space-y-10">
      <header><h1 className="text-2xl font-bold text-white sm:text-3xl">Models</h1><p className="mt-2 max-w-3xl text-sm text-slate-400 sm:text-base">Compare how ForecastPH models perform across all {rows.length} PSE-listed companies. Results come from the latest fresh model training and chronological out-of-sample evaluation.</p></header>

      <section aria-label="Model performance summary" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Companies" value={String(rows.length)} sublabel="Current operational evaluation" />
        <StatCard label="Evaluation Forecasts" value={evaluationForecasts?.toLocaleString() ?? "--"} sublabel={evaluationMetadataAvailable ? "Complete aligned holdout records across all methods" : "Full evaluation metadata pending next fresh export"} accent="text-cyan-400" />
        <StatCard label="Evaluation Window" value={evaluationCount ? `${evaluationCount} sessions` : evaluationMetadataAvailable ? "Company-specific" : "--"} sublabel={evaluationStart && evaluationEnd ? `${formatDate(evaluationStart)} – ${formatDate(evaluationEnd)}` : "Not inferred from the 60-session display subset"} accent="text-amber-300" />
        <StatCard label="Production Models" value={productionModels.toLocaleString()} sublabel={`${rows.length} companies × ${PRINCIPAL_MODELS.length} principal models`} accent="text-emerald-400" />
      </section>

      {naiveOutperformsAllCount > 0 ? (
        <section role="status" className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          <strong>Naive benchmark warning:</strong> all three principal models had higher evaluation RMSE than Naive for {naiveOutperformsAllCount} {naiveOutperformsAllCount === 1 ? "company" : "companies"}. In those cases, the reported best principal model is not the best evaluated method.
        </section>
      ) : null}

      <section className="rounded-2xl border border-dark-border bg-dark-card p-5 shadow-sm sm:p-6">
        <h2 className="text-lg font-bold text-white">Principal-Model RMSE Wins by Company</h2><p className="mt-1 text-xs text-slate-400">Each win is determined within one company. This chart does not average raw peso RMSE across companies; Naive remains a separately evaluated benchmark.</p>
        <div className="models-chart mt-6 h-64 bg-transparent" role="img" aria-label="Horizontal bar chart showing principal model RMSE wins"><ResponsiveContainer width="100%" height="100%"><BarChart data={wins} layout="vertical" margin={{ top: 4, right: 36, left: 22, bottom: 4 }}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" horizontal={false} /><XAxis type="number" allowDecimals={false} domain={[0, rows.length]} tick={{ fill: "var(--chart-axis-text)", fontSize: 11 }} /><YAxis type="category" dataKey="label" width={150} tick={{ fill: "var(--chart-axis-text)", fontSize: 11 }} tickLine={false} /><Tooltip cursor={{ fill: "var(--chart-hover)" }} content={<WinsTooltip />} /><Bar dataKey="wins" radius={[0, 6, 6, 0]} maxBarSize={34}>{wins.map((item) => <Cell key={item.model} fill={MODEL_COLORS[item.model]} />)}</Bar></BarChart></ResponsiveContainer></div>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">{wins.map((item) => <div key={item.model} className="flex items-center justify-between rounded-lg border border-dark-border/60 bg-dark-bg/40 px-3 py-2 text-xs"><span className="text-slate-300">{item.label}</span><strong className="text-white">{item.wins} · {item.percentage.toFixed(1)}%</strong></div>)}</div>
      </section>

      <section className="rounded-2xl border border-dark-border bg-dark-card p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div><h2 className="text-lg font-bold text-white">Compare Model Performance</h2><p className="mt-1 text-xs text-slate-400">{comparisonDescription} {METRIC_COPY[metric].direction}.</p></div><div className="flex flex-col gap-3 sm:flex-row sm:items-end"><label className="text-xs font-semibold text-slate-300">Company<select aria-label="Company" value={company} onChange={(event) => { const value = event.target.value; setCompany(value); if (value === "all") setMetric("mase"); }} className="mt-1 block w-full rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-sm text-white outline-none focus:border-brand-500 sm:w-48"><option value="all">All Companies</option>{rows.map((row) => <option key={row.symbol} value={row.symbol}>{row.symbol}</option>)}</select></label><div role="group" aria-label="Metric" className="flex flex-wrap rounded-lg border border-dark-border bg-dark-bg p-1">{(Object.keys(METRIC_COPY) as MetricId[]).map((key) => { const disabled = company === "all" && key !== "mase"; return <button key={key} type="button" disabled={disabled} aria-pressed={metric === key} onClick={() => setMetric(key)} title={disabled ? "Choose one company for scale-dependent or supplementary metrics" : undefined} className={`rounded-md px-3 py-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${metric === key ? "bg-brand-600 text-white" : "text-slate-300 hover:bg-white/5"}`}>{METRIC_COPY[key].label}</button>; })}</div></div></div>
        <div className="models-chart mt-6 h-72 bg-transparent sm:h-80" role="img" aria-label={`${METRIC_COPY[metric].label} comparison chart for ${company === "all" ? "all companies" : company}`}><ResponsiveContainer width="100%" height="100%"><BarChart data={comparisonData} margin={{ top: 12, right: 8, left: 2, bottom: 30 }}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" interval={0} angle={-12} textAnchor="end" height={64} tick={{ fill: "var(--chart-axis-text)", fontSize: 10 }} /><YAxis tick={{ fill: "var(--chart-axis-text)", fontSize: 11 }} tickFormatter={(value) => Number(value).toPrecision(3)} /><Tooltip cursor={{ fill: "var(--chart-hover)" }} content={<MetricTooltip />} /><Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={90}>{comparisonData.map((item) => <Cell key={item.model} fill={MODEL_COLORS[item.model]} />)}</Bar></BarChart></ResponsiveContainer></div>
      </section>

      <Leaderboard rows={leaderboard} winnerFilter={winnerFilter} setWinnerFilter={setWinnerFilter} sort={sort} updateSort={updateSort} />

    </div>
  );
}

function Leaderboard({ rows, winnerFilter, setWinnerFilter, sort, updateSort }: { rows: ModelPerformanceRow[]; winnerFilter: WinnerFilter; setWinnerFilter: (value: WinnerFilter) => void; sort: { key: SortKey; ascending: boolean }; updateSort: (key: SortKey) => void }) {
  return <section className="rounded-2xl border border-dark-border bg-dark-card p-5 shadow-sm sm:p-6"><div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-lg font-bold text-white">Model Leaderboard</h2><p className="mt-1 text-xs text-slate-400">Best principal model means the lowest-RMSE result among LIR, ARIMA, and LSTM. Best evaluated method also includes Naive.</p></div><div role="group" aria-label="Filter leaderboard by winning model" className="flex flex-wrap gap-2">{(["all", ...PRINCIPAL_MODELS] as WinnerFilter[]).map((filter) => <button key={filter} type="button" aria-pressed={winnerFilter === filter} onClick={() => setWinnerFilter(filter)} className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-colors ${winnerFilter === filter ? "border-brand-500 bg-brand-600 text-white" : "border-dark-border text-slate-300 hover:bg-white/5"}`}>{filter === "all" ? "All" : `${filter === "lag_reg" ? "LIR" : MODEL_LABELS[filter]} winners`}</button>)}</div></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[1080px] text-sm"><thead><tr className="border-b border-dark-border bg-dark-bg/60 text-left text-[11px] uppercase tracking-wide text-slate-400">{([["symbol","Company"],["winner","Best Principal"],["evaluatedWinner","Best Evaluated"],["rmse","RMSE"],["mae","MAE"],["mase","MASE"],["r2","Holdout R² (supp.)"],["vsNaive","vs Naive RMSE"]] as [SortKey,string][]).map(([key, label]) => <th key={key} scope="col" className={key === "symbol" || key === "winner" || key === "evaluatedWinner" ? "px-3 py-3" : "px-3 py-3 text-right"}><button type="button" onClick={() => updateSort(key)} className="inline-flex items-center gap-1 font-semibold hover:text-white">{label}<span aria-hidden="true">{sort.key === key ? (sort.ascending ? "↑" : "↓") : "↕"}</span></button></th>)}</tr></thead><tbody>{rows.map((row) => { const winner = principalWinner(row); const improvement = improvementVsNaive(row); return <tr key={row.symbol} className="border-b border-dark-border/50 last:border-0"><td className="px-3 py-3"><Link href={`/companies/${row.symbol}`} className="inline-flex items-center gap-2 font-bold text-white hover:text-brand-300"><CompanyLogo symbol={row.symbol} size="xs" />{row.symbol}<span className="sr-only"> — {row.name}</span></Link></td><td className="px-3 py-3 text-slate-300">{row.bestPrincipalModel}</td><td className="px-3 py-3 text-slate-300">{row.bestEvaluatedMethod}</td>{(["rmse","mae","mase","r2"] as MetricId[]).map((key) => <td key={key} className="px-3 py-3 text-right font-mono text-slate-300">{formatNum(row.metrics[winner][key], 4)}</td>)}<td className={`px-3 py-3 text-right font-mono font-semibold ${row.bestPrincipalBeatsNaive ? "text-emerald-400" : "text-rose-400"}`}>{improvement >= 0 ? "+" : ""}{improvement.toFixed(2)}%</td></tr>; })}</tbody></table>{rows.length === 0 ? <p className="py-8 text-center text-sm text-slate-400">No companies match this winner filter.</p> : null}</div></section>;
}
