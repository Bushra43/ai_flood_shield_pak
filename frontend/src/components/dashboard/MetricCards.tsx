import {
  Activity,
  ArrowUpRight,
  Brain,
  Droplets,
  Gauge,
  ShieldAlert,
  Waves,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { formatCusecs, formatPercent } from "@/lib/format";
import { getRiskStyle } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { FloodStatus } from "@/types/floodshield";

interface MetricCardsProps {
  status: FloodStatus;
}

export function MetricCards({ status }: MetricCardsProps) {
  const cards = [
    {
      key: "inflow",
      title: "Current Inflow",
      value: `${formatCusecs(status.current_inflow)} cusecs`,
      explanation: "Live observed river inflow at Marala.",
      icon: Droplets,
      accent: "text-sky-700 bg-sky-50 border-sky-100",
      featured: true,
    },
    {
      key: "outflow",
      title: "Current Outflow",
      value: `${formatCusecs(status.current_outflow)} cusecs`,
      explanation: "Measured release downstream of the station.",
      icon: Waves,
      accent: "text-cyan-700 bg-cyan-50 border-cyan-100",
      featured: false,
    },
    {
      key: "forecast",
      title: "FFD Forecast",
      value: `${status.ffd_forecast_text}k cusecs`,
      explanation: "Official 24-hour inflow outlook from FFD.",
      icon: ArrowUpRight,
      accent: "text-teal-800 bg-teal-50 border-teal-100",
      featured: true,
    },
    {
      key: "confidence",
      title: "ML Confidence",
      value: formatPercent(status.ml_confidence),
      explanation: "Classifier confidence for tomorrow’s class.",
      icon: Gauge,
      accent: "text-indigo-700 bg-indigo-50 border-indigo-100",
      featured: false,
    },
    {
      key: "danger",
      title: "Current Danger",
      value: status.current_danger,
      explanation: "Present river danger classification.",
      icon: Activity,
      risk: status.current_danger,
      featured: false,
    },
    {
      key: "ffd-risk",
      title: "FFD Risk",
      value: status.ffd_forecast_risk,
      explanation: "Risk inferred from the FFD forecast band.",
      icon: ShieldAlert,
      risk: status.ffd_forecast_risk,
      featured: false,
    },
    {
      key: "ml",
      title: "ML Tomorrow",
      value: status.ml_next_day_risk,
      explanation: "Next-day FloodShield model prediction.",
      icon: Brain,
      risk: status.ml_next_day_risk,
      featured: false,
    },
    {
      key: "final",
      title: "Final Alert",
      value: status.final_alert,
      explanation: "Fused alert from current, FFD and ML signals.",
      icon: ShieldAlert,
      risk: status.final_alert,
      featured: true,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon;
        const riskStyle = card.risk ? getRiskStyle(card.risk) : null;

        return (
          <Card
            key={card.key}
            className={cn(
              "p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md",
              card.featured && "sm:col-span-1",
              card.key === "final" && riskStyle
                ? cn("border-2", riskStyle.border, riskStyle.softBg)
                : "",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-xl border",
                  riskStyle
                    ? cn(riskStyle.softBg, riskStyle.border, riskStyle.text)
                    : card.accent,
                )}
              >
                <Icon className="h-5 w-5" />
              </div>
              {card.risk ? <StatusPill level={card.risk} size="sm" /> : null}
            </div>

            <p className="mt-4 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              {card.title}
            </p>
            <p
              className={cn(
                "mt-2 font-mono text-2xl font-semibold tracking-tight text-slate-900",
                riskStyle?.text,
              )}
            >
              {typeof card.value === "string" && card.risk
                ? String(card.value).toUpperCase()
                : card.value}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">
              {card.explanation}
            </p>
          </Card>
        );
      })}
    </div>
  );
}
