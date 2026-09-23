"use client";

import React from "react";
import StockComparisonChart from "@/components/comparison/StockComparisonChart";
import type { CompanyDetail } from "@/lib/types";

interface SectorComparisonChartProps {
  companies: CompanyDetail[];
}

export default function SectorComparisonChart({ companies }: SectorComparisonChartProps) {
  return (
    <StockComparisonChart
      companies={companies}
      title="Actual vs Selected Model"
      subtitle="Historical actual closing prices versus each company's selected principal-model predictions."
      emptyMessage="No aligned historical sessions available across the selected sector companies."
    />
  );
}
