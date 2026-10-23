import { ArrowRight, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { formatCusecs, percentIncrease } from "@/lib/format";
import type { FloodStatus } from "@/types/floodshield";

interface CurrentVsForecastProps {
  status: FloodStatus;
}

export function CurrentVsForecast({ status }: CurrentVsForecastProps) {
  const forecastMin = status.ffd_forecast_min;
  const forecastMax = status.ffd_forecast_max;
  const hasBand =
    typeof forecastMin === "number" && typeof forecastMax === "number";
  const mid = hasBand
    ? (forecastMin + forecastMax) / 2
    : status.current_inflow;
  const increase = hasBand
    ? percentIncrease(status.current_inflow, mid)
    : 0;

  return (
    <Card className="overflow-hidden p-6 sm:p-8">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            Current vs FFD Forecast
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Near-term inflow trajectory based on official FFD guidance
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-sm font-semibold text-teal-800">
          <TrendingUp className="h-4 w-4" />
          {hasBand && status.forecast_status !== "expired"
            ? `+${increase.toFixed(0)}% vs current`
            : "Not a current forecast"}
        </div>
      </div>

      <div className="grid items-center gap-4 lg:grid-cols-[1fr_auto_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Current
          </p>
          <p className="mt-3 font-mono text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
            {formatCusecs(status.current_inflow)}
          </p>
          <p className="mt-2 text-sm text-slate-500">thousand cusecs inflow</p>
        </div>

        <div className="flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal-800 text-white shadow-md">
            <ArrowRight className="h-5 w-5" />
          </div>
        </div>

        <div className="rounded-2xl border border-teal-200 bg-teal-50/70 p-5 sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
            FFD Next 24 Hours
          </p>
          <p className="mt-3 font-mono text-4xl font-bold tracking-tight text-teal-900 sm:text-5xl">
            {status.ffd_forecast_text}k
          </p>
          <p className="mt-2 text-sm text-teal-800/80">
            thousand cusecs inflow band
          </p>
        </div>
      </div>

      <p className="mt-6 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed text-slate-600">
        A forecast increase in inflow does not automatically mean flooding.
        FloodShield fuses FFD outlook with current danger and ML prediction
        before issuing the final alert level.
      </p>
    </Card>
  );
}
