import { formatPct, formatPeso } from "@/lib/format";
import type { SectorSnapshotData } from "@/lib/sectorComparison";

interface SectorSnapshotProps {
  snapshot: SectorSnapshotData;
}

export default function SectorSnapshot({ snapshot }: SectorSnapshotProps) {
  const { selectedCount, largestMove, beatingNaiveCount } = snapshot;

  const isMovePositive = largestMove ? largestMove.pctChange >= 0 : true;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 sm:gap-4">
      {/* 1. Selected Companies */}
      <div className="rounded-xl border border-dark-border bg-dark-card p-4 sm:p-4.5 shadow-sm transition-colors hover:border-brand-500/40">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Selected Companies
        </p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl sm:text-3xl font-extrabold text-white">
            {selectedCount}
          </span>
          <span className="text-xs text-slate-400">study equities</span>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">
          Equal coverage across sector peers
        </p>
      </div>

      {/* 2. Largest Expected Move */}
      <div className="rounded-xl border border-dark-border bg-dark-card p-4 sm:p-4.5 shadow-sm transition-colors hover:border-brand-500/40">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Largest Expected Move
        </p>
        <div className="mt-2 flex flex-wrap items-baseline gap-2">
          {largestMove ? (
            <>
              <span className="text-xl sm:text-2xl font-extrabold text-white">
                {largestMove.symbol}
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-bold ${
                  isMovePositive
                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                }`}
              >
                <span>{isMovePositive ? "▲" : "▼"}</span>
                <span>{formatPct(largestMove.pctChange)}</span>
              </span>
            </>
          ) : (
            <span className="text-xl font-bold text-slate-400">--</span>
          )}
        </div>
        <p className="mt-1 text-[11px] text-slate-500">
          {largestMove
            ? `Next-session expected delta (${formatPeso(largestMove.pesoChange)})`
            : "No forecast move available"}
        </p>
      </div>

      {/* 3. Principal Models Beating Naive */}
      <div className="rounded-xl border border-dark-border bg-dark-card p-4 sm:p-4.5 shadow-sm transition-colors hover:border-brand-500/40">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Principal Models Beating Naive
        </p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl sm:text-3xl font-extrabold text-white">
            {beatingNaiveCount} of {selectedCount}
          </span>
          <span className="text-xs text-slate-400">
            ({selectedCount > 0 ? Math.round((beatingNaiveCount / selectedCount) * 100) : 0}%)
          </span>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">
          Selected model held-out RMSE &lt; Naive benchmark
        </p>
      </div>
    </div>
  );
}
