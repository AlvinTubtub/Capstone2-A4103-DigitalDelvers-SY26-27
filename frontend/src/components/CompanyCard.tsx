import Link from "next/link";
import ChangeBadge from "./ChangeBadge";
import CompanyLogo from "./CompanyLogo";
import WatchlistStar from "./watchlist/WatchlistStar";
import { formatDate, formatPeso } from "@/lib/format";
import type { CompanySummary } from "@/lib/types";

export default function CompanyCard({ company }: { company: CompanySummary }) {
  return (
    <article className="group relative space-y-3 rounded-xl border border-dark-border bg-dark-card p-5 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-brand-500/80 hover:shadow-lg hover:shadow-brand-500/10 focus-within:-translate-y-1 focus-within:border-brand-500 focus-within:shadow-lg motion-reduce:transform-none">
      <Link
        href={`/companies/${company.symbol}`}
        className="absolute inset-0 z-10 cursor-pointer rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg"
        aria-label={`View ${company.symbol}, ${company.name}`}
      />

      <div className="pointer-events-none relative flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <CompanyLogo symbol={company.symbol} name={company.name} size="md" />
          <p className="text-lg font-bold leading-tight text-white transition-colors group-hover:text-brand-300">
            {company.symbol}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="pointer-events-auto relative z-20">
            <WatchlistStar symbol={company.symbol} showLabel size="sm" />
          </span>
          <ChangeBadge pctChange={company.pctChange} />
        </div>
      </div>

      <p className="pointer-events-none relative min-h-10 text-sm leading-snug text-slate-400">
        {company.name}
      </p>

      <div className="pointer-events-none relative border-t border-dark-border/50 pt-3">
        <div>
          <p className="text-xs text-slate-500">Forecasted Close</p>
          <p className="text-lg font-semibold text-white">{formatPeso(company.predictedClose)}</p>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
          {company.forecastDate ? (
            <span>Forecast for {formatDate(company.forecastDate)}</span>
          ) : (
            <span />
          )}
          <span className="rounded-md border border-dark-border bg-dark-bg px-2 py-0.5 text-[11px] text-slate-400">
            {company.sector}
          </span>
        </div>
      </div>
    </article>
  );
}
