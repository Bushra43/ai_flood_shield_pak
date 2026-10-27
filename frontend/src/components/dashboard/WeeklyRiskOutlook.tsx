import { CloudSun } from "lucide-react";
import { Card } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { HARDCODED_WEEKLY_OUTLOOK } from "@/data/hardcodedDisplay";
import { getRiskStyle } from "@/lib/risk";
import { cn } from "@/lib/utils";

export function WeeklyRiskOutlook() {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
          Flood risk — next week
        </p>
        <h3 className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-50">
          25–31 October 2026
        </h3>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {HARDCODED_WEEKLY_OUTLOOK.map((day) => {
          const style = getRiskStyle(day.risk_level);
          return (
            <Card
              key={day.date}
              className={cn(
                "border p-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md",
                style.border,
                style.softBg,
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                    {day.label}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    Risk Level
                  </p>
                </div>
                <StatusPill level={day.risk_level} size="sm" />
              </div>

              <div className="mt-4 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                <p className="inline-flex items-center gap-1.5 font-medium text-slate-800 dark:text-slate-100">
                  <CloudSun className="h-3.5 w-3.5 text-slate-500 dark:text-slate-400" />
                  {day.weather}
                </p>
                <p>Wind: {day.wind}</p>
                <p>Humidity: {day.humidity}</p>
                <p>Precipitation: {day.precipitation}</p>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
