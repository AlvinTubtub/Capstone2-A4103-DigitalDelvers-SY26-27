"use client";

import React from "react";
import StockMetricsComparison from "@/components/comparison/StockMetricsComparison";
import type { CompanyDetail } from "@/lib/types";

interface SectorMetricsTableProps {
  companies: CompanyDetail[];
}

export default function SectorMetricsTable({ companies }: SectorMetricsTableProps) {
  return (
    <StockMetricsComparison
      companies={companies}
      title="Side-by-Side Stock Metrics"
      subtitle="Compare current forecast values and evaluation information for the three selected companies."
    />
  );
}
