import { ArrowDown, ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function Node({
  title,
  subtitle,
  tone = "default",
}: {
  title: string;
  subtitle?: string;
  tone?: "default" | "dark" | "accent" | "output";
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-3 text-center shadow-sm",
        tone === "default" && "border-slate-200 bg-white text-slate-900",
        tone === "dark" && "border-teal-900 bg-teal-950 text-white",
        tone === "accent" && "border-teal-200 bg-teal-50 text-teal-950",
        tone === "output" && "border-emerald-200 bg-emerald-50 text-emerald-950",
      )}
    >
      <p className="text-sm font-semibold">{title}</p>
      {subtitle ? (
        <p
          className={cn(
            "mt-1 text-xs",
            tone === "dark" ? "text-teal-100/80" : "text-slate-500",
          )}
        >
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}

function VArrow() {
  return (
    <div className="flex justify-center py-2 text-slate-400">
      <ArrowDown className="h-4 w-4" />
    </div>
  );
}

export function SystemArchitecture() {
  return (
    <Card className="p-6 sm:p-8">
      <div className="mb-8 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-800">
          System Design
        </p>
        <h3 className="mt-1 text-xl font-semibold text-slate-900">
          FloodShield System Architecture
        </h3>
        <p className="mt-2 text-sm text-slate-500">
          Dual-path architecture: historical training pipeline and live FFD
          inference fused into bilingual alerts for the dashboard and mobile app.
        </p>
      </div>

      <div className="grid gap-8 xl:grid-cols-[1fr_auto_1.2fr]">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            Training Path
          </p>
          <Node title="Historical FFD Data" subtitle="2024 + 2025 PDFs" />
          <VArrow />
          <Node title="Data Extraction" />
          <VArrow />
          <Node title="Cleaning + Feature Engineering" />
          <VArrow />
          <Node title="Marala ML Dataset" />
          <VArrow />
          <Node title="Machine Learning Model" />
          <VArrow />
          <Node
            title="Trained floodshield_model.pkl"
            tone="accent"
          />
        </div>

        <div className="hidden items-center xl:flex">
          <div className="rounded-full border border-slate-200 bg-slate-50 p-3 text-slate-400">
            <ArrowRight className="h-5 w-5" />
          </div>
        </div>

        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            Live Inference Path
          </p>
          <Node title="FFD Website" subtitle="Live Data 24/7" />
          <VArrow />
          <Node title="FloodShield Engine" tone="dark" />
          <VArrow />

          <div className="grid gap-2 sm:grid-cols-3">
            <Node title="Current Danger" tone="accent" />
            <Node title="FFD Forecast Risk" tone="accent" />
            <Node title="ML Prediction" tone="accent" />
          </div>

          <VArrow />
          <Node title="Risk Fusion" tone="dark" />
          <VArrow />
          <Node title="Qwen AI Alert Generator" />
          <VArrow />
          <Node title="English / Urdu Alerts" tone="output" />
          <VArrow />
          <Node title="Dashboard / Mobile App" tone="output" />
        </div>
      </div>
    </Card>
  );
}
