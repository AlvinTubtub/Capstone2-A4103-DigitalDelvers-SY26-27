"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  renderIcon: (active: boolean) => React.ReactNode;
}

const ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Home",
    renderIcon: (active) => (
      <svg
        className={`w-5 h-5 ${active ? "stroke-brand-400 stroke-2" : "stroke-current stroke-1.5"}`}
        fill="none"
        viewBox="0 0 24 24"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1V9.5z" />
      </svg>
    ),
  },
  {
    href: "/companies",
    label: "Companies",
    renderIcon: (active) => (
      <svg
        className={`w-5 h-5 ${active ? "stroke-brand-400 stroke-2" : "stroke-current stroke-1.5"}`}
        fill="none"
        viewBox="0 0 24 24"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="4" y="3" width="16" height="18" rx="2" />
        <path d="M9 8h2m-2 4h2m-2 4h2m4-8h2m-2 4h2m-2 4h2" />
      </svg>
    ),
  },
  {
    href: "/watchlist",
    label: "My Watchlist",
    renderIcon: (active) => (
      <svg
        className={`w-5 h-5 ${
          active
            ? "fill-brand-400 text-brand-400"
            : "fill-none stroke-current stroke-1.5"
        }`}
        viewBox="0 0 24 24"
      >
        {active ? (
          <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
        ) : (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
          />
        )}
      </svg>
    ),
  },
  {
    href: "/learn-stocks",
    label: "Learn Stocks",
    renderIcon: (active) => (
      <svg
        className={`w-5 h-5 ${active ? "stroke-brand-400 stroke-2" : "stroke-current stroke-1.5"}`}
        fill="none"
        viewBox="0 0 24 24"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </svg>
    ),
  },
  {
    href: "/about",
    label: "About",
    renderIcon: (active) => (
      <svg
        className={`w-5 h-5 ${active ? "stroke-brand-400 stroke-2" : "stroke-current stroke-1.5"}`}
        fill="none"
        viewBox="0 0 24 24"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
    ),
  },
];

export default function MobileNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Mobile Navigation"
      className="fixed bottom-0 left-0 right-0 w-full glass z-50 border-t border-dark-border md:hidden safe-area-pb"
    >
      <div className="flex items-center justify-around h-16 px-1 max-w-lg mx-auto">
        {ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href ||
                pathname.startsWith(`${item.href}/`) ||
                (item.href === "/learn-stocks" && pathname.startsWith("/learn"));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center justify-center flex-1 py-1 px-0.5 rounded-lg transition-colors ${
                active
                  ? "text-brand-400 font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <div className="mb-0.5">{item.renderIcon(active)}</div>
              <span className="text-[9px] leading-tight tracking-tight max-w-[60px] text-center">
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
