"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  PSE_MARKET_SCHEDULE,
  PSE_MARKET_SCHEDULE_SOURCE,
  BROKER_DIRECTORY,
  EDUCATIONAL_VIDEOS,
  GLOSSARY_TERMS,
} from "@/lib/learnData";

export default function LearnStocksPage() {
  // Accordion open states (default: first open, or based on hash)
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    "trading-101": true,
  });

  // Glossary category filter state
  const [termCategory, setTermCategory] = useState<"all" | "market" | "forecastph">("all");

  // Track expanded terms in glossary
  const [expandedTerms, setExpandedTerms] = useState<Record<string, boolean>>({});

  // Auto-expand accordion if URL contains a hash
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace("#", "");
      if (!hash) return;

      const aliasMap: Record<string, string> = {
        "forecast-prediction": "how-to-read",
        "how-to-read": "how-to-read",
        "trading-101": "trading-101",
        "pse-basics": "pse-basics",
        "trading-terms": "trading-terms",
        "forecast-accuracy": "forecast-accuracy",
        "forecast-charts": "forecast-charts",
        "watch-learn": "watch-learn",
        "pse-brokers": "pse-brokers",
        "research-methodology": "research-methodology",
      };

      const targetId = aliasMap[hash] || hash;
      setOpenSections({ [targetId]: true });

      // Smooth scroll to the target section
      setTimeout(() => {
        const el = document.getElementById(targetId);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 100);
    };

    handleHash();
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  const toggleSection = (id: string) => {
    setOpenSections((prev) => (prev[id] ? {} : { [id]: true }));
  };

  const navigateToSection = (id: string) => {
    setOpenSections({ [id]: true });
    setTimeout(() => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }, 50);
  };

  const toggleTerm = (term: string) => {
    setExpandedTerms((prev) => ({
      ...prev,
      [term]: !prev[term],
    }));
  };

  const filteredTerms = GLOSSARY_TERMS.filter((t) => {
    if (termCategory === "all") return true;
    return t.category === termCategory;
  });

  return (
    <div className="space-y-10 pb-16">
      {/* "Start Here" 4-Step Learning Path */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-400 uppercase tracking-wider mb-1">
              <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" />
              Recommended Curriculum
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Start Here: 4-Step Learning Path
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 max-w-sm">
            Follow this sequential path from foundational market mechanics to evaluating live forecasts.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Step 1: Learn Before You Trade */}
          <a
            href="#trading-101"
            onClick={(e) => {
              e.preventDefault();
              navigateToSection("trading-101");
            }}
            className="group bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:shadow-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 motion-reduce:transform-none flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                  Step 1
                </span>
                <span className="text-xs text-slate-400 font-medium">Fundamentals</span>
              </div>
              <h3 className="text-base font-bold text-white group-hover:text-brand-300 transition-colors">
                Learn Before You Trade
              </h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Understand shares, dividends, trading sessions, capital gains, and risk diversification.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-brand-400 group-hover:text-brand-300">
              <span>Stock Trading 101</span>
              <span className="transition-transform group-hover:translate-x-0.5">↓</span>
            </div>
          </a>

          {/* Step 2: Understand a Forecast */}
          <a
            href="#how-to-read"
            onClick={(e) => {
              e.preventDefault();
              navigateToSection("how-to-read");
            }}
            className="group bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:shadow-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 motion-reduce:transform-none flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-brand-500/15 border border-brand-500/30 text-brand-400">
                  Step 2
                </span>
                <span className="text-xs text-slate-400 font-medium">Predictions</span>
              </div>
              <h3 className="text-base font-bold text-white group-hover:text-brand-300 transition-colors">
                Understand a Forecast
              </h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Learn how next-day price targets are generated, what expected movement means, and why prices diverge.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-brand-400 group-hover:text-brand-300">
              <span>How to Read Forecasts</span>
              <span className="transition-transform group-hover:translate-x-0.5">↓</span>
            </div>
          </a>

          {/* Step 3: Check Historical Accuracy */}
          <a
            href="#forecast-accuracy"
            onClick={(e) => {
              e.preventDefault();
              navigateToSection("forecast-accuracy");
            }}
            className="group bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:shadow-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 motion-reduce:transform-none flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/15 border border-amber-500/30 text-amber-400">
                  Step 3
                </span>
                <span className="text-xs text-slate-400 font-medium">Evaluation</span>
              </div>
              <h3 className="text-base font-bold text-white group-hover:text-brand-300 transition-colors">
                Check Historical Accuracy
              </h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Evaluate out-of-sample backtests, RMSE, MAE, MASE, and the separately evaluated Naive benchmark.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-brand-400 group-hover:text-brand-300">
              <span>Model Verification</span>
              <span className="transition-transform group-hover:translate-x-0.5">↓</span>
            </div>
          </a>

          {/* Step 4: Explore Companies */}
          <Link
            href="/companies"
            className="group bg-dark-card border border-slate-700/60 dark:border-dark-border rounded-2xl p-5 shadow-sm hover:border-brand-500/80 focus-visible:border-brand-500 hover:-translate-y-1 focus-visible:-translate-y-1 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:shadow-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400 motion-reduce:transform-none flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-500/15 border border-purple-500/30 text-purple-400">
                  Step 4
                </span>
                <span className="text-xs text-slate-400 font-medium">Practice</span>
              </div>
              <h3 className="text-base font-bold text-white group-hover:text-brand-300 transition-colors">
                Explore Companies
              </h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Inspect 15 PSE companies across 5 sectors, toggle Beginner/Advanced views, and add to Watchlist.
              </p>
            </div>
            <div className="pt-4 mt-3 border-t border-dark-border/60 flex items-center justify-between text-xs font-semibold text-brand-400 group-hover:text-brand-300">
              <span>Browse 15 Companies</span>
              <span className="transition-transform group-hover:translate-x-0.5">→</span>
            </div>
          </Link>
        </div>
      </section>

      {/* Main Accordion List */}
      <div className="space-y-4 pt-2">
        {/* ================================================================
            STOCK TRADING 101
        ================================================================ */}
        <section id="trading-101" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("trading-101")}
            aria-expanded={Boolean(openSections["trading-101"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <img
                src="/images/learn/learn-before-you-trade.jpg"
                alt="Stock Trading 101 thumbnail"
                className="w-12 h-12 rounded-xl object-cover border border-dark-border shadow-xs shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider">Fundamentals</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  Stock Trading 101
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Foundational concepts of stocks, shares, dividends, and risk
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["trading-101"] ? "−" : "+"}
            </span>
          </button>

          {openSections["trading-101"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-6 text-sm text-slate-300 leading-relaxed">
              {/* Alternating Feature Block: Image Left, Text Right */}
              <div className="flex flex-col md:flex-row items-center gap-5 p-4 sm:p-5 rounded-2xl bg-dark-bg/80 border border-dark-border">
                <div className="w-full md:w-5/12 aspect-video overflow-hidden rounded-xl bg-slate-900 shrink-0 border border-dark-border/80">
                  <img
                    src="/images/learn/learn-before-you-trade.jpg"
                    alt="Investor analyzing market fundamentals and stock charts at a desk"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                    Investment Foundations
                  </span>
                  <h3 className="text-lg font-bold text-white">
                    Mastering Fundamentals Before Entering the Market
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Participating in the Philippine stock market connects you with the nation&apos;s real economic drivers—from consumer retail and telecommunications to universal banking. Understanding fractional shares, dividend distributions, and the difference between long-term value accumulation and short-term volatility trading is essential before risking hard-earned capital.
                  </p>
                </div>
              </div>

              {/* 6 Concept Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-1.5">
                  <h3 className="font-bold text-white text-base">What is a Stock?</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    A stock (or equity) represents fractional ownership in a corporation. When you buy a stock, you become a <strong className="text-white">shareholder</strong> and own a tiny portion of the company&apos;s overall assets and future earnings.
                  </p>
                </div>

                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-1.5">
                  <h3 className="font-bold text-white text-base">Shares & Public Companies</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    A company&apos;s total ownership is divided into individual units called <strong className="text-white">shares</strong>. Public companies offer their shares on the Philippine Stock Exchange (PSE) so any verified retail or institutional investor can buy and sell them.
                  </p>
                </div>

                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-1.5">
                  <h3 className="font-bold text-white text-base">Capital Gains vs. Losses</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    A <strong className="text-emerald-400">capital gain</strong> occurs when you sell a stock for a higher price than what you paid for it. A <strong className="text-red-400">capital loss</strong> occurs if the market price drops and you sell below your purchase cost.
                  </p>
                </div>

                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-1.5">
                  <h3 className="font-bold text-white text-base">Dividends</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Some profitable companies return a portion of their earnings directly to shareholders as <strong className="text-amber-400">cash dividends</strong> or additional <strong className="text-amber-400">stock dividends</strong>, providing passive income in addition to share price growth.
                  </p>
                </div>

                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-1.5">
                  <h3 className="font-bold text-white text-base">Investing vs. Trading</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    <strong className="text-white">Investing</strong> focuses on long-term wealth accumulation by holding fundamentally sound businesses over years. <strong className="text-white">Trading</strong> focuses on short-term price movements over days, weeks, or months to capture price volatility.
                  </p>
                </div>

                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-1.5">
                  <h3 className="font-bold text-white text-base">Risk & Diversification</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Stock prices fluctuate continuously based on supply, demand, and news. Spreading capital across diverse industries (e.g. banking, utilities, retail, real estate) helps prevent a downturn in one company from erasing your total portfolio value.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            PHILIPPINE STOCK EXCHANGE BASICS
        ================================================================ */}
        <section id="pse-basics" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("pse-basics")}
            aria-expanded={Boolean(openSections["pse-basics"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <img
                src="/images/learn/pse-trading.jpg"
                alt="Philippine Stock Exchange thumbnail"
                className="w-12 h-12 rounded-xl object-cover border border-dark-border shadow-xs shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-blue-400 uppercase tracking-wider">Exchange Basics</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  Philippine Stock Exchange Basics
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Authoritative PSE trading hours, sessions, holidays, and mechanics
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["pse-basics"] ? "−" : "+"}
            </span>
          </button>

          {openSections["pse-basics"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-6 text-sm text-slate-300 leading-relaxed">
              {/* Alternating Feature Block: Text Left, Image Right */}
              <div className="flex flex-col md:flex-row-reverse items-center gap-5 p-4 sm:p-5 rounded-2xl bg-dark-bg/80 border border-dark-border">
                <div className="w-full md:w-5/12 aspect-video overflow-hidden rounded-xl bg-slate-900 shrink-0 border border-dark-border/80">
                  <img
                    src="/images/learn/pse-trading.jpg"
                    alt="Philippine Stock Exchange (PSE) headquarters building facade"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400">
                    National Capital Market
                  </span>
                  <h3 className="text-lg font-bold text-white">
                    The Philippine Stock Exchange (PSE)
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    The PSE serves as the sole national stock exchange of the Philippines. Operating with automated electronic matching systems connecting SEC-licensed brokers, trading takes place strictly during designated Monday through Friday sessions, excluding declared Philippine national holidays.
                  </p>
                </div>
              </div>

              {/* Official Trading Schedule */}
              <div className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Official PSE Trading Schedule (Monday – Friday, Non-Holidays)
                  </h3>
                  <a
                    href={PSE_MARKET_SCHEDULE_SOURCE.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 hover:underline"
                  >
                    <span>Source: PSE Market Operations</span>
                    <span className="text-[10px]">↗</span>
                  </a>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {PSE_MARKET_SCHEDULE.map((item) => (
                    <div key={item.phase} className="bg-dark-bg/80 border border-dark-border rounded-xl p-3.5 space-y-1">
                      <span className="text-[11px] font-bold text-brand-400 uppercase tracking-wide">{item.time}</span>
                      <h4 className="text-sm font-semibold text-white">{item.phase}</h4>
                      <p className="text-xs text-slate-400 leading-normal">{item.description}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Holiday & Trading Awareness */}
              <div className="p-4 bg-brand-950/30 border border-brand-500/30 rounded-xl space-y-2">
                <h4 className="text-xs font-bold text-brand-300 uppercase tracking-wide flex items-center gap-1.5">
                  <span>📅</span> Philippine Holidays & Automated Calendar Guard
                </h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  The PSE is closed on all regular and special non-working Philippine public holidays (e.g., National Heroes Day, Holy Week, Bonifacio Day). ForecastPH includes an automated calendar guard that skips holiday ingestion and generates forecasts only for valid upcoming trading sessions.
                </p>
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            ESSENTIAL TRADING TERMS
        ================================================================ */}
        <section id="trading-terms" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("trading-terms")}
            aria-expanded={Boolean(openSections["trading-terms"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center shrink-0 text-xl font-bold">
                📖
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-purple-400 uppercase tracking-wider">Glossary</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  Essential Trading Terms
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Quick reference glossary for market concepts and ForecastPH metrics
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["trading-terms"] ? "−" : "+"}
            </span>
          </button>

          {openSections["trading-terms"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-4 text-sm text-slate-300 leading-relaxed">
              {/* Category Filter */}
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setTermCategory("all")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-400 ${
                    termCategory === "all"
                      ? "bg-brand-600 text-white shadow-xs"
                      : "bg-dark-bg border border-dark-border text-slate-400 hover:text-white"
                  }`}
                >
                  All Terms ({GLOSSARY_TERMS.length})
                </button>
                <button
                  type="button"
                  onClick={() => setTermCategory("market")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-400 ${
                    termCategory === "market"
                      ? "bg-brand-600 text-white shadow-xs"
                      : "bg-dark-bg border border-dark-border text-slate-400 hover:text-white"
                  }`}
                >
                  Market Terms (12)
                </button>
                <button
                  type="button"
                  onClick={() => setTermCategory("forecastph")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-400 ${
                    termCategory === "forecastph"
                      ? "bg-brand-600 text-white shadow-xs"
                      : "bg-dark-bg border border-dark-border text-slate-400 hover:text-white"
                  }`}
                >
                  ForecastPH Terminology (8)
                </button>
              </div>

              {/* Grid of Compact Term Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-2">
                {filteredTerms.map((t) => (
                  <div key={t.term} className="bg-dark-bg/80 border border-dark-border hover:border-brand-500/40 rounded-xl transition-colors">
                    <button
                      type="button"
                      onClick={() => toggleTerm(t.term)}
                      aria-expanded={Boolean(expandedTerms[t.term])}
                      className="w-full p-4 text-left space-y-2 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="font-bold text-white text-sm">{t.term}</h4>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-dark-card border border-dark-border text-brand-400 font-mono shrink-0">
                          {t.category === "forecastph" ? "ForecastPH" : "Market"}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 leading-snug">{t.shortDef}</p>
                      {expandedTerms[t.term] && (
                        <p className="text-xs text-slate-400 pt-2 border-t border-dark-border/60 leading-relaxed">
                          {t.detailedDef}
                        </p>
                      )}
                      <span className="inline-block text-[11px] text-brand-400 font-medium">
                        {expandedTerms[t.term] ? "Show less ↑" : "Learn more ↓"}
                      </span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            HOW TO READ A FORECASTPH PREDICTION
        ================================================================ */}
        <section id="how-to-read" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("how-to-read")}
            aria-expanded={Boolean(openSections["how-to-read"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <img
                src="/images/learn/understand-forecast.jpg"
                alt="Understanding Forecasts thumbnail"
                className="w-12 h-12 rounded-xl object-cover border border-dark-border shadow-xs shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider">Predictions</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  How to Read a ForecastPH Prediction
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Practical walkthrough of predicted values, models, and real-world factors
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["how-to-read"] ? "−" : "+"}
            </span>
          </button>

          {openSections["how-to-read"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-6 text-sm text-slate-300 leading-relaxed">
              {/* Alternating Feature Block: Image Left, Text Right */}
              <div className="flex flex-col md:flex-row items-center gap-5 p-4 sm:p-5 rounded-2xl bg-dark-bg/80 border border-dark-border">
                <div className="w-full md:w-5/12 aspect-video overflow-hidden rounded-xl bg-slate-900 shrink-0 border border-dark-border/80">
                  <img
                    src="/images/learn/understand-forecast.jpg"
                    alt="Professional investor analyzing Philippine stock market line chart"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-cyan-400">
                    Predictive Analytics
                  </span>
                  <h3 className="text-lg font-bold text-white">
                    Contextualizing Next-Day Closing Targets
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    ForecastPH ingests official quotation reports published at the 3:15 PM PHT market close and generates algorithmic price forecasts for the next trading session. Forecasts reflect historical numerical patterns—not subjective speculation or guaranteed trading profits.
                  </p>
                </div>
              </div>

              {/* Concrete Example Card */}
              <div className="bg-dark-bg/90 border border-brand-500/40 rounded-2xl p-5 sm:p-6 shadow-[0_0_20px_rgba(59,130,246,0.1)] space-y-4">
                <div className="flex items-center justify-between border-b border-dark-border/80 pb-3">
                  <span className="text-xs font-semibold text-brand-400 uppercase tracking-wide">Sample Prediction Walkthrough</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-brand-500/20 text-brand-300 border border-brand-500/30">Next Trading Session</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center sm:text-left">
                  <div className="p-3 bg-dark-card border border-dark-border rounded-xl">
                    <p className="text-xs text-slate-400">Current Close</p>
                    <p className="text-xl font-bold text-white font-mono mt-0.5">₱100.00</p>
                  </div>
                  <div className="p-3 bg-dark-card border border-dark-border rounded-xl">
                    <p className="text-xs text-slate-400">Forecasted Close</p>
                    <p className="text-xl font-bold text-brand-400 font-mono mt-0.5">₱102.50</p>
                  </div>
                  <div className="p-3 bg-dark-card border border-dark-border rounded-xl">
                    <p className="text-xs text-slate-400">Expected Movement</p>
                    <p className="text-xl font-bold text-emerald-400 font-mono mt-0.5">▲ +2.50%</p>
                    <p className="text-[11px] text-emerald-300">+₱2.50</p>
                  </div>
                  <div className="p-3 bg-dark-card border border-dark-border rounded-xl">
                    <p className="text-xs text-slate-400">Best Principal Model</p>
                    <p className="text-base font-bold text-white mt-0.5">LSTM</p>
                    <p className="text-[11px] text-brand-400">Best evaluation RMSE</p>
                  </div>
                </div>

                <div className="p-4 bg-dark-card border border-dark-border rounded-xl space-y-2">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">What this means:</h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    &quot;The model estimates that the next trading day&apos;s closing price could be approximately <strong className="text-white">₱102.50</strong>.&quot;
                  </p>
                  <p className="text-xs text-amber-300 font-medium">
                    ⚠️ This does <strong className="underline">not</strong> mean the stock is guaranteed to reach ₱102.50.
                  </p>
                </div>
              </div>

              {/* Factors influencing prices */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Why actual prices diverge from forecasts:</h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Machine learning models evaluate historical numerical price and volume patterns. However, live markets react to unexpected real-time events that no purely historical model can anticipate:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="p-3 bg-dark-bg border border-dark-border rounded-xl text-xs space-y-1">
                    <strong className="text-white">Company Disclosures:</strong> Earnings surprises, dividend declarations, executive changes, or mergers.
                  </div>
                  <div className="p-3 bg-dark-bg border border-dark-border rounded-xl text-xs space-y-1">
                    <strong className="text-white">Macroeconomic Data:</strong> BSP interest rate hikes, inflation reports, or currency fluctuations.
                  </div>
                  <div className="p-3 bg-dark-bg border border-dark-border rounded-xl text-xs space-y-1">
                    <strong className="text-white">Market Sentiment:</strong> Global equity market trends, geopolitical events, or sudden shifts in foreign institutional flow.
                  </div>
                  <div className="p-3 bg-dark-bg border border-dark-border rounded-xl text-xs space-y-1">
                    <strong className="text-white">Sector Dynamics:</strong> Changes in commodity prices (oil, metals), real estate regulations, or power utility tariff decisions.
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            UNDERSTANDING HISTORICAL ACCURACY
        ================================================================ */}
        <section id="forecast-accuracy" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("forecast-accuracy")}
            aria-expanded={Boolean(openSections["forecast-accuracy"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <img
                src="/images/learn/check-historical-accuracy.jpg"
                alt="Forecast Accuracy thumbnail"
                className="w-12 h-12 rounded-xl object-cover border border-dark-border shadow-xs shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider">Model Evaluation</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  Understanding Historical Accuracy
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Out-of-sample backtests, MASE naive benchmark, RMSE, and error metrics
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["forecast-accuracy"] ? "−" : "+"}
            </span>
          </button>

          {openSections["forecast-accuracy"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-6 text-sm text-slate-300 leading-relaxed">
              {/* Alternating Feature Block: Text Left, Image Right */}
              <div className="flex flex-col md:flex-row-reverse items-center gap-5 p-4 sm:p-5 rounded-2xl bg-dark-bg/80 border border-dark-border">
                <div className="w-full md:w-5/12 aspect-video overflow-hidden rounded-xl bg-slate-900 shrink-0 border border-dark-border/80">
                  <img
                    src="/images/learn/check-historical-accuracy.jpg"
                    alt="Quantitative market data analytics and empirical backtest performance evaluation"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                    Model Verification
                  </span>
                  <h3 className="text-lg font-bold text-white">
                    Rigorous Out-of-Sample Empirical Evaluation
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    ForecastPH uses chronological development, validation, and evaluation periods with no lookahead. The Naive benchmark predicts that the next Close equals the current Close. MASE below 1 means evaluation MAE is below the one-step scale calculated from development Close changes; it does not by itself prove that a model beat Naive on the held-out dates.
                  </p>
                </div>
              </div>

              {/* 4 Core Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="bg-dark-bg/80 border border-dark-border p-4 rounded-xl space-y-1">
                  <span className="text-[11px] font-bold text-brand-400 uppercase tracking-wide">Primary Metric</span>
                  <h4 className="font-bold text-white text-sm">RMSE (₱)</h4>
                  <p className="text-xs text-slate-400">Root Mean Squared Error. Heavily penalizes large prediction misses in Philippine Pesos.</p>
                </div>
                <div className="bg-dark-bg/80 border border-dark-border p-4 rounded-xl space-y-1">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">Linear Error</span>
                  <h4 className="font-bold text-white text-sm">MAE (₱)</h4>
                  <p className="text-xs text-slate-400">Mean Absolute Error. Average magnitude of forecast errors in Philippine Pesos.</p>
                </div>
                <div className="bg-dark-bg/80 border border-dark-border p-4 rounded-xl space-y-1">
                  <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wide">Key Benchmark</span>
                  <h4 className="font-bold text-white text-sm">MASE</h4>
                  <p className="text-xs text-slate-400">Mean Absolute Scaled Error. Values below 1.0 are below the development-series one-step error scale; compare held-out model metrics directly to determine whether a principal model beat Naive.</p>
                </div>
                <div className="bg-dark-bg/80 border border-dark-border p-4 rounded-xl space-y-1">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">Goodness-of-Fit</span>
                  <h4 className="font-bold text-white text-sm">Holdout R² — Supplementary Metric</h4>
                  <p className="text-xs text-slate-400">Compares squared holdout errors with a reference based on the holdout-period mean. It can be negative, is not percentage accuracy, and never selects or promotes a model.</p>
                </div>
              </div>

              {/* The 3 Models Compared */}
              <div className="p-4.5 bg-dark-bg/80 border border-dark-border rounded-xl space-y-3">
                <h4 className="font-bold text-white text-sm">The Three Forecasting Architectures</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="space-y-1">
                    <strong className="text-brand-300">Lag-Informed Regression:</strong>
                    <p className="text-slate-400">Interpretable statistical regression using autoregressive price and volume features with LASSO regularization.</p>
                  </div>
                  <div className="space-y-1">
                    <strong className="text-blue-300">ARIMA:</strong>
                    <p className="text-slate-400">Classical autoregressive integrated moving average capturing cyclical trends and price mean-reversion.</p>
                  </div>
                  <div className="space-y-1">
                    <strong className="text-purple-300">LSTM:</strong>
                    <p className="text-slate-400">Recurrent deep neural network designed to capture non-linear sequence patterns across multi-session horizons.</p>
                  </div>
                </div>
              </div>

              {/* Critical Principles for Responsible Learning */}
              <div className="space-y-3">
                <h4 className="font-bold text-white text-sm">Critical Principles for Responsible Learning</h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="p-3 bg-dark-bg/80 border border-dark-border rounded-xl text-xs space-y-1">
                    <span className="text-amber-400 font-bold">Past Performance Rule</span>
                    <p className="text-slate-400">High historical accuracy on past sessions does not guarantee future forecasts will be equally accurate.</p>
                  </div>
                  <div className="p-3 bg-dark-bg/80 border border-dark-border rounded-xl text-xs space-y-1">
                    <span className="text-amber-400 font-bold">Market Regime Shifts</span>
                    <p className="text-slate-400">Sudden policy changes, macro shocks, or geopolitical events can cause models trained on calm periods to underperform.</p>
                  </div>
                  <div className="p-3 bg-dark-bg/80 border border-dark-border rounded-xl text-xs space-y-1">
                    <span className="text-amber-400 font-bold">Supplementary Signal</span>
                    <p className="text-slate-400">Use forecasts as an educational demonstration of time-series modeling, never as a sole trading trigger.</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            INTERACTIVE FORECAST & HISTORICAL CHARTS
        ================================================================ */}
        <section id="forecast-charts" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("forecast-charts")}
            aria-expanded={Boolean(openSections["forecast-charts"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <img
                src="/images/learn/reading-charts.jpg"
                alt="Reading Charts thumbnail"
                className="w-12 h-12 rounded-xl object-cover border border-dark-border shadow-xs shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-brand-400 uppercase tracking-wider">Interactive Charts</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  Interactive Forecast & Historical Charts
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Guide to OHLCV history, next-day forecast branches, and backtest error charts
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["forecast-charts"] ? "−" : "+"}
            </span>
          </button>

          {openSections["forecast-charts"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-6 text-sm text-slate-300 leading-relaxed">
              {/* Alternating Feature Block: Image Left, Text Right */}
              <div className="flex flex-col md:flex-row items-center gap-5 p-4 sm:p-5 rounded-2xl bg-dark-bg/80 border border-dark-border">
                <div className="w-full md:w-5/12 aspect-video overflow-hidden rounded-xl bg-slate-900 shrink-0 border border-dark-border/80">
                  <img
                    src="/images/learn/reading-charts.jpg"
                    alt="Mobile stock market chart interface showing price movements and indicators"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-brand-400">
                    Visual Data Analysis
                  </span>
                  <h3 className="text-lg font-bold text-white">
                    Navigating ForecastPH Interactive Chart Suites
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Visual charts communicate price action, volume velocity, and model divergence far more effectively than isolated tables. On every company detail page, ForecastPH presents synchronized time-series visualizers equipped with period filters and zoom controls.
                  </p>
                </div>
              </div>

              {/* 4 Chart Explanations */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4.5 bg-dark-bg/80 border border-dark-border rounded-xl space-y-2">
                  <h4 className="font-bold text-white text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-brand-400" />
                    Historical OHLCV Chart
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Displays continuous historical price movements alongside trading volume. Includes PSE EDGE-style date-range quick filters (1M, 3M, 6M, 1Y) and interactive zoom and pan controls.
                  </p>
                </div>

                <div className="p-4.5 bg-dark-bg/80 border border-dark-border rounded-xl space-y-2">
                  <h4 className="font-bold text-white text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-400" />
                    Next-Day Prediction Chart
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Plots the latest verified session close and projects broken dashed lines representing next-day targets from Lag Regression, ARIMA, and LSTM.
                  </p>
                </div>

                <div className="p-4.5 bg-dark-bg/80 border border-dark-border rounded-xl space-y-2">
                  <h4 className="font-bold text-white text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    Latest 60 Evaluation Sessions
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Overlays actual closing prices against the stored chronological-evaluation forecasts and later prospective operational forecasts shown on company pages.
                  </p>
                </div>

                <div className="p-4.5 bg-dark-bg/80 border border-dark-border rounded-xl space-y-2">
                  <h4 className="font-bold text-white text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-400" />
                    Forecast Error Over Time (Residuals)
                  </h4>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Plots the prediction residual (Predicted Close minus Actual Close in ₱). Oscillations around zero indicate balanced predictions, while consistent positive or negative drifts indicate directional bias.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            WATCH & LEARN: EDUCATIONAL VIDEOS
        ================================================================ */}
        <section id="watch-learn" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("watch-learn")}
            aria-expanded={Boolean(openSections["watch-learn"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center shrink-0 text-xl font-bold">
                🎬
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-red-400 uppercase tracking-wider">Video Guides</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  Watch & Learn: Educational Video Guides
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Curated video tutorials on Philippine investing and forecasting concepts
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["watch-learn"] ? "−" : "+"}
            </span>
          </button>

          {openSections["watch-learn"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-4 text-sm text-slate-300 leading-relaxed">
              <p className="text-xs text-slate-400">
                Curated educational videos from verified finance educators and market analysts covering Philippine equity fundamentals, financial modeling, and risk discipline.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {EDUCATIONAL_VIDEOS.map((v) => (
                  <div key={v.id} className="bg-dark-bg/80 border border-dark-border rounded-xl p-4 space-y-3 flex flex-col justify-between">
                    <div className="space-y-2">
                      <span className="inline-block px-2.5 py-0.5 rounded text-[10px] font-semibold bg-brand-500/15 text-brand-300 border border-brand-500/30">
                        {v.topic}
                      </span>
                      <h3 className="font-bold text-white text-sm leading-snug">{v.title}</h3>

                      {/* Responsive video container */}
                      <div className="relative w-full aspect-video rounded-lg overflow-hidden bg-slate-900 border border-dark-border">
                        <iframe
                          src={`https://www.youtube-nocookie.com/embed/${v.youtubeId}`}
                          title={v.title}
                          loading="lazy"
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          allowFullScreen
                          className="absolute inset-0 w-full h-full"
                        />
                      </div>

                      <p className="text-xs text-slate-400 leading-relaxed">{v.description}</p>
                    </div>

                    <div className="pt-2 border-t border-dark-border/50 flex items-center justify-between text-xs">
                      <span className="text-slate-500 font-medium">{v.channel}</span>
                      <a
                        href={v.directUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-400 hover:text-brand-300 font-medium inline-flex items-center gap-1"
                      >
                        Open on YouTube ↗
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            FINDING AN SEC-LICENSED STOCK BROKER
        ================================================================ */}
        <section id="pse-brokers" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("pse-brokers")}
            aria-expanded={Boolean(openSections["pse-brokers"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <img
                src="/images/learn/finding-a-broker.jpg"
                alt="Finding a Broker thumbnail"
                className="w-12 h-12 rounded-xl object-cover border border-dark-border shadow-xs shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider">Licensed Brokers</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  Finding an SEC-Licensed Stock Broker
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Authoritative directory of registered Philippine brokers and account opening checklist
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["pse-brokers"] ? "−" : "+"}
            </span>
          </button>

          {openSections["pse-brokers"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-6 text-sm text-slate-300 leading-relaxed">
              {/* Alternating Feature Block: Text Left, Image Right */}
              <div className="flex flex-col md:flex-row-reverse items-center gap-5 p-4 sm:p-5 rounded-2xl bg-dark-bg/80 border border-dark-border">
                <div className="w-full md:w-5/12 aspect-video overflow-hidden rounded-xl bg-slate-900 shrink-0 border border-dark-border/80">
                  <img
                    src="/images/learn/finding-a-broker.jpg"
                    alt="Stock market trade execution concept with Buy and Sell indicators"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                    Regulated Market Access
                  </span>
                  <h3 className="text-lg font-bold text-white">
                    Transacting Safely Through Registered Intermediaries
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    ForecastPH is an independent academic research platform. We do not accept funds, offer trading execution, or endorse commercial brokerages. To purchase actual shares of Philippine corporations, retail investors must open an account with a broker registered with the SEC and accredited by the PSE.
                  </p>
                </div>
              </div>

              {/* Broker Directory Grid */}
              <div className="space-y-3">
                <h4 className="font-bold text-white text-sm">
                  SEC-Registered Online Stock Brokerages
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {BROKER_DIRECTORY.map((b) => (
                    <div
                      key={b.id}
                      className="bg-dark-bg/80 border border-dark-border rounded-xl p-4 flex flex-col justify-between space-y-3"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="font-bold text-white text-base leading-tight">{b.name}</h3>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 whitespace-nowrap">
                            PSE directory reference
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 font-medium">{b.parentEntity}</p>
                        <p className="text-[11px] text-slate-400">{b.pseStatus}</p>
                        <p className="text-xs text-slate-300 pt-1 leading-relaxed">{b.description}</p>
                      </div>

                      <div className="pt-3 border-t border-dark-border/60 flex items-center justify-between text-xs">
                        <a
                          href={b.websiteUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-brand-400 hover:text-brand-300 font-semibold"
                        >
                          Official Website ↗
                        </a>
                        <a
                          href={b.pseDirectoryUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-400 hover:text-slate-200"
                        >
                          PSE Directory ↗
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Checklist & Advisory */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4.5 bg-dark-bg/80 border border-dark-border rounded-xl space-y-2 text-xs">
                  <h4 className="font-bold text-white text-sm">Checklist Before Opening an Account</h4>
                  <ul className="list-disc list-inside space-y-1 text-slate-300">
                    <li>Valid Philippine government-issued ID (Passport, UMID, Driver&apos;s License, PhilID).</li>
                    <li>Philippine Tax Identification Number (TIN).</li>
                    <li>Active Philippine bank account for online funding and dividend withdrawals.</li>
                    <li>Proof of billing address dated within the last 3 months.</li>
                  </ul>
                </div>

                <div className="p-4.5 bg-amber-950/20 border border-amber-500/30 rounded-xl space-y-2 text-xs text-amber-200">
                  <h4 className="font-bold text-amber-300 text-sm flex items-center gap-1.5">
                    <span>⚠️</span> Anti-Scam Advisory
                  </h4>
                  <p className="leading-relaxed">
                    Always verify that your broker is listed on the official Securities and Exchange Commission (SEC) and PSE directories. Never send money to personal bank accounts, cryptocurrency wallets, or social media &quot;investment managers&quot; promising guaranteed trading returns.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ================================================================
            ABOUT THE FORECASTPH RESEARCH
        ================================================================ */}
        <section id="research-methodology" className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden shadow-sm scroll-mt-24">
          <button
            type="button"
            onClick={() => toggleSection("research-methodology")}
            aria-expanded={Boolean(openSections["research-methodology"])}
            className="w-full text-left px-5 sm:px-6 py-4.5 sm:py-5 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center shrink-0 text-xl font-bold">
                🔬
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider">Research & Methodology</span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-white leading-snug truncate">
                  About the ForecastPH Research
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  Machine learning architectures, walk-forward evaluation, and research methodology
                </p>
              </div>
            </div>
            <span className="text-sm font-bold text-brand-400 w-8 h-8 rounded-lg bg-dark-bg border border-dark-border flex items-center justify-center shrink-0 transition-transform duration-200">
              {openSections["research-methodology"] ? "−" : "+"}
            </span>
          </button>

          {openSections["research-methodology"] && (
            <div className="px-5 sm:px-6 pb-6 pt-3 border-t border-dark-border/60 space-y-6 text-sm text-slate-300 leading-relaxed">
              <p>
                ForecastPH is an academic capstone research project comparing machine learning and traditional time-series methods on the Philippine Stock Exchange across diverse market sectors.
              </p>

              {/* The 3 Core Models */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">🧮</span>
                    <h3 className="font-bold text-white text-base">Lag Regression</h3>
                  </div>
                  <p className="text-xs font-semibold text-brand-400">&quot;The Pattern Spotter&quot;</p>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    An interpretable machine learning model analyzing historical price and volume lags. Uses Partial Autocorrelation Function (PACF) to identify repeating lag cycles and LASSO regularization to eliminate non-informative features without overfitting.
                  </p>
                </div>

                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">📈</span>
                    <h3 className="font-bold text-white text-base">ARIMA</h3>
                  </div>
                  <p className="text-xs font-semibold text-blue-400">&quot;The Trend Tracker&quot;</p>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    A classical statistical time-series standard (Autoregressive Integrated Moving Average). Uses statistical differencing to achieve stationarity, tracks underlying trends, and models error autocorrelation with strict convergence verification.
                  </p>
                </div>

                <div className="bg-dark-bg/80 border border-dark-border p-4.5 rounded-xl space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">🧠</span>
                    <h3 className="font-bold text-white text-base">LSTM</h3>
                  </div>
                  <p className="text-xs font-semibold text-purple-400">&quot;Deep Sequence Memory&quot;</p>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    A recurrent neural network with specialized input, forget, and output gates. Learns non-linear temporal dependencies across historical multi-day sequences using normalized training data with zero lookahead leakage.
                  </p>
                </div>
              </div>

              {/* Current Methodology Notes */}
              <div className="p-4.5 bg-dark-bg border border-dark-border rounded-xl space-y-2 text-xs text-slate-400">
                <h4 className="font-bold text-slate-200 uppercase tracking-wide">Current Evaluation and Production:</h4>
                <ul className="list-disc list-inside space-y-1 text-slate-300">
                  <li><strong className="text-white">Chronological Evaluation:</strong> LIR, ARIMA, LSTM, and Naive are compared on one common set of held-out target dates without random shuffling.</li>
                  <li><strong className="text-white">Production Refresh:</strong> All three principal models are freshly refitted during quarterly training. Daily updates load persisted models and perform inference without retraining.</li>
                  <li><strong className="text-white">Naive Benchmark:</strong> The benchmark predicts that tomorrow&apos;s price equals today&apos;s price. MASE uses a development-series scale, so held-out RMSE must be compared directly to determine whether the best principal model beat Naive.</li>
                </ul>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Bottom CTA */}
      <div className="p-6 sm:p-8 bg-dark-card border border-dark-border rounded-2xl text-center space-y-4 shadow-sm">
        <span className="inline-block px-3 py-1 text-xs font-semibold text-brand-400 bg-brand-500/10 border border-brand-500/25 rounded-full">
          Ready to Explore
        </span>
        <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
          Ready to inspect live predictions?
        </h3>
        <p className="text-xs sm:text-sm text-slate-400 max-w-lg mx-auto leading-relaxed">
          Explore 15 Philippine companies tracked across banking, property, retail, mining, and utilities, or save tickers to your personal Watchlist.
        </p>
        <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/companies"
            className="px-6 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold shadow-md shadow-brand-500/20 transition-all outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            Explore Companies →
          </Link>
          <Link
            href="/watchlist"
            className="px-6 py-2.5 rounded-xl bg-dark-bg border border-dark-border hover:border-slate-500 text-slate-200 text-sm font-semibold transition-all outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            My Watchlist ★
          </Link>
        </div>
      </div>
    </div>
  );
}
