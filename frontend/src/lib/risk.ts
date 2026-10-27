import type { RiskLevel } from "@/types/floodshield";

export type RiskTone =
  | "normal"
  | "low"
  | "medium"
  | "high"
  | "severe"
  | "extreme"
  | "unknown";

export interface RiskStyle {
  tone: RiskTone;
  label: string;
  text: string;
  bg: string;
  border: string;
  softBg: string;
  ring: string;
  dot: string;
  chart: string;
  description: string;
}

function normalize(level: RiskLevel): string {
  return String(level ?? "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ");
}

export function getRiskTone(level: RiskLevel): RiskTone {
  const value = normalize(level);

  if (
    value === "normal" ||
    value === "none" ||
    value === "safe" ||
    value === "below low" ||
    value === "below-low"
  ) {
    return "normal";
  }
  if (value === "low" || value === "minor") return "low";
  if (value === "medium" || value === "moderate") return "medium";
  if (value === "high") return "high";
  if (value === "very high" || value === "severe") return "severe";
  if (value === "extreme" || value === "critical") return "extreme";
  if (value === "unknown" || value === "" || value === "insufficient data") {
    return "unknown";
  }
  return "unknown";
}

export function getRiskStyle(level: RiskLevel): RiskStyle {
  const tone = getRiskTone(level);
  const label = String(level ?? "Unknown").toUpperCase();

  switch (tone) {
    case "normal":
      return {
        tone,
        label,
        text: "text-emerald-800 dark:text-emerald-300",
        bg: "bg-emerald-600",
        border: "border-emerald-200 dark:border-emerald-800",
        softBg: "bg-emerald-50 dark:bg-emerald-950/50",
        ring: "ring-emerald-200 dark:ring-emerald-800",
        dot: "bg-emerald-500",
        chart: "#059669",
        description: "Conditions are within normal operating range.",
      };
    case "low":
      return {
        tone,
        label,
        text: "text-emerald-700 dark:text-emerald-300",
        bg: "bg-emerald-500",
        border: "border-emerald-200 dark:border-emerald-800",
        softBg: "bg-emerald-50 dark:bg-emerald-950/50",
        ring: "ring-emerald-200 dark:ring-emerald-800",
        dot: "bg-emerald-500",
        chart: "#10b981",
        description: "Low flood risk. Continue routine monitoring.",
      };
    case "medium":
      return {
        tone,
        label,
        text: "text-amber-800 dark:text-amber-300",
        bg: "bg-amber-500",
        border: "border-amber-200 dark:border-amber-800",
        softBg: "bg-amber-50 dark:bg-amber-950/40",
        ring: "ring-amber-200 dark:ring-amber-800",
        dot: "bg-amber-500",
        chart: "#f59e0b",
        description: "Elevated attention recommended.",
      };
    case "high":
      return {
        tone,
        label,
        text: "text-orange-800 dark:text-orange-300",
        bg: "bg-orange-500",
        border: "border-orange-200 dark:border-orange-800",
        softBg: "bg-orange-50 dark:bg-orange-950/40",
        ring: "ring-orange-200 dark:ring-orange-800",
        dot: "bg-orange-500",
        chart: "#f97316",
        description: "High flood risk. Prepare contingency measures.",
      };
    case "severe":
      return {
        tone,
        label,
        text: "text-red-800 dark:text-red-300",
        bg: "bg-red-600",
        border: "border-red-200 dark:border-red-800",
        softBg: "bg-red-50 dark:bg-red-950/40",
        ring: "ring-red-200 dark:ring-red-800",
        dot: "bg-red-600",
        chart: "#dc2626",
        description: "Severe flood risk. Follow official guidance immediately.",
      };
    case "extreme":
      return {
        tone,
        label,
        text: "text-red-950 dark:text-red-200",
        bg: "bg-red-900",
        border: "border-red-300 dark:border-red-700",
        softBg: "bg-red-100 dark:bg-red-950/60",
        ring: "ring-red-300 dark:ring-red-700",
        dot: "bg-red-900",
        chart: "#7f1d1d",
        description: "Extreme flood risk. Prioritize life-safety actions.",
      };
    default:
      return {
        tone,
        label,
        text: "text-slate-700 dark:text-slate-300",
        bg: "bg-slate-500",
        border: "border-slate-200 dark:border-slate-700",
        softBg: "bg-slate-50 dark:bg-slate-900",
        ring: "ring-slate-200 dark:ring-slate-700",
        dot: "bg-slate-400",
        chart: "#64748b",
        description: "Risk classification unavailable.",
      };
  }
}
