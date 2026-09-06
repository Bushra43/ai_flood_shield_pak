import { Activity, ArrowDownRight, Brain, Gauge } from "lucide-react";
import { Card } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { formatCusecs, formatPercent } from "@/lib/format";
import { getRiskStyle } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { FloodStatus } from "@/types/floodshield";

interface FloodAlertHeroProps {
  status: FloodStatus;
}

export function FloodAlertHero({ status }: FloodAlertHeroProps) {
  const alertStyle = getRiskStyle(status.final_alert);

  return (
    <Card
      className={cn(
        "overflow-hidden border-2 transition-colors duration-500",
        alertStyle.border,
        "bg-gradient-to-br from-white via-white to-slate-50",
      )}
    >
      <div className="grid gap-0 lg:grid-cols-[1.4fr_1fr]">
        <div className="p-6 sm:p-8 lg:p-10">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-slate-900 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-white">
              {status.river} River
            </span>
            <span className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
              {status.station}
            </span>
          </div>

          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            Final Alert Level
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
            <StatusPill level={status.final_alert} size="lg" />
          </div>

          <p className="mt-5 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
            Current conditions remain within normal levels, while FFD forecasts
            increased inflow during the next 24 hours.
          </p>
        </div>

        <div className={cn("border-t border-slate-100 p-6 sm:p-8 lg:border-l lg:border-t-0", alertStyle.softBg)}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <HeroStat
              icon={<Activity className="h-4 w-4" />}
              label="Current"
              value={`${formatCusecs(status.current_inflow)} cusecs`}
            />
            <HeroStat
              icon={<ArrowDownRight className="h-4 w-4" />}
              label="24-hour forecast"
              value={`${status.ffd_forecast_text}k cusecs`}
            />
            <HeroStat
              icon={<Brain className="h-4 w-4" />}
              label="ML Tomorrow"
              value={String(status.ml_next_day_risk).toUpperCase()}
            />
            <HeroStat
              icon={<Gauge className="h-4 w-4" />}
              label="Confidence"
              value={formatPercent(status.ml_confidence)}
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
    <div className="rounded-xl border border-white/70 bg-white/80 p-4 shadow-sm backdrop-blur-sm">
      <div className="flex items-center gap-2 text-slate-500">
        {icon}
        <span className="text-[11px] font-semibold uppercase tracking-wider">
          {label}
        </span>
      </div>
      <p className="mt-2 font-mono text-lg font-semibold tracking-tight text-slate-900">
        {value}
      </p>
    </div>
  );
}
