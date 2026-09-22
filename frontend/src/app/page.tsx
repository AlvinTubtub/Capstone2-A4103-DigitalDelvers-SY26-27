import Link from "next/link";
import CompanyLogo from "@/components/CompanyLogo";
import BrandLogo from "@/components/BrandLogo";
import ChangeBadge from "@/components/ChangeBadge";
import { getCompanies, getDashboard } from "@/lib/data";
import { formatDate, formatDateTimePht, formatPct, formatPeso } from "@/lib/format";

interface SectorCardItem {
  name: string;
  queryParam: string;
  image: string;
  description: string;
  tickers: string[];
}

const SECTOR_CARDS: SectorCardItem[] = [
  {
    name: "Financials",
    queryParam: "Financials",
    image: "/images/sectors/financials.jpg",
    description: "Banking, capital markets & financial institutions",
    tickers: ["BPI", "MBT", "SECB"],
  },
  {
    name: "Industrial",
    queryParam: "Industrial",
    image: "/images/sectors/industrial.jpg",
    description: "Utilities, power distribution & food manufacturing",
    tickers: ["MER", "JFC", "SHLPH"],
  },
  {
    name: "Mining & Oil",
    queryParam: "Mining and Oil",
    image: "/images/sectors/mining-and-oil.jpg",
    description: "Resource extraction, minerals & energy generation",
    tickers: ["APX", "NIKL", "SCC"],
  },
  {
    name: "Property",
    queryParam: "Property",
    image: "/images/sectors/property.jpg",
    description: "Real estate development, commercial leasing & malls",
    tickers: ["ALI", "SMPH", "MEG"],
  },
  {
    name: "Services",
    queryParam: "Services",
    image: "/images/sectors/services.jpg",
    description: "Telecommunications, retail grocers & port management",
    tickers: ["GLO", "PGOLD", "ICT"],
  },
];

interface BeginnerGuideCardItem {
  step: number;
  title: string;
  image: string;
  alt: string;
  href: string;
  description: string;
}

const BEGINNER_GUIDE_CARDS: BeginnerGuideCardItem[] = [
  {
    step: 1,
    title: "Understand the Forecast",
    image: "/images/learn/understand-forecast.jpg",
    alt: "Trader inspecting stock forecast projections on transparent display",
    href: "/learn-stocks#how-to-read",
    description:
      "PSE Pulse predicts the estimated next trading-day closing price based on numerical historical market data. Predictions are statistical estimates and are not guaranteed.",
  },
  {
    step: 2,
    title: "Check Historical Accuracy",
    image: "/images/learn/check-historical-accuracy.jpg",
    alt: "Analyst inspecting stock market line chart and historical prediction accuracy",
    href: "/learn-stocks#forecast-accuracy",
    description:
      "Always review the Backtest, Forecast Error, RMSE, MAE, MASE, and supplementary holdout R² to understand historical evaluation performance before interpreting a forecast.",
  },
  {
    step: 3,
    title: "Learn Before You Trade",
    image: "/images/learn/learn-before-you-trade.jpg",
    alt: "Traders reviewing market candlestick charts on laptop and tablet",
    href: "/learn-stocks#trading-101",
    description:
      "Build a strong foundation in Philippine stock market fundamentals, risk management, and order types before making financial decisions.",
  },
];

