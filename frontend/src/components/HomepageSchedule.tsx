"use client";

import { useEffect, useState } from "react";
import { formatDate, formatDateTimePht } from "@/lib/format";
import { getNextScheduledCheck } from "@/lib/nextScheduledCheck";

type HomepageScheduleProps = {
  forecastDate?: string | null;
  lastRunAt?: string | null;
};

export default function HomepageSchedule({ forecastDate, lastRunAt }: HomepageScheduleProps) {
  // The server and first client render match. The browser clock is read after hydration.
  const [nextCheck, setNextCheck] = useState<string | null>(null);

  useEffect(() => {
    let boundaryTimer: ReturnType<typeof setTimeout>;

    const update = () => {
      clearTimeout(boundaryTimer);
      const check = getNextScheduledCheck(new Date());
      setNextCheck(check.toISOString());
      // At the scheduled instant, that check is no longer in the future.
      boundaryTimer = setTimeout(update, Math.max(1, check.getTime() - Date.now()));
    };

    update();
    const clockTimer = setInterval(update, 60_000);
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") update();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", update);

    return () => {
      clearTimeout(boundaryTimer);
      clearInterval(clockTimer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", update);
    };
  }, []);

  return (
    <div className="mt-6 flex max-w-full flex-col items-center">
      <div className="inline-flex max-w-full flex-wrap items-center justify-center gap-x-3 gap-y-1.5 px-4 py-2 rounded-full bg-slate-950/75 border border-white/20 text-xs !text-slate-200 backdrop-blur-md shadow-md drop-shadow-[0_1px_4px_rgba(0,0,0,0.9)]">
        {forecastDate && (
          <span className="!text-blue-300 font-semibold">
            Forecast for: {formatDate(forecastDate)}
          </span>
        )}
        {lastRunAt && (
          <span className="inline-flex max-w-full min-w-0 items-start gap-3 !text-slate-200">
            {forecastDate && <span aria-hidden="true" className="shrink-0 !text-slate-400">&middot;</span>}
            <span className="min-w-0">Last pipeline run: {formatDateTimePht(lastRunAt)}</span>
          </span>
        )}
        {nextCheck && (
          <span className="inline-flex max-w-full min-w-0 items-start gap-3 !text-slate-200">
            {(forecastDate || lastRunAt) && <span aria-hidden="true" className="shrink-0 !text-slate-400">&middot;</span>}
            <span className="min-w-0">Next scheduled check: {formatDateTimePht(nextCheck)}</span>
          </span>
        )}
      </div>
      <p className="mt-8 sm:mt-2 max-w-xl text-xs !text-slate-200 drop-shadow-[0_1px_4px_rgba(0,0,0,0.9)]">
        New data appears after the official PSE report is available and processing finishes.
      </p>
    </div>
  );
}
