"use client";

import { useMemo, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import CompanyCard from "./CompanyCard";
import SectorComparison from "./companies/SectorComparison";
import type { CompanySummary } from "@/lib/types";

export default function CompanyGrid({ companies }: { companies: CompanySummary[] }) {
  const searchParams = useSearchParams();
  const sectors = useMemo(() => ["All", ...Array.from(new Set(companies.map((c) => c.sector))).sort()], [companies]);
  
  const [sector, setSector] = useState("All");

  useEffect(() => {
    const raw = searchParams.get("sector");
    if (!raw) {
      setSector("All");
      return;
    }
    const normalized = raw.toLowerCase().replace(/&/g, "and").trim();
    const matched = sectors.find(
      (s) => s.toLowerCase().replace(/&/g, "and").trim() === normalized
    );
    if (matched) {
      setSector(matched);
    }
  }, [searchParams, sectors]);

  const filtered = sector === "All" ? companies : companies.filter((c) => c.sector === sector);

  return (
    <div>
      <div className="mb-6 max-w-xs">
        <label htmlFor="sector-filter" className="sr-only">
          Filter by sector
        </label>
        <select
          id="sector-filter"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          className="bg-dark-card border border-dark-border text-sm rounded-lg focus:ring-brand-500 focus:border-brand-500 block w-full p-2.5 text-white"
        >
          {sectors.map((s) => (
            <option key={s} value={s}>
              {s === "All" ? "All Sectors" : s}
            </option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((c) => (
          <CompanyCard key={c.symbol} company={c} />
        ))}
      </div>

      {sector !== "All" && (
        <SectorComparison sector={sector} companies={filtered} />
      )}
    </div>
  );
}
