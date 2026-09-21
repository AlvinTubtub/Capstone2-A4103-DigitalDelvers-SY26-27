"use client";

import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { href: "#overview", label: "Overview" },
  { href: "#methodology", label: "Methodology" },
  { href: "#model-performance", label: "Performance" },
  { href: "#scope", label: "Scope" },
  { href: "#architecture", label: "Architecture" },
  { href: "#data", label: "Data" },
  { href: "#limitations", label: "Limitations" },
];

export default function AboutInPageNav() {
  const [activeAnchor, setActiveAnchor] = useState("#overview");

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 180;
      for (let i = NAV_ITEMS.length - 1; i >= 0; i--) {
        const item = NAV_ITEMS[i];
        const el = document.querySelector(item.href);
        if (el) {
          const top = (el as HTMLElement).offsetTop;
          if (scrollPosition >= top) {
            setActiveAnchor(item.href);
            break;
          }
        }
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      aria-label="About In-Page Navigation"
      className="sticky top-16 z-30 -mx-4 px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 py-2.5 sm:py-3 bg-dark-bg/95 backdrop-blur-md border-b border-dark-border/80 transition-all"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-start sm:justify-center overflow-x-auto no-scrollbar gap-2 sm:gap-2.5">
        {NAV_ITEMS.map((item) => {
          const isActive = activeAnchor === item.href;
          return (
            <a
              key={item.href}
              href={item.href}
              className={`px-3.5 py-1.5 sm:px-4 sm:py-2 rounded-full text-xs sm:text-sm font-medium whitespace-nowrap transition-all outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg ${
                isActive
                  ? "bg-brand-600 text-white font-semibold shadow-xs ring-1 ring-brand-400/40"
                  : "bg-dark-card text-slate-300 hover:text-white hover:bg-dark-card/90 border border-dark-border hover:border-brand-500/40"
              }`}
            >
              {item.label}
            </a>
          );
        })}
      </div>
    </nav>
  );
}
