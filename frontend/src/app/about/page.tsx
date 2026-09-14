import Link from "next/link";
import CompanyLogo from "@/components/CompanyLogo";
import { getCompanies, getDashboard } from "@/lib/data";
import { formatDate, formatDateTimePht } from "@/lib/format";
import type { CompanySummary } from "@/lib/types";

interface SectorInfo {
  name: string;
  queryParam: string;
  icon: string;
  description: string;
}

const SECTOR_INFO: Record<string, SectorInfo> = {
  Financials: {
    name: "Financials",
    queryParam: "Financials",
    icon: "🏦",
    description: "Universal commercial banks, capital lending, and retail financial services driving economic liquidity.",
  },
  Industrial: {
    name: "Industrial",
    queryParam: "Industrial",
    icon: "⚡",
    description: "Power distribution utilities, energy infrastructure, quick-service food manufacturing, and petroleum retailing.",
  },
  "Mining and Oil": {
    name: "Mining & Oil",
    queryParam: "Mining and Oil",
    icon: "⛏️",
    description: "Mineral resource exploration, precious metal extraction, thermal coal mining, and energy generation.",
  },
  Property: {
    name: "Property",
    queryParam: "Property",
    icon: "🏢",
    description: "Integrated real estate developers, commercial office leasing, residential master-planned estates, and retail shopping malls.",
  },
  Services: {
    name: "Services",
    queryParam: "Services",
    icon: "📡",
    description: "Nationwide telecommunications, maritime container terminal operations, and chain supermarket retailing.",
  },
};