export default async function HomePage() {
  const [dashboard, companies] = await Promise.all([
    getDashboard(),
    getCompanies(),
  ]);

  return (
    <div className="space-y-8">
      {/* 1. Hero Section: Full-Bleed Makati Skyline with Centered Content */}
      <section className="relative w-screen left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] -mt-8 mb-10 overflow-hidden bg-slate-950 min-h-[380px] sm:min-h-[460px] lg:min-h-[520px] max-h-[560px] flex items-center justify-center border-b border-slate-800/80 shadow-2xl dark-surface">
        {/* Full-width Skyline Background Image */}
        <div
          className="absolute inset-0 bg-cover bg-center sm:bg-[center_32%] bg-no-repeat pointer-events-none"
          style={{
            backgroundImage: "url('/images/makati-skyline.jpg')",
          }}
          aria-hidden="true"
        />

        {/* Ambient Vignette & Center Radial Overlay: Keeps towers & sky vibrant while centering contrast under text */}
        <div
          className="absolute inset-0 bg-gradient-to-b from-slate-950/70 via-slate-950/45 to-slate-950/85 pointer-events-none"
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-950/85 via-slate-950/40 to-transparent pointer-events-none"
          aria-hidden="true"
        />

        {/* Hero Content: Centered Horizontally & Vertically */}
        <div className="relative z-10 w-full max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-16 text-center flex flex-col items-center justify-center">
          <div className="inline-flex items-center gap-2.5 sm:gap-3 px-4 py-2 sm:px-5 sm:py-2.5 lg:px-6 lg:py-3 bg-slate-950/80 border border-brand-400/50 rounded-full mb-6 sm:mb-8 backdrop-blur-md shadow-lg">
            <BrandLogo variant="mark" size="md" />
            <span className="text-base sm:text-lg lg:text-xl font-bold tracking-tight !text-white">
              PSE Pulse
            </span>
          </div>

          <h1 className="text-2xl sm:text-4xl lg:text-5xl font-extrabold !text-white mb-4 tracking-tight leading-tight max-w-3xl drop-shadow-[0_2px_16px_rgba(0,0,0,0.95)]">
            Cross-Sector Next-Day Stock Price Forecasting
          </h1>

          <p className="!text-slate-100 text-sm sm:text-base lg:text-lg max-w-2xl mx-auto leading-relaxed drop-shadow-[0_1px_8px_rgba(0,0,0,0.9)]">
            Explore historical Philippine stock market data, compare machine learning and statistical
            models, and understand next-day price prediction techniques.
          </p>

          {(dashboard?.forecastDate || dashboard?.lastRunAt) && (
            <div className="inline-flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 mt-6 px-4 py-2 rounded-full bg-slate-950/75 border border-white/20 text-xs !text-slate-200 backdrop-blur-md shadow-md drop-shadow-[0_1px_4px_rgba(0,0,0,0.9)]">
              {dashboard?.forecastDate && (
                <span className="!text-blue-300 font-semibold">
                  Forecast for: {formatDate(dashboard.forecastDate)}
                </span>
              )}
              {dashboard?.forecastDate && dashboard?.lastRunAt && (
                <span className="!text-slate-400">&middot;</span>
              )}
              {dashboard?.lastRunAt && (
                <span className="!text-slate-200">
                  Last pipeline run: {formatDateTimePht(dashboard.lastRunAt)}
                </span>
              )}
            </div>
          )}
        </div>
      </section>

      {/* 2. Summary Grid: Interactive Metric Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Companies Tracked (Clickable -> /companies) */}
        <Link
          href="/companies"
          className="group bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:shadow-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg motion-reduce:transform-none flex flex-col justify-between"
          aria-label={`View all ${dashboard?.totalCompanies ?? 15} tracked companies on the Companies page`}
        >
          <div className="flex items-start justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 group-hover:text-slate-200 transition-colors">
              Companies Tracked
            </span>
            <div className="w-8 h-8 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center group-hover:bg-brand-500 group-hover:text-white transition-colors shrink-0 shadow-xs">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl sm:text-3xl font-extrabold text-white group-hover:text-brand-400 transition-colors">
              {String(dashboard?.totalCompanies ?? "--")}
            </div>
            <div className="flex items-center justify-between text-xs text-brand-400 mt-1 font-medium">
              <span>View all companies</span>
              <span className="transition-transform group-hover:translate-x-0.5">→</span>
            </div>
          </div>
        </Link>

        {/* 2. Sectors Represented (Clickable -> #explore-by-sector) */}
        <a
          href="#explore-by-sector"
          className="group bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:shadow-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg motion-reduce:transform-none flex flex-col justify-between"
          aria-label="Scroll to explore all 5 sectors"
        >
          <div className="flex items-start justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 group-hover:text-slate-200 transition-colors">
              Sectors Represented
            </span>
            <div className="w-8 h-8 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center group-hover:bg-purple-500 group-hover:text-white transition-colors shrink-0 shadow-xs">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl sm:text-3xl font-extrabold text-white group-hover:text-purple-300 transition-colors">
              {String(dashboard?.sectors.length ?? "--")}
            </div>
            <div className="flex items-center justify-between text-xs text-purple-400 mt-1 font-medium">
              <span>Explore sectors</span>
              <span className="transition-transform group-hover:translate-y-0.5">↓</span>
            </div>
          </div>
        </a>

        {/* 3. Forecasted Gainers / Losers (Informational Only - NOT clickable) */}
        <div
          className="bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm flex flex-col justify-between"
          aria-label={`Forecasted market movements: ${dashboard?.marketSummary.gainers ?? 0} gainers, ${dashboard?.marketSummary.losers ?? 0} losers`}
        >
          <div className="flex items-start justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Forecasted Gainers / Losers
            </span>
            <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shrink-0 shadow-xs">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-baseline gap-2">
              <span className="text-emerald-400">{dashboard?.marketSummary.gainers ?? 0}</span>
              <span className="text-slate-500 text-xl font-normal">/</span>
              <span className="text-rose-400">{dashboard?.marketSummary.losers ?? 0}</span>
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Next-session expectations
            </div>
          </div>
        </div>

        {/* 4. Data Source (Clickable -> external PSE report) */}
        <a
          href="https://www.pse.com.ph/market-report/"
          target="_blank"
          rel="noopener noreferrer"
          className="group bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:shadow-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg motion-reduce:transform-none flex flex-col justify-between"
          aria-label="Official PSE Daily Quotations Reports (opens in a new tab)"
        >
          <div className="flex items-start justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 group-hover:text-slate-200 transition-colors">
              Data Source
            </span>
            <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center group-hover:bg-cyan-500 group-hover:text-white transition-colors shrink-0 shadow-xs">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            <div className="text-sm font-bold text-white group-hover:text-cyan-300 transition-colors leading-snug">
              Official PSE Daily Reports
            </div>
            <div className="flex items-center justify-between text-xs text-cyan-400 mt-1 font-medium">
              <span>View PSE Market Report</span>
              <svg className="w-3 h-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </div>
          </div>
        </a>
      </section>

      {/* 3. Compact company outlook */}
      <section className="overflow-hidden rounded-2xl border border-dark-border bg-dark-card shadow-sm">
        <div className="border-b border-dark-border px-5 py-5 sm:px-6">
          <h2 className="text-xl font-bold tracking-tight text-white sm:text-2xl">
            Companies at a Glance
          </h2>
          <p className="mt-1 text-xs text-slate-400 sm:text-sm">
            Quickly compare the latest close and next-day PSE Pulse outlook across all tracked companies.
          </p>
        </div>

        <div className="max-h-[400px] overflow-y-scroll overscroll-contain" aria-label="All tracked companies">
          <div
            className="sticky top-0 z-10 hidden grid-cols-[0.8fr_1.2fr_repeat(3,minmax(0,1fr))] border-b border-dark-border bg-dark-card px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400 sm:grid sm:px-6"
            aria-hidden="true"
          >
            <span>Company</span>
            <span>Sector</span>
            <span className="text-right">Close</span>
            <span className="text-right">Next-Day</span>
            <span className="text-right">Expected Change</span>
          </div>

          <ul className="divide-y divide-dark-border/60">
            {companies.map((company) => {
              const changeColor =
                company.pctChange > 0
                  ? "text-emerald-400"
                  : company.pctChange < 0
                    ? "text-rose-400"
                    : "text-slate-400";

              return (
                <li key={company.symbol}>
                  <Link
                    href={`/companies/${company.symbol}`}
                    className="group grid cursor-pointer grid-cols-2 gap-x-4 gap-y-3 px-5 py-4 outline-none transition-colors hover:bg-brand-500/5 focus-visible:bg-brand-500/10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-400 sm:grid-cols-[0.8fr_1.2fr_repeat(3,minmax(0,1fr))] sm:items-center sm:gap-0 sm:px-6 sm:py-3 motion-reduce:transition-none"
                    aria-label={`View ${company.symbol}: close ${formatPeso(company.latestClose)}, next-day forecast ${formatPeso(company.predictedClose)}, expected change ${formatPct(company.pctChange)}`}
                  >
                    <span className="flex items-center gap-2 font-bold text-white transition-colors group-hover:text-brand-300">
                      <CompanyLogo symbol={company.symbol} name={company.name} size="xs" />
                      {company.symbol}
                    </span>
                    <span className="text-right text-xs text-slate-400 sm:text-left sm:text-sm">
                      <span className="sr-only sm:hidden">Sector: </span>
                      {company.sector}
                    </span>
                    <span className="text-sm text-slate-300 sm:text-right">
                      <span className="mb-0.5 block text-[10px] uppercase tracking-wide text-slate-500 sm:hidden">Close</span>
                      {formatPeso(company.latestClose)}
                    </span>
                    <span className="text-right text-sm font-semibold text-white">
                      <span className="mb-0.5 block text-[10px] uppercase tracking-wide text-slate-500 sm:hidden">Next-Day</span>
                      {formatPeso(company.predictedClose)}
                    </span>
                    <span className={`col-span-2 text-right text-sm font-semibold tabular-nums sm:col-span-1 ${changeColor}`}>
                      <span className="mr-2 text-[10px] font-medium uppercase tracking-wide text-slate-500 sm:hidden">Expected Change</span>
                      {formatPct(company.pctChange)}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      {/* 4. Top Forecasted Gainer & Loser Spotlight Cards */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Top Forecasted Gainer Spotlight Card */}
        {dashboard?.topGainer ? (
          <Link
            href={`/companies/${dashboard.topGainer.symbol}`}
            className="group relative rounded-2xl overflow-hidden border border-slate-700/60 dark:border-dark-border bg-gradient-to-br from-dark-card to-emerald-950/25 hover:border-emerald-500/60 focus-visible:border-emerald-500 p-6 shadow-sm hover:shadow-xl hover:shadow-emerald-500/10 focus-visible:shadow-xl hover:-translate-y-1 focus-visible:-translate-y-1 transition-all duration-300 outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg motion-reduce:transform-none flex flex-col justify-between"
            aria-label={`View top forecasted gainer: ${dashboard.topGainer.symbol} (${dashboard.topGainer.name})`}
          >
            <div>
              {/* Header: Spotlight Badge & Sector */}
              <div className="flex items-center justify-between gap-2 mb-4">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 shadow-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Top Forecasted Gainer
                </span>
                <span className="text-xs text-slate-400 font-medium">
                  {dashboard.topGainer.sector}
                </span>
              </div>

              {/* Body: Logo, Ticker, Name & Predicted Price */}
              <div className="flex items-center justify-between gap-4 py-1">
                <div className="flex items-center gap-3.5 min-w-0">
                  <CompanyLogo symbol={dashboard.topGainer.symbol} name={dashboard.topGainer.name} size="lg" />
                  <div className="min-w-0">
                    <div className="text-2xl sm:text-3xl font-black text-white group-hover:text-emerald-300 transition-colors leading-tight">
                      {dashboard.topGainer.symbol}
                    </div>
                    <p className="text-xs sm:text-sm text-slate-300 truncate max-w-[13rem] sm:max-w-[16rem]">
                      {dashboard.topGainer.name}
                    </p>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Predicted Close
                  </span>
                  <p className="text-2xl sm:text-3xl font-extrabold text-white group-hover:text-emerald-400 transition-colors">
                    {formatPeso(dashboard.topGainer.predictedClose)}
                  </p>
                  <div className="mt-1 flex justify-end">
                    <ChangeBadge pctChange={dashboard.topGainer.pctChange} />
                  </div>
                </div>
              </div>
            </div>

            {/* Directional Footer Link */}
            <div className="flex items-center justify-between pt-4 mt-5 border-t border-slate-700/50 dark:border-dark-border/80 text-xs font-semibold text-emerald-400 group-hover:text-emerald-300 transition-colors">
              <span>View company forecast</span>
              <span className="transition-transform group-hover:translate-x-1 font-bold">→</span>
            </div>
          </Link>
        ) : (
          <div className="bg-dark-card border border-dark-border rounded-2xl p-6 text-slate-500 text-sm">
            No gainer data available.
          </div>
        )}

        {/* Top Forecasted Loser Spotlight Card */}
        {dashboard?.topLoser ? (
          <Link
            href={`/companies/${dashboard.topLoser.symbol}`}
            className="group relative rounded-2xl overflow-hidden border border-slate-700/60 dark:border-dark-border bg-gradient-to-br from-dark-card to-rose-950/25 hover:border-rose-500/60 focus-visible:border-rose-500 p-6 shadow-sm hover:shadow-xl hover:shadow-rose-500/10 focus-visible:shadow-xl hover:-translate-y-1 focus-visible:-translate-y-1 transition-all duration-300 outline-none focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg motion-reduce:transform-none flex flex-col justify-between"
            aria-label={`View top forecasted loser: ${dashboard.topLoser.symbol} (${dashboard.topLoser.name})`}
          >
            <div>
              {/* Header: Spotlight Badge & Sector */}
              <div className="flex items-center justify-between gap-2 mb-4">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/15 border border-rose-500/30 text-rose-400 shadow-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
                  Top Forecasted Loser
                </span>
                <span className="text-xs text-slate-400 font-medium">
                  {dashboard.topLoser.sector}
                </span>
              </div>

              {/* Body: Logo, Ticker, Name & Predicted Price */}
              <div className="flex items-center justify-between gap-4 py-1">
                <div className="flex items-center gap-3.5 min-w-0">
                  <CompanyLogo symbol={dashboard.topLoser.symbol} name={dashboard.topLoser.name} size="lg" />
                  <div className="min-w-0">
                    <div className="text-2xl sm:text-3xl font-black text-white group-hover:text-rose-300 transition-colors leading-tight">
                      {dashboard.topLoser.symbol}
                    </div>
                    <p className="text-xs sm:text-sm text-slate-300 truncate max-w-[13rem] sm:max-w-[16rem]">
                      {dashboard.topLoser.name}
                    </p>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Predicted Close
                  </span>
                  <p className="text-2xl sm:text-3xl font-extrabold text-white group-hover:text-rose-400 transition-colors">
                    {formatPeso(dashboard.topLoser.predictedClose)}
                  </p>
                  <div className="mt-1 flex justify-end">
                    <ChangeBadge pctChange={dashboard.topLoser.pctChange} />
                  </div>
                </div>
              </div>
            </div>

            {/* Directional Footer Link */}
            <div className="flex items-center justify-between pt-4 mt-5 border-t border-slate-700/50 dark:border-dark-border/80 text-xs font-semibold text-rose-400 group-hover:text-rose-300 transition-colors">
              <span>View company forecast</span>
              <span className="transition-transform group-hover:translate-x-1 font-bold">→</span>
            </div>
          </Link>
        ) : (
          <div className="bg-dark-card border border-dark-border rounded-2xl p-6 text-slate-500 text-sm">
            No loser data available.
          </div>
        )}
      </section>

      {/* 5. Beginner Guide Section: Image-led Learning Cards */}
      <section className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-7 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="inline-block px-2.5 py-0.5 text-[11px] font-semibold text-brand-400 bg-brand-500/10 border border-brand-500/20 rounded-full mb-1">
              Beginner Guide
            </span>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              New to Stock Forecasting?
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Three quick rules for interpreting automated machine learning stock predictions.
            </p>
          </div>
          <Link
            href="/learn-stocks#trading-101"
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs sm:text-sm font-semibold transition-all shrink-0 self-start sm:self-auto shadow-md shadow-brand-500/20 group"
          >
            <span>Start with Stock Trading 101</span>
            <span className="transition-transform group-hover:translate-x-0.5">→</span>
          </Link>
        </div>

        {/* 3 Responsive Image Cards: 1 col mobile, 2 col tablet, 3 col desktop */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {BEGINNER_GUIDE_CARDS.map((card) => (
            <Link
              key={card.title}
              href={card.href}
              className="group rounded-2xl overflow-hidden border border-slate-700/60 dark:border-dark-border bg-dark-bg/70 hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-xl hover:shadow-brand-500/10 focus-visible:shadow-xl transition-all duration-300 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg motion-reduce:transform-none flex flex-col"
              aria-label={`${card.title} — ${card.description}`}
            >
              {/* 16:9 Image Area with subtle zoom on hover/focus */}
              <div className="relative aspect-video w-full overflow-hidden bg-slate-900">
                <img
                  src={card.image}
                  alt={card.alt}
                  className="w-full h-full object-cover transition-transform duration-300 ease-out group-hover:scale-105 group-focus-visible:scale-105 motion-reduce:transform-none"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/75 via-transparent to-transparent pointer-events-none" />
              </div>

              {/* Text Content Below Image */}
              <div className="p-5 flex-1 flex flex-col justify-between space-y-3">
                <div className="space-y-1.5">
                  <h3 className="text-base font-bold text-white group-hover:text-brand-300 transition-colors flex items-center justify-between">
                    <span>{card.title}</span>
                    <span className="text-xs text-brand-400 transition-transform group-hover:translate-x-0.5">
                      →
                    </span>
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {card.description}
                  </p>
                </div>
                <div className="pt-2 border-t border-dark-border/60 text-[11px] font-medium text-brand-400 flex items-center gap-1 group-hover:underline">
                  <span>Learn how this works</span>
                  <span className="transition-transform group-hover:translate-x-0.5">→</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* 6. Explore by Sector Section */}
      <section id="explore-by-sector" className="space-y-4 scroll-mt-24">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Explore by Sector</h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Browse 15 Philippine Stock Exchange listed companies organized across 5 core sectors.
            </p>
          </div>
          <Link
            href="/companies"
            className="inline-flex items-center text-sm font-medium text-brand-400 hover:text-brand-300 group self-start sm:self-auto"
          >
            <span>View all companies</span>
            <span className="ml-1 transition-transform group-hover:translate-x-0.5">→</span>
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
          {SECTOR_CARDS.map((sector) => (
            <Link
              key={sector.name}
              href={`/companies?sector=${encodeURIComponent(sector.queryParam)}`}
              className="group relative rounded-2xl overflow-hidden border border-slate-700/60 dark:border-dark-border bg-slate-900 aspect-[16/10] flex flex-col justify-end p-5 transition-all duration-300 hover:-translate-y-1 focus-visible:-translate-y-1 hover:border-brand-500/80 focus-visible:border-brand-500 hover:shadow-xl hover:shadow-brand-500/10 focus-visible:shadow-xl outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg motion-reduce:transform-none dark-surface"
              aria-label={`Explore ${sector.name} sector: ${sector.tickers.join(", ")}`}
            >
              {/* Background image with subtle zoom out on hover/focus (scale-[1.04] to scale-100 over 300ms) */}
              <img
                src={sector.image}
                alt=""
                aria-hidden="true"
                className="absolute inset-0 w-full h-full object-cover scale-[1.04] group-hover:scale-100 group-focus-visible:scale-100 transition-transform duration-300 ease-out motion-reduce:transform-none"
              />

              {/* Dark overlay ensuring high text readability & contrast across themes */}
              <div
                className="absolute inset-0 bg-gradient-to-t from-slate-950/95 via-slate-950/60 to-slate-950/20 group-hover:from-slate-950/90 transition-colors pointer-events-none"
                aria-hidden="true"
              />

              {/* Sector Card Content */}
              <div className="relative z-10 space-y-1.5 pointer-events-none">
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-block text-[11px] font-semibold !text-blue-300 tracking-wider uppercase drop-shadow-sm">
                    Sector
                  </span>
                  <div className="w-7 h-7 rounded-full bg-white/20 group-hover:bg-brand-500 !text-white flex items-center justify-center transition-colors shadow-sm">
                    <svg
                      className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5 !text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>

                <h3 className="text-lg sm:text-xl font-bold !text-white tracking-tight group-hover:!text-blue-300 transition-colors drop-shadow-md">
                  {sector.name}
                </h3>

                <p className="text-xs !text-slate-200 line-clamp-1 drop-shadow-sm">
                  {sector.description}
                </p>

                <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px] !text-slate-200">
                  {sector.tickers.map((ticker) => (
                    <span
                      key={ticker}
                      className="px-1.5 py-0.5 rounded bg-slate-900/90 border border-white/25 font-mono font-medium !text-white"
                    >
                      {ticker}
                    </span>
                  ))}
                  <span className="!text-slate-300 ml-1">· 3 companies</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
