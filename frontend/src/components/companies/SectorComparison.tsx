"use client";

import React, { useEffect, useState } from "react";
import SectorSnapshot from "./SectorSnapshot";
import SectorComparisonChart from "./SectorComparisonChart";
import SectorMetricsTable from "./SectorMetricsTable";
import { computeSectorSnapshot } from "@/lib/sectorComparison";
import type { CompanyDetail, CompanySummary } from "@/lib/types";

interface SectorComparisonProps {
  sector: string;
  companies: CompanySummary[];
}

export default function SectorComparison({ sector, companies }: SectorComparisonProps) {
  const [details, setDetails] = useState<CompanyDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Only fetch for specific sectors, never for "All"
    if (!sector || sector === "All" || companies.length === 0) {
      setDetails([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const symbols = companies.map((c) => c.symbol);

    Promise.all(
      symbols.map(async (sym) => {
        const res = await fetch(`/forecasts/company/${sym.toUpperCase()}.json`, {
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
        setLoading(false);
        setError(null);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError("Sector comparison is temporarily unavailable.");
        setLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [sector, companies]);

  if (!sector || sector === "All") {
    return null;
  }

  // Loading skeleton below the 3 company cards
  if (loading) {
    return (
      <div className="mt-10 pt-8 border-t border-dark-border/60 space-y-6">
        <div className="space-y-1">
          <div className="h-7 w-64 bg-dark-card/80 animate-pulse rounded-md" />
          <div className="h-4 w-96 bg-dark-card/50 animate-pulse rounded-md" />
        </div>
        <div className="rounded-2xl border border-dark-border bg-dark-card/60 p-6 flex flex-col items-center justify-center min-h-[220px] text-center space-y-3">
          <div className="w-8 h-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          <p className="text-sm font-medium text-slate-300">
            Loading {sector} comparison...
          </p>
          <p className="text-xs text-slate-500">
            Retrieving historical series and evaluation metrics for {companies.map((c) => c.symbol).join(", ")}
          </p>
        </div>
      </div>
    );
  }

  // Graceful error state (keeps company cards above fully functional)
  if (error || details.length === 0) {
    return (
      <div className="mt-10 pt-8 border-t border-dark-border/60">
        <div className="rounded-xl border border-dark-border bg-dark-card p-5 text-center space-y-2">
          <p className="text-sm font-semibold text-slate-300">
            {error || "Sector comparison is temporarily unavailable."}
          </p>
          <p className="text-xs text-slate-500">
            The three {sector} company cards above remain fully accessible.
          </p>
        </div>
      </div>
    );
  }

  const snapshot = computeSectorSnapshot(details);

  return (
    <section
      aria-label={`${sector} Sector Comparison`}
      className="mt-10 pt-8 border-t border-dark-border space-y-8"
    >
      {/* Sector Comparison Header */}
      <div className="space-y-1.5">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-brand-500/10 text-brand-400 border border-brand-500/20 mb-1">
          Sector Deep-Dive
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          {sector} Sector Comparison
        </h2>
        <p className="text-sm text-slate-400 max-w-3xl leading-relaxed">
          Compare the three selected {sector} companies using their historical actual prices,
          selected-model predictions, and current evaluation metrics.
        </p>
        <p className="text-xs text-slate-500 pt-0.5">
          Descriptive comparison of the three selected companies in this study. Results should not
          be generalized to the entire PSE sector.
        </p>
      </div>

      {/* Section 1: Sector Snapshot */}
      <SectorSnapshot snapshot={snapshot} />

      {/* Section 2: Actual vs Selected Model Line Chart */}
      <SectorComparisonChart companies={details} />

      {/* Section 3: Side-by-Side Stock Metrics */}
      <SectorMetricsTable companies={details} />

      {/* Bottom Methodological Note */}
      <div className="rounded-xl border border-dark-border/60 bg-dark-bg/50 p-4 text-xs text-slate-400 leading-relaxed">
        <span className="font-semibold text-slate-300">Methodological Context:</span>{" "}
        This comparison evaluates only the three equities per sector included in the research design.
        Model selections reflect held-out RMSE evidence on historical evaluation sessions and do not
        constitute financial advice, trading signals, or investment recommendations.
      </div>
    </section>
  );
}
