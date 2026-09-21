"use client";

import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import CompanyLogo from "@/components/CompanyLogo";
import BrandLogo from "@/components/BrandLogo";
import type { CompanySummary } from "@/lib/types";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/companies", label: "Companies" },
  { href: "/watchlist", label: "My Watchlist" },
  { href: "/learn-stocks", label: "Learn Stocks" },
  { href: "/about", label: "About" },
];

export default function Navbar({
  companies,
}: {
  companies: CompanySummary[];
}) {
  const pathname = usePathname();
  const [query, setQuery] = useState("");

  const matches = useMemo(() => {
    if (!query.trim()) return [];

    const q = query.toLowerCase();

    return companies
      .filter(
        (c) =>
          c.symbol.toLowerCase().includes(q) ||
          c.name.toLowerCase().includes(q)
      )
      .slice(0, 5);
  }, [query, companies]);

  function goTo(url: string) {
    setQuery("");
    window.location.assign(url);
  }

  return (
    <nav className="fixed top-0 w-full glass z-50 border-b border-dark-border">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a
            href="/"
            aria-label="PSE Pulse home"
            className="flex items-center transition-transform hover:opacity-95"
          >
            <BrandLogo variant="navbar" />
          </a>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-baseline space-x-1">
            {LINKS.map((link) => {
              const active =
                link.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(link.href);

              return (
                <a
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors hover:bg-white/5 hover:text-white ${
                    active
                      ? "bg-brand-600 text-white"
                      : "text-slate-300"
                  }`}
                >
                  {link.label}
                </a>
              );
            })}
          </div>

          {/* Search + Theme */}
          <div className="flex items-center gap-3">
            <div className="relative hidden sm:block">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 text-sm">
                🔍
              </div>

              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="block w-48 lg:w-64 pl-9 pr-3 py-1.5 border border-dark-border rounded-full leading-5 bg-dark-bg text-slate-300 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 focus:border-brand-500 sm:text-sm transition-colors"
                placeholder="Search symbol or name..."
              />

              {matches.length > 0 && (
                <div className="absolute mt-1 w-full bg-dark-card border border-dark-border rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto">
                  {matches.map((company) => (
                    <button
                      key={company.symbol}
                      type="button"
                      onClick={() =>
                        goTo(`/companies/${company.symbol}`)
                      }
                      className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 transition-colors flex items-center gap-2.5"
                    >
                      <CompanyLogo symbol={company.symbol} size="xs" />
                      <div className="truncate min-w-0">
                        <span className="font-semibold text-white">
                          {company.symbol}
                        </span>
                        <span className="text-slate-400 text-xs">
                          {" "}
                          — {company.name}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <ThemeToggle />
          </div>
        </div>
      </div>
    </nav>
  );
}