export default async function AboutPage() {
  const [dashboard, companies] = await Promise.all([getDashboard(), getCompanies()]);

  const totalCompanies = dashboard?.totalCompanies ?? companies.length;
  const sectorCount = dashboard?.sectors?.length ?? 5;
  const lastPipelineRun = formatDateTimePht(dashboard?.lastRunAt || dashboard?.generatedAt);
  const forecastSessionDate = formatDate(dashboard?.forecastDate);

  // Group companies by sector for dynamic coverage display
  const companiesBySector = companies.reduce<Record<string, CompanySummary[]>>((acc, company) => {
    const key = company.sector || "Other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(company);
    return acc;
  }, {});

  const sectorsToDisplay = dashboard?.sectors?.length
    ? dashboard.sectors.map((s) => s.name)
    : Object.keys(companiesBySector);

  return (
    <div className="space-y-12 pb-16">
      {/* ================================================================
          WHAT FORECASTPH DOES
      ================================================================ */}
      <section className="space-y-6">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Platform Mission
          </span>
          <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            What ForecastPH Does
          </h1>
          <p className="text-sm text-slate-400 leading-relaxed">
            Cross-sector, next-day Philippine stock-price forecasting and empirical model comparison designed to bridge quantitative data science with practical equity education.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 space-y-3 shadow-sm hover:border-brand-500/60 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/30 text-brand-400 flex items-center justify-center text-xl">
              🌐
            </div>
            <h3 className="font-bold text-white text-base">Cross-Sector Evaluation</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Monitors {totalCompanies} key equities across {sectorCount} distinct Philippine economic sectors rather than isolating a single company or market-wide composite index.
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 space-y-3 shadow-sm hover:border-emerald-500/60 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center text-xl">
              📈
            </div>
            <h3 className="font-bold text-white text-base">Next-Session Targets</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Ingests verified closing prices to predict the subsequent trading session&apos;s expected price movement and closing target in Philippine Pesos (₱).
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 space-y-3 shadow-sm hover:border-purple-500/60 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 text-purple-400 flex items-center justify-center text-xl">
              ⚖️
            </div>
            <h3 className="font-bold text-white text-base">Multi-Model Benchmarks</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Competitively compares three machine-learning and econometric architectures against a random-walk naïve baseline to evaluate genuine forecasting utility.
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 space-y-3 shadow-sm hover:border-amber-500/60 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-400 flex items-center justify-center text-xl">
              🎓
            </div>
            <h3 className="font-bold text-white text-base">Educational Decision Support</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Converts complex statistical time-series outputs into interactive charts, error distributions, and accessible metrics for students and budding traders.
            </p>
          </div>
        </div>
      </section>

      {/* ================================================================
          3. HOW IT WORKS: Visual Process Flow
      ================================================================ */}
      <section className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Methodological Pipeline
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            How ForecastPH Works
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            A 5-stage automated pipeline transforming authoritative market disclosures into audited next-day closing projections.
          </p>
        </div>

        {/* Responsive Process Steps */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 relative">
          {/* Step 1 */}
          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-4.5 space-y-3 flex flex-col justify-between relative group hover:border-brand-500/60 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-brand-500/15 text-brand-400 border border-brand-500/30">
                  Step 1
                </span>
                <span className="text-lg">📥</span>
              </div>
              <h3 className="text-sm font-bold text-white leading-snug">
                Historical PSE Data
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Ingestion of official PSE Daily Quotations Reports at the 3:15 PM PHT market close, gathering multi-year daily OHLCV records.
              </p>
            </div>
            <div className="text-[11px] font-semibold text-brand-400 pt-2 border-t border-dark-border/50 flex items-center justify-between">
              <span>Raw Market Data</span>
              <span className="hidden lg:inline text-slate-500">→</span>
            </div>
          </div>

          {/* Step 2 */}
          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-4.5 space-y-3 flex flex-col justify-between relative group hover:border-cyan-500/60 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                  Step 2
                </span>
                <span className="text-lg">⚙️</span>
              </div>
              <h3 className="text-sm font-bold text-white leading-snug">
                Data Preparation
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Chronological splitting (85% dev / 15% holdout) with rolling-origin validation, feature scaling, and lag creation with zero lookahead bias.
              </p>
            </div>
            <div className="text-[11px] font-semibold text-cyan-400 pt-2 border-t border-dark-border/50 flex items-center justify-between">
              <span>Cleaned Features</span>
              <span className="hidden lg:inline text-slate-500">→</span>
            </div>
          </div>

          {/* Step 3 */}
          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-4.5 space-y-3 flex flex-col justify-between relative group hover:border-purple-500/60 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30">
                  Step 3
                </span>
                <span className="text-lg">🧠</span>
              </div>
              <h3 className="text-sm font-bold text-white leading-snug">
                Multiple Models
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Parallel training of Lag-Informed LASSO Regression, classical ARIMA, and recurrent LSTM deep neural networks under uniform conditions.
              </p>
            </div>
            <div className="text-[11px] font-semibold text-purple-400 pt-2 border-t border-dark-border/50 flex items-center justify-between">
              <span>Trained Predictors</span>
              <span className="hidden lg:inline text-slate-500">→</span>
            </div>
          </div>

          {/* Step 4 */}
          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-4.5 space-y-3 flex flex-col justify-between relative group hover:border-emerald-500/60 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  Step 4
                </span>
                <span className="text-lg">🎯</span>
              </div>
              <h3 className="text-sm font-bold text-white leading-snug">
                Next-Session Forecast
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Inference calculates expected percentage changes and reconstructs the target next-day closing price in Philippine Pesos (₱).
              </p>
            </div>
            <div className="text-[11px] font-semibold text-emerald-400 pt-2 border-t border-dark-border/50 flex items-center justify-between">
              <span>Target Projections</span>
              <span className="hidden lg:inline text-slate-500">→</span>
            </div>
          </div>

          {/* Step 5 */}
          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-4.5 space-y-3 flex flex-col justify-between relative group hover:border-amber-500/60 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                  Step 5
                </span>
                <span className="text-lg">🛡️</span>
              </div>
              <h3 className="text-sm font-bold text-white leading-snug">
                Backtest & Evaluation
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Chronological out-of-sample evaluation calculating RMSE, MAE, development-scaled MASE, and supplementary R² on common target dates.
              </p>
            </div>
            <div className="text-[11px] font-semibold text-amber-400 pt-2 border-t border-dark-border/50 flex items-center justify-between">
              <span>Audited Accuracy</span>
              <span className="text-emerald-400">✓ Done</span>
            </div>
          </div>
        </div>
      </section>

      {/* ================================================================
          4. COVERAGE (Dynamically Generated from Repository Data)
      ================================================================ */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
              Active Universe
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Market Coverage
            </h2>
            <p className="text-sm text-slate-400 max-w-xl">
              Dynamically derived from live repository records, spanning liquid equities across core Philippine sectors.
            </p>
          </div>

          {/* Dynamic Summary Badges */}
          <div className="flex items-center gap-3">
            <div className="px-4 py-2 rounded-xl bg-dark-card border border-dark-border text-center shadow-xs">
              <span className="block text-xl font-extrabold text-white">{totalCompanies}</span>
              <span className="text-[11px] text-slate-400 font-medium">Companies Tracked</span>
            </div>
            <div className="px-4 py-2 rounded-xl bg-dark-card border border-dark-border text-center shadow-xs">
              <span className="block text-xl font-extrabold text-brand-400">{sectorCount}</span>
              <span className="text-[11px] text-slate-400 font-medium">PSE Sectors</span>
            </div>
          </div>
        </div>

        {/* 5 Sector Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sectorsToDisplay.map((sectorKey) => {
            const info = SECTOR_INFO[sectorKey] || {
              name: sectorKey,
              queryParam: sectorKey,
              icon: "📊",
              description: "Public equities listed on the Philippine Stock Exchange.",
            };
            const sectorCompanies = companiesBySector[sectorKey] || [];

            return (
              <div
                key={sectorKey}
                className="bg-dark-card border border-dark-border rounded-2xl p-5 space-y-4 shadow-sm flex flex-col justify-between hover:border-brand-500/50 transition-colors"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{info.icon}</span>
                      <h3 className="font-bold text-white text-base">{info.name}</h3>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-dark-bg border border-dark-border text-slate-300">
                      {sectorCompanies.length} Stocks
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{info.description}</p>
                </div>

                <div className="space-y-2 pt-3 border-t border-dark-border/60">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Tracked Tickers:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {sectorCompanies.map((c) => (
                      <Link
                        key={c.symbol}
                        href={`/companies/${c.symbol}`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-dark-bg border border-dark-border hover:border-brand-400/60 hover:text-brand-300 text-xs font-semibold text-slate-200 transition-colors"
                        title={c.name}
                      >
                        <CompanyLogo symbol={c.symbol} name={c.name} size="xs" />
                        <span>{c.symbol}</span>
                      </Link>
                    ))}
                  </div>

                  <div className="pt-1">
                    <Link
                      href={`/companies?sector=${encodeURIComponent(info.queryParam)}`}
                      className="text-xs font-semibold text-brand-400 hover:text-brand-300 inline-flex items-center gap-1 transition-colors"
                    >
                      Filter {info.name} on Companies page →
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ================================================================
          5. MODELS USED: Plain-Language Architecture Descriptions
      ================================================================ */}
      <section className="space-y-6">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Forecasting Architectures
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Models Used in ForecastPH
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Three mathematically diverse model paradigms evaluated under identical chronological splits to identify which architecture best captures Philippine price behaviors.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Lag Regression */}
          <div className="bg-dark-card border border-dark-border rounded-2xl p-6 space-y-4 shadow-sm flex flex-col justify-between hover:border-emerald-500/50 transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                  Interpretable ML
                </span>
                <span className="text-2xl">🧮</span>
              </div>
              <h3 className="text-lg font-bold text-white">Lag-Informed Regression</h3>
              <p className="text-xs text-brand-400 font-medium">
                Regularized Linear Autoregression (LASSO)
              </p>
              <p className="text-xs text-slate-300 leading-relaxed">
                Uses recent historical closing prices and trading volumes (time-lagged features) to model the next-day price change. Applies LASSO (L1 regularization) to eliminate uninformative signals and prevent overfitting.
              </p>
            </div>

            <div className="pt-3 border-t border-dark-border/60 space-y-2 text-xs">
              <div className="text-slate-400">
                <strong className="text-slate-200">Key Strengths:</strong> High mathematical transparency, rapid computation, and resilience against noise in steady market conditions.
              </div>
              <div className="text-slate-400">
                <strong className="text-slate-200">Best Suited For:</strong> Equities with consistent momentum and stable historical price relationships.
              </div>
            </div>
          </div>

          {/* ARIMA */}
          <div className="bg-dark-card border border-dark-border rounded-2xl p-6 space-y-4 shadow-sm flex flex-col justify-between hover:border-blue-500/50 transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-500/15 border border-blue-500/30 text-blue-400">
                  Statistical Standard
                </span>
                <span className="text-2xl">📉</span>
              </div>
              <h3 className="text-lg font-bold text-white">ARIMA</h3>
              <p className="text-xs text-blue-400 font-medium">
                Autoregressive Integrated Moving Average
              </p>
              <p className="text-xs text-slate-300 leading-relaxed">
                A foundational econometric time-series method that models temporal dependencies directly within the price series. It combines autoregression of past values, differencing for stationarity, and moving averages of forecast errors.
              </p>
            </div>

            <div className="pt-3 border-t border-dark-border/60 space-y-2 text-xs">
              <div className="text-slate-400">
                <strong className="text-slate-200">Key Strengths:</strong> Rigorous mathematical formulation, longstanding use in financial economics, and explicit mean-reversion structure.
              </div>
              <div className="text-slate-400">
                <strong className="text-slate-200">Best Suited For:</strong> Stocks exhibiting pronounced cyclical patterns or stationary short-term fluctuations.
              </div>
            </div>
          </div>

          {/* LSTM */}
          <div className="bg-dark-card border border-dark-border rounded-2xl p-6 space-y-4 shadow-sm flex flex-col justify-between hover:border-purple-500/50 transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-500/15 border border-purple-500/30 text-purple-400">
                  Deep Learning
                </span>
                <span className="text-2xl">🧠</span>
              </div>
              <h3 className="text-lg font-bold text-white">LSTM</h3>
              <p className="text-xs text-purple-400 font-medium">
                Long Short-Term Memory Recurrent Neural Network
              </p>
              <p className="text-xs text-slate-300 leading-relaxed">
                A specialized recurrent deep learning architecture equipped with internal memory cells and gating mechanisms (input, forget, output gates) that retain contextual signals across multi-day sequences without suffering from vanishing gradients.
              </p>
            </div>

            <div className="pt-3 border-t border-dark-border/60 space-y-2 text-xs">
              <div className="text-slate-400">
                <strong className="text-slate-200">Key Strengths:</strong> Ability to detect non-linear sequence dependencies, regime transitions, and complex interactions across multiple sessions.
              </div>
              <div className="text-slate-400">
                <strong className="text-slate-200">Best Suited For:</strong> Volatile equities where price dynamics follow non-linear trajectory patterns.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ================================================================
          6. UNDERSTANDING ACCURACY: Backtesting & Metrics
      ================================================================ */}
      <section className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Empirical Validation
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Understanding Forecast Accuracy
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            How model performance is objectively quantified, why backtesting eliminates forward-looking bias, and what the statistical metrics mean.
          </p>
        </div>

        {/* Why Backtesting Matters Card */}
        <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-5 space-y-2.5">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-bold text-base">🛡️</span>
            <h3 className="font-bold text-white text-base">Why Out-of-Sample Backtesting Matters</h3>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            In machine learning, testing a model on the same data used to train it leads to misleadingly optimistic results (overfitting). ForecastPH enforces strict <strong className="text-white">chronological splitting</strong> with zero lookahead bias: 85% of historical data forms the development dataset, while the final 15% is reserved as an untouched hold-out test set. Backtesting measures how models would have performed during real historical trading days when tomorrow&apos;s closing price was genuinely unknown.
          </p>
        </div>

        {/* The 4 Core Metrics Explained */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-4.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">Metric 1</span>
              <span className="text-xs font-semibold text-emerald-400">Lower is better</span>
            </div>
            <h4 className="font-bold text-white text-base">RMSE</h4>
            <p className="text-[11px] text-slate-400 font-medium">Root Mean Square Error</p>
            <p className="text-xs text-slate-300 leading-relaxed">
              Measures the average magnitude of prediction errors in Philippine Pesos (₱). Because misses are squared before averaging, large errors are penalized much more heavily than small ones.
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-4.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">Metric 2</span>
              <span className="text-xs font-semibold text-emerald-400">Lower is better</span>
            </div>
            <h4 className="font-bold text-white text-base">MAE</h4>
            <p className="text-[11px] text-slate-400 font-medium">Mean Absolute Error</p>
            <p className="text-xs text-slate-300 leading-relaxed">
              Calculates the average absolute difference between predicted and actual prices in Pesos (₱). It provides an intuitive, linear measure of typical forecast error without disproportionately overweighting outliers.
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-brand-500/40 rounded-xl p-4.5 space-y-2 relative shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">Metric 3</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                &lt; 1.0 = Below Development Scale
              </span>
            </div>
            <h4 className="font-bold text-white text-base">MASE</h4>
            <p className="text-[11px] text-slate-400 font-medium">Mean Absolute Scaled Error</p>
            <p className="text-xs text-slate-300 leading-relaxed">
              Evaluation MAE divided by one common one-step absolute-change scale calculated from each company&apos;s development Close series.
              <span className="block mt-1 text-emerald-300 font-semibold">
                MASE &lt; 1.0 does not by itself prove lower held-out error than the separately evaluated Naive method.
              </span>
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-4.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">Metric 4</span>
              <span className="text-xs font-semibold text-emerald-400">Supplementary metric</span>
            </div>
            <h4 className="font-bold text-white text-base">Holdout R² — Supplementary Metric</h4>
            <p className="text-[11px] text-slate-400 font-medium">Coefficient of Determination</p>
            <p className="text-xs text-slate-300 leading-relaxed">
              Compares squared holdout errors with a reference based on the holdout-period mean. Higher is generally better, but values can be negative. R² is not percentage accuracy and is not used for tuning, winner selection, promotion, or deployment.
            </p>
          </div>
        </div>

        {/* Evaluation Design Callout */}
        <div className="p-4.5 rounded-xl bg-dark-bg/60 border border-dark-border text-xs space-y-1.5 text-slate-300">
          <div className="flex items-center gap-2 font-bold text-white text-sm">
            <span>🔬</span>
            <span>Common Chronological Evaluation</span>
          </div>
          <p className="leading-relaxed text-slate-400">
            ForecastPH evaluates Lag-Informed Regression, ARIMA, LSTM, and the Naive benchmark on the same held-out target dates for each company. The best principal model is the lowest-RMSE deployable model; the best evaluated method also includes Naive and may therefore differ.
          </p>
        </div>
      </section>

      {/* ================================================================
          7. DATA SOURCE AND REFRESH PIPELINE
      ================================================================ */}
      <section className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
              Data Governance & Automation
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Data Source & Refresh Rhythm
            </h2>
            <p className="text-sm text-slate-400 max-w-xl">
              Forecasts are generated exclusively from authoritative public disclosures published by the exchange.
            </p>
          </div>

          <a
            href="https://www.pse.com.ph/market-report/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-xs transition-colors shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            <span>Official PSE Market Reports</span>
            <span>↗</span>
          </a>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-4.5 space-y-2">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
              Official Primary Source
            </span>
            <h4 className="text-base font-bold text-white">PSE Daily Quotations Reports</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Authoritative daily end-of-day reports published on the Philippine Stock Exchange portal providing audited OHLCV data.
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-4.5 space-y-2">
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider block">
              Latest Automated Inference
            </span>
            <h4 className="text-base font-bold text-white">{lastPipelineRun}</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              Automated timestamp recorded when the pipeline last processed quotation reports and updated forecast targets.
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-4.5 space-y-2">
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider block">
              Active Forecast Horizon
            </span>
            <h4 className="text-base font-bold text-white">{forecastSessionDate}</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              The next designated Philippine trading session for which model closing projections are targeted.
            </p>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-dark-bg/60 border border-dark-border text-xs text-slate-400 space-y-1 leading-relaxed">
          <strong className="text-white block">Trading Hours & Pipeline Trigger:</strong>
          Philippine equity trading takes place Monday through Friday, 9:30 AM to 3:00 PM PHT (closing auction 2:45–2:50 PM, run-off trading 2:50–3:00 PM). The PSE publishes official Daily Quotations Reports at approximately 3:15 PM PHT, triggering automated inference runs ahead of the next session.
        </div>
      </section>

      {/* ================================================================
          8. IMPORTANT LIMITATIONS & RESPONSIBLE USE
      ================================================================ */}
      <section className="bg-gradient-to-br from-dark-card to-amber-950/15 border border-amber-500/30 rounded-2xl p-6 sm:p-8 space-y-5 shadow-sm relative overflow-hidden">
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-amber-500/20 text-amber-300 flex items-center justify-center font-bold text-lg">
            ⚠️
          </span>
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Important Limitations & Educational Disclaimer
            </h2>
            <p className="text-xs text-amber-300/80 font-medium">
              Decision-support guidelines for responsible market exploration
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-300 leading-relaxed">
          <div className="p-4 rounded-xl bg-dark-bg/80 border border-dark-border space-y-1.5">
            <h3 className="font-bold text-white text-sm">Educational Decision Support Only</h3>
            <p className="text-slate-400">
              ForecastPH is strictly an academic capstone research platform. Forecasts, model rankings, and backtest metrics are model-generated estimates for educational exploration and <strong className="text-white">never constitute financial advice, investment recommendations, or automated trading signals</strong>.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-dark-bg/80 border border-dark-border space-y-1.5">
            <h3 className="font-bold text-white text-sm">Numerical Data Boundaries</h3>
            <p className="text-slate-400">
              Models evaluate historical price and volume patterns. They cannot anticipate breaking news, corporate earnings surprises, macroeconomic policy changes, regulatory decisions, geopolitical events, or sudden shifts in market liquidity.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-dark-bg/80 border border-dark-border space-y-1.5">
            <h3 className="font-bold text-white text-sm">No Guaranteed Returns</h3>
            <p className="text-slate-400">
              Historical accuracy during backtests does not guarantee future forecasting success. Equity investments involve significant capital risk, including the possible loss of principal.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-dark-bg/80 border border-dark-border space-y-1.5">
            <h3 className="font-bold text-white text-sm">Independent Due Diligence</h3>
            <p className="text-slate-400">
              Users must perform thorough fundamental analysis and consult registered SEC-licensed investment advisors before executing trades in the Philippine market.
            </p>
          </div>
        </div>
      </section>

      {/* ================================================================
          9. LEARN MORE & EXPLORE FURTHER
      ================================================================ */}
      <section className="space-y-6">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Navigation Suite
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Explore ForecastPH
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Continue your exploration of Philippine equities, machine learning models, and trading mechanics.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link
            href="/learn-stocks"
            className="group bg-dark-card border border-dark-border rounded-2xl p-5 shadow-sm hover:border-emerald-500/80 hover:-translate-y-1 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center text-xl">
                📚
              </div>
              <h3 className="font-bold text-white text-base group-hover:text-emerald-300 transition-colors">
                Learn Stocks
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Foundational guide covering trading sessions, glossary terms, chart reading, and SEC broker directory.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-emerald-400">
              <span>Start Learning</span>
              <span className="transition-transform group-hover:translate-x-1">→</span>
            </div>
          </Link>

          <Link
            href="/companies"
            className="group bg-dark-card border border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 hover:-translate-y-1 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-500/30 text-brand-400 flex items-center justify-center text-xl">
                🏢
              </div>
              <h3 className="font-bold text-white text-base group-hover:text-brand-300 transition-colors">
                Companies
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Inspect 15 tracked companies across 5 sectors, toggle Beginner/Advanced views, and track favorites.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-brand-400">
              <span>Browse Equities</span>
              <span className="transition-transform group-hover:translate-x-1">→</span>
            </div>
          </Link>

          <Link
            href="/compare"
            className="group bg-dark-card border border-dark-border rounded-2xl p-5 shadow-sm hover:border-purple-500/80 hover:-translate-y-1 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 text-purple-400 flex items-center justify-center text-xl">
                📊
              </div>
              <h3 className="font-bold text-white text-base group-hover:text-purple-300 transition-colors">
                Models
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Compare current evaluation metrics, RMSE winners, and Naive-benchmark performance across Lag Reg, ARIMA, and LSTM.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-purple-400">
              <span>Compare Architectures</span>
              <span className="transition-transform group-hover:translate-x-1">→</span>
            </div>
          </Link>

          <a
            href="https://www.pse.com.ph/market-report/"
            target="_blank"
            rel="noopener noreferrer"
            className="group bg-dark-card border border-dark-border rounded-2xl p-5 shadow-sm hover:border-cyan-500/80 hover:-translate-y-1 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 flex items-center justify-center text-xl">
                📑
              </div>
              <h3 className="font-bold text-white text-base group-hover:text-cyan-300 transition-colors">
                Official PSE Reports
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Access official Daily Quotations, market indices, and exchange disclosures directly from PSE.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-cyan-400">
              <span>Visit PSE Portal</span>
              <span className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5">↗</span>
            </div>
          </a>
        </div>
      </section>
    </div>
  );
}
