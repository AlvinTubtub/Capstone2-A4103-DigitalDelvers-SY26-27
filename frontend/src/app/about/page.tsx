import AboutInPageNav from "@/components/about/AboutInPageNav";
import AboutModelsSection from "@/components/about/AboutModelsSection";
import BrandLogo from "@/components/BrandLogo";
import { getCompanies, getDashboard } from "@/lib/data";
import { formatDate, formatDateTimePht } from "@/lib/format";

export default async function AboutPage() {
  const [dashboard, companies] = await Promise.all([
    getDashboard(),
    getCompanies(),
  ]);

  const totalCompanies = dashboard?.totalCompanies ?? companies.length ?? 15;
  const sectorCount = dashboard?.sectors?.length ?? 5;
  const lastPipelineRun = formatDateTimePht(
    dashboard?.lastRunAt || dashboard?.generatedAt,
  );
  const forecastSessionDate = formatDate(dashboard?.forecastDate);

  return (
    <div className="space-y-12 sm:space-y-16 pb-16">
      {/* ================================================================
          ABOUT HERO / RESEARCH OVERVIEW
      ================================================================ */}
      <section className="space-y-6 pt-2">
        <div className="text-center max-w-3xl mx-auto">
          {/* Eyebrow */}
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-brand-500/15 text-brand-400 border border-brand-500/30 mb-4 sm:mb-5">
            RESEARCH & METHODOLOGY
          </div>

          {/* Clean Centered Title Row */}
          <div className="flex items-center justify-center gap-3 sm:gap-4 mb-4 sm:mb-5">
            <BrandLogo variant="mark" size="lg" />
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight leading-tight">
              About PSE Pulse
            </h1>
          </div>

          {/* Formal Research Title */}
          <p className="text-base sm:text-lg font-semibold text-slate-200 tracking-tight max-w-2xl mx-auto mb-3 sm:mb-4">
            Cross-Sector Next-Day Stock Price Forecasting of Selected PSE-Listed Companies
          </p>

          {/* Supporting Description */}
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl mx-auto">
            An educational and research forecasting platform designed to evaluate
            next-session closing prices across liquid Philippine equities.
            PSE Pulse comparatively evaluates three principal forecasting
            models against a Naive benchmark to advance open quantitative
            education—not financial advice.
          </p>
        </div>

        {/* Dynamic Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 flex flex-col justify-between shadow-sm hover:border-brand-500/60 transition-colors h-full">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Tracked Universe
                </span>
                <span className="w-9 h-9 rounded-xl bg-dark-bg/90 border border-dark-border flex items-center justify-center text-lg shrink-0">
                  🏢
                </span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-white">
                {totalCompanies} Companies
              </div>
            </div>
            <p className="text-xs text-slate-400 pt-2.5 border-t border-dark-border/30 mt-3">
              Selected liquid public equities listed on the PSE
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 flex flex-col justify-between shadow-sm hover:border-brand-500/60 transition-colors h-full">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">
                  Economic Breadth
                </span>
                <span className="w-9 h-9 rounded-xl bg-dark-bg/90 border border-dark-border flex items-center justify-center text-lg shrink-0">
                  🌐
                </span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-white">
                {sectorCount} PSE Sectors
              </div>
            </div>
            <p className="text-xs text-slate-400 pt-2.5 border-t border-dark-border/30 mt-3">
              Financials, Industrial, Mining/Oil, Property, Services
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 flex flex-col justify-between shadow-sm hover:border-brand-500/60 transition-colors h-full">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                  Model Architectures
                </span>
                <span className="w-9 h-9 rounded-xl bg-dark-bg/90 border border-dark-border flex items-center justify-center text-lg shrink-0">
                  ⚖️
                </span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-white">
                3 Principal Models
              </div>
              <div className="flex items-center gap-1.5 pt-0.5">
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 border border-amber-500/30 text-amber-300">
                  + Naive Benchmark
                </span>
              </div>
            </div>
            <p className="text-xs text-slate-400 pt-2.5 border-t border-dark-border/30 mt-3">
              LIR, ARIMA, LSTM evaluated against neutral baseline
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 flex flex-col justify-between shadow-sm hover:border-brand-500/60 transition-colors h-full">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">
                  Forecast Horizon
                </span>
                <span className="w-9 h-9 rounded-xl bg-dark-bg/90 border border-dark-border flex items-center justify-center text-lg shrink-0">
                  🎯
                </span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-white">
                Next-Session
              </div>
            </div>
            <p className="text-xs text-slate-400 pt-2.5 border-t border-dark-border/30 mt-3">
              Target trading session:{" "}
              <span className="text-slate-200 font-semibold">
                {forecastSessionDate}
              </span>
            </p>
          </div>
        </div>
      </section>

      {/* In-Page Navigation Bar */}
      <AboutInPageNav />

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          1. RESEARCH PURPOSE & RESEARCH QUESTIONS (#overview)
      ================================================================ */}
      <section id="overview" className="space-y-6 scroll-mt-24">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            RESEARCH OBJECTIVE
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Research Purpose & Research Questions
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            PSE Pulse investigates whether Lag-Informed Regression, ARIMA, and
            LSTM can produce useful next-session closing-price forecasts across
            selected Philippine Stock Exchange companies, and whether
            forecasting performance differs across companies and sectors.
          </p>
        </div>

        {/* 3 Research Question Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 flex flex-col justify-between h-full shadow-sm hover:border-brand-500/50 transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-500/15 text-brand-400 border border-brand-500/30">
                  RQ1
                </span>
                <span className="text-lg">⚖️</span>
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Model Comparison
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                How do Lag-Informed Regression, ARIMA, and LSTM compare in
                next-session forecasting accuracy across the selected companies?
              </p>
            </div>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 flex flex-col justify-between h-full shadow-sm hover:border-amber-500/50 transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                  RQ2
                </span>
                <span className="text-lg">🎯</span>
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Benchmark Utility
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Do the principal forecasting models achieve lower historical
                out-of-sample error than a previous-close Naive benchmark?
              </p>
            </div>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 flex flex-col justify-between h-full shadow-sm hover:border-purple-500/50 transition-colors">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30">
                  RQ3
                </span>
                <span className="text-lg">🌐</span>
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Cross-Sector Behavior
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Does the model with the lowest historical evaluation error remain
                consistent across companies and PSE sectors?
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          2. HOW PSE PULSE WORKS (#methodology)
      ================================================================ */}
      <section
        id="methodology"
        className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm scroll-mt-24"
      >
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Methodological Pipeline
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            How PSE Pulse Works
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            An audited multi-stage lifecycle transforming authoritative market
            disclosures into next-session closing projections without daily
            retraining.
          </p>
        </div>

        {/* 7 Connected Process Steps */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-5 sm:p-5.5 space-y-3.5 flex flex-col justify-between hover:border-brand-500/60 transition-colors h-full">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-500/15 text-brand-400 border border-brand-500/30">
                  Step 1
                </span>
                <span className="text-lg">📥</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                Historical / EOD Market Data
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Ingestion of official PSE Daily Quotations Reports at the
                3:15 PM PHT market close, gathering verified daily OHLCV
                disclosures.
              </p>
            </div>
            <div className="text-xs font-semibold text-brand-400 pt-3 border-t border-dark-border/30">
              Raw Market Data
            </div>
          </div>

          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-5 sm:p-5.5 space-y-3.5 flex flex-col justify-between hover:border-cyan-500/60 transition-colors h-full">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                  Step 2
                </span>
                <span className="text-lg">⚙️</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                Validation & Feature Preparation
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Strict physical checks, calendar alignment, causal lag creation,
                and technical indicators designed with zero lookahead bias.
              </p>
            </div>
            <div className="text-xs font-semibold text-cyan-400 pt-3 border-t border-dark-border/30">
              Validated Features
            </div>
          </div>

          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-5 sm:p-5.5 space-y-3.5 flex flex-col justify-between hover:border-purple-500/60 transition-colors h-full">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30">
                  Step 3
                </span>
                <span className="text-lg">🔬</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                LIR / ARIMA / LSTM Methodology
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Rigorous training across three distinct paradigms: LASSO linear
                regularization, ARIMA time-series grid search, and PyTorch LSTM
                networks.
              </p>
            </div>
            <div className="text-xs font-semibold text-purple-400 pt-3 border-t border-dark-border/30">
              Model Paradigms
            </div>
          </div>

          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-5 sm:p-5.5 space-y-3.5 flex flex-col justify-between hover:border-amber-500/60 transition-colors h-full">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                  Step 4
                </span>
                <span className="text-lg">🛡️</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                Chronological OOS Evaluation
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Dynamic 85% development / 15% evaluation holdout split without
                shuffling. All models evaluated on identical holdout sessions.
              </p>
            </div>
            <div className="text-xs font-semibold text-amber-400 pt-3 border-t border-dark-border/30">
              Audited Metrics
            </div>
          </div>

          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-5 sm:p-5.5 space-y-3.5 flex flex-col justify-between hover:border-emerald-500/60 transition-colors h-full">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  Step 5
                </span>
                <span className="text-lg">🔄</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                Full-Data Production Refit
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                After winning configurations are selected, all three principal
                models are refitted on 100% of validated history and persisted.
              </p>
            </div>
            <div className="text-xs font-semibold text-emerald-400 pt-3 border-t border-dark-border/30">
              Persisted Weights
            </div>
          </div>

          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-5 sm:p-5.5 space-y-3.5 flex flex-col justify-between hover:border-blue-500/60 transition-colors h-full">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
                  Step 6
                </span>
                <span className="text-lg">🎯</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                Persisted-Model Daily Inference
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Daily automation loads persisted model weights to compute
                next-session price targets. Models are NOT retrained daily.
              </p>
            </div>
            <div className="text-xs font-semibold text-blue-400 pt-3 border-t border-dark-border/30">
              Target Forecasts
            </div>
          </div>

          <div className="bg-dark-bg/90 border border-dark-border rounded-xl p-5 sm:p-5.5 space-y-3.5 flex flex-col justify-between hover:border-brand-500/60 transition-colors h-full sm:col-span-2 lg:col-span-3">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-500/15 text-brand-400 border border-brand-500/30">
                  Step 7
                </span>
                <span className="text-lg">🌐</span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                Frontend Forecast Presentation & Drift Audit
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Atomic JSON bundles export predictions, prospective ledger
                outcomes, and drift assessments to the website. The UI never runs
                Python code or live inference.
              </p>
            </div>
            <div className="text-xs font-semibold text-brand-400 pt-3 border-t border-dark-border/30">
              Decoupled Static Delivery
            </div>
          </div>
        </div>

        {/* Explicit Training vs Inference Note */}
        <div className="p-5 sm:p-6 rounded-xl bg-dark-bg/80 border border-brand-500/30 text-xs sm:text-sm text-slate-300 space-y-2 leading-relaxed">
          <div className="flex items-center gap-2 font-bold text-white text-sm sm:text-base">
            <span className="text-brand-400">ℹ️</span>
            <span>Quarterly Model Refitting vs. Daily Forward Inference</span>
          </div>
          <p className="text-slate-400 text-xs sm:text-sm leading-relaxed">
            Model hyperparameter tuning and production refitting run on a
            predetermined quarterly schedule (February 28, May 28, August 28, and
            November 28 at 8:00 AM PHT). Daily trading session updates load
            persisted production models to execute forward inference;
            <strong className="text-white">
              {" "}PSE Pulse does not retrain or alter model configurations during
              daily operational runs.
            </strong>
          </p>
        </div>
      </section>

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          3. MODEL PERFORMANCE & COMPARISON (#model-performance)
          (Reusing the existing ModelsDashboard component unchanged)
      ================================================================ */}
      <AboutModelsSection />

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          4. HOW TO INTERPRET THE RESULTS
      ================================================================ */}
      <section className="space-y-6">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Evaluation Semantics
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            How to Interpret the Results
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Essential guidelines for understanding model rankings, statistical
            baselines, and production operation.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 flex flex-col justify-between h-full shadow-sm hover:border-brand-500/50 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg bg-amber-500/15 text-amber-300 flex items-center justify-center font-bold text-base shrink-0">
                  🏆
                </span>
                <h3 className="font-bold text-white text-sm uppercase tracking-wider">
                  Descriptive Winner
                </h3>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                The best principal model is the model with the lowest historical
                evaluation RMSE among Lag-Informed Regression, ARIMA, and LSTM
                during the common out-of-sample holdout period.
              </p>
            </div>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 flex flex-col justify-between h-full shadow-sm hover:border-brand-500/50 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg bg-blue-500/15 text-blue-400 flex items-center justify-center font-bold text-base shrink-0">
                  📊
                </span>
                <h3 className="font-bold text-white text-sm uppercase tracking-wider">
                  Statistical Evidence
                </h3>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Lower historical holdout error does not automatically prove
                statistically significant superiority. Research hypothesis testing
                remains distinct from descriptive leaderboard tables.
              </p>
            </div>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 flex flex-col justify-between h-full shadow-sm hover:border-purple-500/50 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg bg-purple-500/15 text-purple-400 flex items-center justify-center font-bold text-base shrink-0">
                  🏭
                </span>
                <h3 className="font-bold text-white text-sm uppercase tracking-wider">
                  Production Models
                </h3>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                PSE Pulse operates and refits all three principal model families.
                The historical RMSE winner is not automatically promoted as the sole
                production model; all three issue prospective next-session targets.
              </p>
            </div>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 flex flex-col justify-between h-full shadow-sm hover:border-brand-500/50 transition-colors">
            <div className="space-y-2.5">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg bg-emerald-500/15 text-emerald-400 flex items-center justify-center font-bold text-base shrink-0">
                  📡
                </span>
                <h3 className="font-bold text-white text-sm uppercase tracking-wider">
                  Prospective Monitoring
                </h3>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Live prospective forecast outcomes are logged into an append-only
                ledger and monitored separately from the frozen historical
                evaluation, tracking model drift over ongoing market sessions.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          5. RESEARCH SCOPE & BOUNDARIES (#scope)
      ================================================================ */}
      <section id="scope" className="space-y-6 scroll-mt-24">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            RESEARCH BOUNDARIES
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Research Scope & Boundaries
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            PSE Pulse is deliberately scoped to historical numerical market data,
            next-session closing-price forecasting, and comparative model
            evaluation. The platform does not attempt to represent every factor
            that can influence equity prices.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left Column: Included in PSE Pulse */}
          <div className="bg-dark-card border border-emerald-500/30 rounded-2xl p-6 space-y-4 shadow-sm flex flex-col justify-between h-full">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-sm font-bold shrink-0">
                  ✓
                </span>
                <h3 className="font-bold text-white text-base tracking-tight">
                  Included in PSE Pulse
                </h3>
              </div>
              <ul className="space-y-2 text-xs text-slate-300">
                {[
                  "Daily Philippine Stock Exchange OHLCV market data",
                  "Next-session closing-price forecasting",
                  "15 selected PSE-listed companies across five sectors",
                  "Lag-Informed Regression",
                  "ARIMA",
                  "LSTM",
                  "Previous-close Naive evaluation benchmark",
                  "Chronological out-of-sample evaluation",
                  "Post-formal prospective forecast monitoring",
                ].map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-emerald-400 font-bold mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Right Column: Outside the Research Scope */}
          <div className="bg-dark-card border border-dark-border rounded-2xl p-6 space-y-4 shadow-sm flex flex-col justify-between h-full">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="w-7 h-7 rounded-lg bg-slate-800 text-slate-400 border border-dark-border flex items-center justify-center text-xs font-bold shrink-0">
                  ✕
                </span>
                <h3 className="font-bold text-white text-base tracking-tight">
                  Outside the Research Scope
                </h3>
              </div>
              <ul className="space-y-2 text-xs text-slate-400">
                {[
                  "Intraday price forecasting",
                  "Automated trading or order execution",
                  "Buy/sell recommendations",
                  "Portfolio optimization",
                  "Personalized investment advice",
                  "News or social-media sentiment forecasting",
                  "Fundamental valuation models",
                  "Guaranteed price or return predictions",
                ].map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-slate-500 font-bold mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Scope Context Note */}
        <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border text-xs text-slate-300 leading-relaxed">
          <p className="text-slate-400">
            The implemented forecasting models primarily use historical
            numerical market data. Unexpected news, corporate events, policy
            changes, macroeconomic shocks, and other external information may
            therefore affect actual market outcomes without being represented
            directly in the model inputs.
          </p>
        </div>
      </section>

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          6. RESEARCH INTEGRITY & EVALUATION DESIGN
      ================================================================ */}
      <section className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            Methodological Safeguards
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Research Integrity & Evaluation Design
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Seven foundational scientific safeguards eliminating data snooping,
            lookahead bias, and circular retraining.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 hover:border-emerald-500/40 transition-colors h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                  ✓
                </span>
                <span>Chronological Evaluation</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                No random train/test shuffling; time order is strictly preserved
                to prevent future session leakage into past estimates.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 hover:border-emerald-500/40 transition-colors h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                  ✓
                </span>
                <span>Common Evaluation Dates</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                All four forecasting methods are evaluated across the exact same
                aligned target trading days for every company in the universe.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 hover:border-emerald-500/40 transition-colors h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                  ✓
                </span>
                <span>Naive Benchmark</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Previous Close is evaluated alongside principal models to
                empirically verify whether complex algorithms outperform a
                no-change random walk.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 hover:border-emerald-500/40 transition-colors h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                  ✓
                </span>
                <span>Common MASE Scaling</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Model MASE values use the identical development-series scaling
                basis per company, enabling sound, scale-free cross-equity
                comparisons.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 hover:border-emerald-500/40 transition-colors h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                  ✓
                </span>
                <span>Frozen Research Evidence</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Historical formal evaluation runs are permanently frozen and
                preserved separately from subsequent operational monitoring.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 hover:border-emerald-500/40 transition-colors h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                  ✓
                </span>
                <span>Post-Formal Monitoring</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                New daily market outcomes append to prospective ledger records and
                never overwrite or retroactively rewrite frozen historical
                evaluation metrics.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 hover:border-emerald-500/40 transition-colors h-full flex flex-col justify-between sm:col-span-2 lg:col-span-3">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                  ✓
                </span>
                <span>Tamper-Detectable Evidence Packages</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Research evidence packages incorporate strict integrity verification
                manifests ensuring that data provenance, model configurations, and
                evaluation series remain verifiable and untampered.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          7. SYSTEM ARCHITECTURE & TECHNOLOGY (#architecture)
      ================================================================ */}
      <section id="architecture" className="space-y-6 scroll-mt-24">
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
            SYSTEM IMPLEMENTATION
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            System Architecture & Technology
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            PSE Pulse separates forecasting, research evaluation, persisted
            model artifacts, and web presentation so model development can
            remain independent from the public-facing interface.
          </p>
        </div>

        {/* Architecture Flow Diagram */}
        <div className="bg-dark-card border border-dark-border rounded-2xl p-6 shadow-sm space-y-4">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
            End-to-End System Pipeline
          </span>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2.5">
            <div className="p-3.5 rounded-xl bg-dark-bg/90 border border-dark-border text-center flex-1">
              <span className="block text-base mb-1">🏛️</span>
              <span className="text-xs font-bold text-white block">
                PSE End-of-Day Data
              </span>
              <span className="text-[10px] text-slate-400">
                Official EOD Disclosures
              </span>
            </div>

            <div className="text-slate-500 font-bold text-sm text-center md:text-base rotate-90 md:rotate-0 self-center">
              →
            </div>

            <div className="p-3.5 rounded-xl bg-dark-bg/90 border border-dark-border text-center flex-1">
              <span className="block text-base mb-1">🐍</span>
              <span className="text-xs font-bold text-white block">
                Python Backend
              </span>
              <span className="text-[10px] text-slate-400">
                Forecasting & Evaluation
              </span>
            </div>

            <div className="text-slate-500 font-bold text-sm text-center md:text-base rotate-90 md:rotate-0 self-center">
              →
            </div>

            <div className="p-3.5 rounded-xl bg-dark-bg/90 border border-dark-border text-center flex-1">
              <span className="block text-base mb-1">📦</span>
              <span className="text-xs font-bold text-white block">
                Validated Artifacts
              </span>
              <span className="text-[10px] text-slate-400">
                Persisted Weights & Audits
              </span>
            </div>

            <div className="text-slate-500 font-bold text-sm text-center md:text-base rotate-90 md:rotate-0 self-center">
              →
            </div>

            <div className="p-3.5 rounded-xl bg-dark-bg/90 border border-dark-border text-center flex-1">
              <span className="block text-base mb-1">📄</span>
              <span className="text-xs font-bold text-white block">
                Frontend JSON
              </span>
              <span className="text-[10px] text-slate-400">
                Decoupled Static Data
              </span>
            </div>

            <div className="text-slate-500 font-bold text-sm text-center md:text-base rotate-90 md:rotate-0 self-center">
              →
            </div>

            <div className="p-3.5 rounded-xl bg-dark-bg/90 border border-dark-border text-center flex-1">
              <span className="block text-base mb-1">🌐</span>
              <span className="text-xs font-bold text-white block">
                Next.js Website
              </span>
              <span className="text-[10px] text-slate-400">
                PSE Pulse Presentation
              </span>
            </div>
          </div>
        </div>

        {/* 3 Compact Technology Groups */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 space-y-3 flex flex-col justify-between h-full shadow-sm">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">📊</span>
                <h3 className="font-bold text-white text-base tracking-tight">
                  Data & Modeling
                </h3>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[
                  "Python",
                  "Pandas",
                  "NumPy",
                  "scikit-learn",
                  "statsmodels",
                  "PyTorch",
                ].map((tech) => (
                  <span
                    key={tech}
                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-bg border border-dark-border text-slate-200"
                  >
                    {tech}
                  </span>
                ))}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 pt-3 border-t border-dark-border/40">
              Econometric, machine learning, and deep neural network libraries.
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 space-y-3 flex flex-col justify-between h-full shadow-sm">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">⚙️</span>
                <h3 className="font-bold text-white text-base tracking-tight">
                  Research & Automation
                </h3>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[
                  "Chronological evaluation",
                  "Persisted model artifacts",
                  "Integrity validation",
                  "GitHub Actions",
                  "Scheduled pipeline automation",
                ].map((tech) => (
                  <span
                    key={tech}
                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-bg border border-dark-border text-slate-200"
                  >
                    {tech}
                  </span>
                ))}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 pt-3 border-t border-dark-border/40">
              Automated reproducible pipeline and model verification workflows.
            </p>
          </div>

          <div className="bg-dark-card border border-dark-border rounded-2xl p-5 sm:p-6 space-y-3 flex flex-col justify-between h-full shadow-sm">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">🖥️</span>
                <h3 className="font-bold text-white text-base tracking-tight">
                  Web Presentation
                </h3>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[
                  "Next.js",
                  "TypeScript",
                  "Tailwind CSS",
                  "Vercel",
                  "Frontend JSON data layer",
                ].map((tech) => (
                  <span
                    key={tech}
                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-bg border border-dark-border text-slate-200"
                  >
                    {tech}
                  </span>
                ))}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 pt-3 border-t border-dark-border/40">
              Decoupled static application optimized for fast client delivery.
            </p>
          </div>
        </div>

        {/* Explicit Frontend Decoupling Callout */}
        <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-brand-500/30 text-xs text-slate-300 leading-relaxed flex items-start gap-2.5">
          <span className="text-brand-400 text-sm mt-0.5">ℹ️</span>
          <p className="text-slate-400">
            <strong className="text-white">Static Architecture Decoupling: </strong>
            The public Next.js frontend reads validated exported forecast data
            and does not run Python model training or inference on Vercel.
          </p>
        </div>
      </section>

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          8. DATA SOURCE & REFRESH RHYTHM (#data)
      ================================================================ */}
      <section
        id="data"
        className="bg-dark-card border border-dark-border rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm scroll-mt-24"
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-400">
              Data Governance & Automation
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Data Source & Refresh Rhythm
            </h2>
            <p className="text-sm text-slate-400 max-w-xl leading-relaxed">
              Forecasts are generated exclusively from authoritative public
              disclosures published by the Philippine Stock Exchange.
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

        {/* 4 Distinctions Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-5 space-y-2 flex flex-col justify-between h-full">
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                1. Historical Research Data
              </span>
              <h4 className="text-base font-bold text-white tracking-tight">
                Development Baseline
              </h4>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pt-2 border-t border-dark-border/30">
              Multi-year validated historical OHLCV data used for model tuning,
              cross-validation, and out-of-sample evaluation.
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-5 space-y-2 flex flex-col justify-between h-full">
            <div className="space-y-2">
              <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider block">
                2. Operational EOD Data
              </span>
              <h4 className="text-base font-bold text-white tracking-tight">
                Official Quotations
              </h4>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pt-2 border-t border-dark-border/30">
              Daily market quotations downloaded after the 3:15 PM PHT market
              close, extending prospective tracking records.
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-5 space-y-2 flex flex-col justify-between h-full">
            <div className="space-y-2">
              <span className="text-xs font-bold text-purple-400 uppercase tracking-wider block">
                3. Scheduled Model Training
              </span>
              <h4 className="text-base font-bold text-white tracking-tight">
                Quarterly Refits
              </h4>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pt-2 border-t border-dark-border/30">
              Model retraining occurs quarterly (Feb 28, May 28, Aug 28, Nov 28)
              and is completely decoupled from daily operations.
            </p>
          </div>

          <div className="bg-dark-bg/80 border border-dark-border rounded-xl p-5 space-y-2 flex flex-col justify-between h-full">
            <div className="space-y-2">
              <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider block">
                4. Daily Forecasting
              </span>
              <h4 className="text-base font-bold text-white tracking-tight">
                Persisted Inference
              </h4>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed pt-2 border-t border-dark-border/30">
              Persisted production model weights perform forward inference for
              the next eligible session without retraining.
            </p>
          </div>
        </div>

        {/* Dynamic Status Display */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
          <div className="p-4 rounded-xl bg-dark-bg/60 border border-dark-border space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Latest Pipeline Execution:
            </span>
            <p className="text-sm font-bold text-white">{lastPipelineRun}</p>
          </div>
          <div className="p-4 rounded-xl bg-dark-bg/60 border border-dark-border space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Active Forecast Session Target:
            </span>
            <p className="text-sm font-bold text-white">{forecastSessionDate}</p>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-dark-bg/60 border border-dark-border text-xs text-slate-300 space-y-1.5 leading-relaxed">
          <strong className="text-white block text-sm">
            Trading Hours & Pipeline Rhythm:
          </strong>
          Philippine equity trading takes place Monday through Friday, 9:30 AM
          to 3:00 PM PHT. The PSE publishes official Daily Quotations Reports at
          approximately 3:15 PM PHT, triggering automated ingestion and persisted
          model inference runs ahead of the next eligible trading day.
        </div>
      </section>

      {/* Subtle section divider */}
      <div className="border-t border-dark-border/25" />

      {/* ================================================================
          9. IMPORTANT LIMITATIONS & EDUCATIONAL DISCLAIMER (#limitations)
      ================================================================ */}
      <section
        id="limitations"
        className="bg-gradient-to-br from-dark-card to-amber-950/15 border border-amber-500/30 rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm relative overflow-hidden scroll-mt-24"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg bg-amber-500/20 text-amber-300 flex items-center justify-center font-bold text-lg shrink-0">
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

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs text-slate-300 leading-relaxed">
          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <h3 className="font-bold text-white text-sm">
                Educational Decision Support Only
              </h3>
              <p className="text-slate-400 leading-relaxed">
                PSE Pulse is strictly an academic research and educational
                platform. Forecasts, model rankings, and backtest metrics are
                statistical estimates for research exploration and{" "}
                <strong className="text-white">
                  never constitute financial advice, investment recommendations,
                  or automated trading signals
                </strong>
                .
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <h3 className="font-bold text-white text-sm">
                Historical Pattern Limitation
              </h3>
              <p className="text-slate-400 leading-relaxed">
                Past forecasting accuracy during historical evaluations does not
                guarantee future performance. Equity markets are subject to
                structural regime shifts, liquidity changes, and non-stationary
                economic environments.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <h3 className="font-bold text-white text-sm">Unexpected Events</h3>
              <p className="text-slate-400 leading-relaxed">
                Models evaluate historical price and volume relationships. They
                cannot anticipate breaking news, corporate earnings surprises,
                macroeconomic policy changes, regulatory decisions, geopolitical
                crises, or sudden intraday liquidity events.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 h-full flex flex-col justify-between">
            <div className="space-y-1.5">
              <h3 className="font-bold text-white text-sm">Model Uncertainty</h3>
              <p className="text-slate-400 leading-relaxed">
                Different forecasting architectures can produce conflicting
                projections for the same trading session. All statistical forecasts
                contain error, and spread between models should not be interpreted
                as a confidence interval.
              </p>
            </div>
          </div>

          <div className="p-4.5 sm:p-5 rounded-xl bg-dark-bg/80 border border-dark-border space-y-2 h-full flex flex-col justify-between sm:col-span-2 lg:col-span-2">
            <div className="space-y-1.5">
              <h3 className="font-bold text-white text-sm">
                Independent Due Diligence
              </h3>
              <p className="text-slate-400 leading-relaxed">
                Users must perform thorough independent analysis and consult
                registered SEC-licensed financial advisors before executing
                investment decisions. Equity trading involves significant risk,
                including the possible loss of principal.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
