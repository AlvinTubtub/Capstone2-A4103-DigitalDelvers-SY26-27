/**
 * Pure client-side storage utilities for the PSE Pulse Watchlist.
 * Stored in browser localStorage using ticker symbols only.
 */

export const WATCHLIST_STORAGE_KEY = "forecastph_watchlist";
export const WATCHLIST_MAX_ITEMS = 5;

/**
 * Retrieve the current watchlist array from localStorage safely.
 * Returns an array of uppercase ticker strings (max 5, deduplicated).
 */
export function getStoredWatchlist(): string[] {
  if (typeof window === "undefined") return [];

  try {
    const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      window.localStorage.removeItem(WATCHLIST_STORAGE_KEY);
      return [];
    }

    // Filter valid strings, uppercase, deduplicate, limit to 5
    const cleaned = Array.from(
      new Set(
        parsed
          .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
          .map((sym) => sym.trim().toUpperCase())
      )
    ).slice(0, WATCHLIST_MAX_ITEMS);

    return cleaned;
  } catch {
    // Best-effort cleanup. This may itself fail when storage is unavailable.
    try {
      window.localStorage.removeItem(WATCHLIST_STORAGE_KEY);
    } catch {}
    return [];
  }
}

/**
 * Save the watchlist array to localStorage safely.
 */
export function setStoredWatchlist(symbols: string[]): boolean {
  if (typeof window === "undefined") return false;

  try {
    const cleaned = Array.from(
      new Set(symbols.map((sym) => sym.trim().toUpperCase()))
    ).slice(0, WATCHLIST_MAX_ITEMS);

    window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(cleaned));
    return true;
  } catch {
    return false;
  }
}
