import {
  Activity,
  ArrowDownRight,
  Cloud,
  CloudRain,
  Droplets,
  Wind,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { HARDCODED_TODAY } from "@/data/hardcodedDisplay";
import { getRiskStyle } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { FloodStatus } from "@/types/floodshield";

interface FloodAlertHeroProps {
  status: FloodStatus;
}

export function FloodAlertHero({ status }: FloodAlertHeroProps) {
  const alertLevel = HARDCODED_TODAY.final_alert;
  const alertStyle = getRiskStyle(alertLevel);
  const weather = HARDCODED_TODAY.weather;

  return (
    <Card
      className={cn(
        "overflow-hidden border-2 transition-colors duration-500",
        alertStyle.border,
        "bg-gradient-to-br from-white via-white to-slate-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950",
      )}
    >
      <div className="grid gap-0 lg:grid-cols-[1.4fr_1fr]">
        <div className="p-6 sm:p-8 lg:p-10">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-slate-900 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white dark:bg-slate-100 dark:text-slate-900">
              {status.river} River
            </span>
            <span className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {status.station}
            </span>
            <span className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
              24 Oct 2026
            </span>
          </div>

          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
            Final Alert Level — Today
          </p>

          <div className="mt-3 flex flex-wrap items-end gap-4">
            <h1
              className={cn(
                "text-5xl font-bold tracking-tight sm:text-6xl lg:text-7xl",
                alertStyle.text,
              )}
            >
              {alertStyle.label}
            </h1>
            <StatusPill level={alertLevel} size="lg" />
          </div>

          <p className="mt-5 max-w-2xl text-sm leading-relaxed text-slate-600 dark:text-slate-300 sm:text-base">
            Current river conditions at Marala remain calm. Observed inflow is
            low and no active FFD 24-hour forecast band is available for today.
          </p>
        </div>

        <div
          className={cn(
            "border-t border-slate-100 p-6 sm:p-8 lg:border-l lg:border-t-0 dark:border-slate-700",
            alertStyle.softBg,
          )}
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <HeroStat
              icon={<Activity className="h-4 w-4" />}
              label="Current Inflow"
              value={HARDCODED_TODAY.current_inflow_label}
            />
            <HeroStat
              icon={<ArrowDownRight className="h-4 w-4" />}
              label="FFD Forecast"
              value={HARDCODED_TODAY.ffd_forecast_label}
            />
            <HeroStat
              icon={<Cloud className="h-4 w-4" />}
              label="Current Weather"
              value={`${weather.temp} · ${weather.condition}`}
            />
            <HeroStat
              icon={<Wind className="h-4 w-4" />}
              label="Wind"
              value={weather.wind}
            />
            <HeroStat
              icon={<Droplets className="h-4 w-4" />}
              label="Humidity"
              value={weather.humidity}
            />
            <HeroStat
              icon={<CloudRain className="h-4 w-4" />}
              label="Precipitation"
              value={weather.precipitation}
            />
          </div>
        </div>
      </div>
    </Card>
  );
}

function HeroStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-white/70 bg-white/80 p-4 shadow-sm backdrop-blur-sm dark:border-slate-700/70 dark:bg-slate-900/80">
      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
        {icon}
        <span className="text-[11px] font-semibold uppercase tracking-wider">
          {label}
        </span>
      </div>
      <p className="mt-2 font-mono text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
        {value}
      </p>
    </div>
  );
}
