"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  WATCHLIST_STORAGE_KEY,
  WATCHLIST_MAX_ITEMS,
  getStoredWatchlist,
  setStoredWatchlist,
} from "@/lib/watchlist";

export interface WatchlistContextType {
  watchlist: string[];
  isWatching: (symbol: string) => boolean;
  toggleWatchlist: (symbol: string) => { success: boolean; message?: string };
  removeFromWatchlist: (symbol: string) => void;
  clearWatchlist: () => void;
  toastMessage: string | null;
  dismissToast: () => void;
  maxLimit: number;
}

const WatchlistContext = createContext<WatchlistContextType | null>(null);

export function WatchlistProvider({
  children,
  validSymbols,
}: {
  children: React.ReactNode;
  validSymbols: string[];
}) {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const allowedSymbols = React.useMemo(
    () => new Set(validSymbols.map((symbol) => symbol.trim().toUpperCase())),
    [validSymbols]
  );

  const loadWatchlist = useCallback(() => {
    const stored = getStoredWatchlist();
    const valid = stored.filter((symbol) => allowedSymbols.has(symbol));
    if (valid.length !== stored.length) setStoredWatchlist(valid);
    return valid;
  }, [allowedSymbols]);

  // Hydrate from localStorage on client mount
  useEffect(() => {
    setWatchlist(loadWatchlist());
    setIsHydrated(true);

    // Cross-tab synchronization
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === WATCHLIST_STORAGE_KEY) {
        setWatchlist(loadWatchlist());
      }
    };

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [loadWatchlist]);

  const dismissToast = useCallback(() => {
    setToastMessage(null);
  }, []);

  const isWatching = useCallback(
    (symbol: string) => {
      const clean = symbol?.trim().toUpperCase();
      return watchlist.includes(clean);
    },
    [watchlist]
  );

  const toggleWatchlist = useCallback(
    (symbol: string) => {
      const clean = symbol?.trim().toUpperCase();
      if (!clean) return { success: false };

      if (!allowedSymbols.has(clean)) {
        const message = "This company is no longer available in PSE Pulse.";
        setToastMessage(message);
        return { success: false, message };
      }

      if (watchlist.includes(clean)) {
        const next = watchlist.filter((s) => s !== clean);
        if (!setStoredWatchlist(next)) {
          const message = "Your browser could not save the watchlist. Check storage settings and try again.";
          setToastMessage(message);
          return { success: false, message };
        }
        setWatchlist(next);
        return { success: true };
      }

      if (watchlist.length >= WATCHLIST_MAX_ITEMS) {
        const msg = "You can monitor up to 5 companies. Remove one from My Watchlist to add another.";
        setToastMessage(msg);
        return { success: false, message: msg };
      }

      const next = [...watchlist, clean];
      if (!setStoredWatchlist(next)) {
        const message = "Your browser could not save the watchlist. Check storage settings and try again.";
        setToastMessage(message);
        return { success: false, message };
      }
      setWatchlist(next);
      return { success: true };
    },
    [allowedSymbols, watchlist]
  );

  const removeFromWatchlist = useCallback(
    (symbol: string) => {
      const clean = symbol?.trim().toUpperCase();
      if (!clean) return;
      const next = watchlist.filter((s) => s !== clean);
      if (setStoredWatchlist(next)) setWatchlist(next);
      else setToastMessage("Your browser could not save the watchlist. Check storage settings and try again.");
    },
    [watchlist]
  );

  const clearWatchlist = useCallback(() => {
    if (setStoredWatchlist([])) setWatchlist([]);
    else setToastMessage("Your browser could not save the watchlist. Check storage settings and try again.");
  }, []);

  return (
    <WatchlistContext.Provider
      value={{
        watchlist: isHydrated ? watchlist : [],
        isWatching,
        toggleWatchlist,
        removeFromWatchlist,
        clearWatchlist,
        toastMessage,
        dismissToast,
        maxLimit: WATCHLIST_MAX_ITEMS,
      }}
    >
      {children}
      {/* Toast Notification for limit or warnings */}
      {toastMessage && (
        <div className="fixed bottom-20 md:bottom-8 right-4 z-50 max-w-md bg-dark-card border border-amber-500/50 text-slate-100 p-4 rounded-xl shadow-2xl backdrop-blur-md animate-[fadeIn_0.2s_ease-out]">
          <div className="flex items-start gap-3">
            <span className="text-amber-400 text-lg leading-none mt-0.5">⚠️</span>
            <div className="flex-1 text-xs sm:text-sm text-slate-200 leading-relaxed">
              {toastMessage}
            </div>
            <button
              type="button"
              onClick={dismissToast}
              className="text-slate-400 hover:text-white text-xs font-semibold p-1 cursor-pointer"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist(): WatchlistContextType {
  const ctx = useContext(WatchlistContext);
  if (!ctx) {
    throw new Error("useWatchlist must be used within a WatchlistProvider");
  }
  return ctx;
}
