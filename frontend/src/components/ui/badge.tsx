import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "soft" | "live" | "demo";
}

export function Badge({
  children,
  className,
  variant = "default",
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium tracking-wide",
        variant === "default" && "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900",
        variant === "outline" &&
          "border border-slate-200 bg-white text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200",
        variant === "soft" &&
          "bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
        variant === "live" &&
          "border border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
        variant === "demo" &&
          "border border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200",
        className,
      )}
    >
      {children}
    </span>
  );
}
