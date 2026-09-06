import { ArrowDown, Cpu, Shield } from "lucide-react";
import { Card } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { getRiskStyle } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { FloodStatus } from "@/types/floodshield";

interface DecisionEngineProps {
  status: FloodStatus;
}

export function DecisionEngine({ status }: DecisionEngineProps) {
  const finalStyle = getRiskStyle(status.final_alert);

  const inputs = [
    {
      title: "Current River Condition",
      value: status.current_danger,
      detail: "Observed danger class at Marala",
    },
    {
      title: "FFD 24-Hour Forecast Risk",
      value: status.ffd_forecast_risk,
      detail: "Official forecast risk signal",
    },
    {
      title: "ML Next-Day Prediction",
      value: status.ml_next_day_risk,
      detail: "FloodShield classifier output",
    },
  ];

  return (
    <Card className="p-6 sm:p-8">
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-800">
          Decision Engine
        </p>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">
          FloodShield Decision Engine
        </h3>
        <p className="mt-2 max-w-3xl text-sm text-slate-500">
          Three independent signals enter the risk fusion engine to produce one
          operational alert level for communities and responders.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {inputs.map((input) => {
          const style = getRiskStyle(input.value);
          return (
            <div
              key={input.title}
              className={cn(
                "rounded-2xl border p-5 transition-colors",
                style.border,
                style.softBg,
              )}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                {input.title}
              </p>
              <p className={cn("mt-3 text-2xl font-bold", style.text)}>
                {String(input.value).toUpperCase()}
              </p>
              <div className="mt-3">
                <StatusPill level={input.value} size="sm" />
              </div>
              <p className="mt-3 text-sm text-slate-600">{input.detail}</p>
            </div>
          );
        })}
      </div>

      <div className="my-6 flex flex-col items-center gap-2">
        <div className="hidden h-px w-full bg-gradient-to-r from-transparent via-slate-300 to-transparent lg:block" />
        <div className="flex items-center gap-2 text-slate-400">
          <ArrowDown className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-[0.16em]">
            Risk Fusion
          </span>
          <ArrowDown className="h-4 w-4" />
        </div>
      </div>

      <div className="mx-auto max-w-xl rounded-2xl border-2 border-teal-800 bg-teal-950 p-6 text-center text-white shadow-lg">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-white/10">
          <Cpu className="h-6 w-6" />
        </div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-200">
          AI FloodShield PAK
        </p>
        <h4 className="mt-2 text-xl font-semibold">Risk Fusion Engine</h4>
        <p className="mt-2 text-sm text-teal-100/80">
          Combines hydrological state, official FFD risk and ML prediction into
          a single actionable alert.
        </p>
      </div>

      <div className="my-6 flex justify-center">
        <ArrowDown className="h-5 w-5 text-slate-400" />
      </div>

      <div
        className={cn(
          "mx-auto max-w-md rounded-2xl border-2 p-6 text-center",
          finalStyle.border,
          finalStyle.softBg,
        )}
      >
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-sm">
          <Shield className={cn("h-5 w-5", finalStyle.text)} />
        </div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Final Alert Level
        </p>
        <p className={cn("mt-2 text-4xl font-bold tracking-tight", finalStyle.text)}>
          {finalStyle.label}
        </p>
      </div>
    </Card>
  );
}
