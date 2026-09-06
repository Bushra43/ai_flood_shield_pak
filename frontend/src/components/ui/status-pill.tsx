import { cn } from "@/lib/utils";
import { getRiskStyle } from "@/lib/risk";
import type { RiskLevel } from "@/types/floodshield";

interface StatusPillProps {
  level: RiskLevel;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function StatusPill({ level, className, size = "md" }: StatusPillProps) {
  const style = getRiskStyle(level);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border font-semibold uppercase tracking-wide",
        style.softBg,
        style.border,
        style.text,
        size === "sm" && "px-2.5 py-1 text-[10px]",
        size === "md" && "px-3 py-1.5 text-xs",
        size === "lg" && "px-4 py-2 text-sm",
        className,
      )}
    >
      <span className={cn("h-2 w-2 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}
