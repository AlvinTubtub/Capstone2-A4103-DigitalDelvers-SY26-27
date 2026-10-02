import InfoTooltip from "@/components/InfoTooltip";
import type { CompanyTooltipId } from "@/lib/tooltipContent";

export default function StatCard({
  label,
  value,
  sublabel,
  accent = "text-white",
  tooltipId,
}: {
  label: string;
  value: string;
  sublabel?: string;
  accent?: string;
  tooltipId?: CompanyTooltipId;
}) {
  return (
    <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
        {tooltipId && <InfoTooltip id={tooltipId} />}
      </div>
      <p className={`text-3xl font-bold mb-1 ${accent}`}>{value}</p>
      {sublabel && <p className="text-sm text-slate-400">{sublabel}</p>}
    </div>
  );
}
