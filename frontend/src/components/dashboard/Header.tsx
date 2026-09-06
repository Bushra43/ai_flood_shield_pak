"use client";

import { Menu, RefreshCw, Shield, X } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDisplayDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DataSourceMode } from "@/types/floodshield";

const NAV_ITEMS = [
  { href: "#overview", label: "Overview" },
  { href: "#live-monitoring", label: "Live Monitoring" },
  { href: "#ai-prediction", label: "AI Prediction" },
  { href: "#historical-data", label: "Historical Data" },
  { href: "#system-architecture", label: "System Architecture" },
  { href: "#about", label: "About" },
];

interface HeaderProps {
  lastUpdated: string | null;
  mode: DataSourceMode;
  isRefreshing: boolean;
  onRefresh: () => void;
}

export function Header({
  lastUpdated,
  mode,
  isRefreshing,
  onRefresh,
}: HeaderProps) {
  const [open, setOpen] = useState(false);
  const displayDate = lastUpdated
    ? formatDisplayDate(lastUpdated.slice(0, 10))
    : "04 Sep 2026";

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-[#f5f8fb]/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-900 text-white shadow-sm">
            <Shield className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold tracking-[0.04em] text-slate-900 sm:text-base">
              AI FLOODSHIELD PAK
            </p>
            <p className="truncate text-[11px] text-slate-500 sm:text-xs">
              Flood Intelligence & Early Warning
            </p>
          </div>
        </div>

        <nav className="hidden items-center gap-1 xl:flex">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-lg px-2.5 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-white hover:text-slate-900"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <Badge variant="live" className="hidden sm:inline-flex">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            LIVE
          </Badge>

          {(mode === "mock" || mode === "error") && (
            <Badge variant="demo">Demo Data</Badge>
          )}

          <div className="hidden text-right md:block">
            <p className="text-[10px] uppercase tracking-wider text-slate-400">
              Last updated
            </p>
            <p className="text-xs font-medium text-slate-700">{displayDate}</p>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            disabled={isRefreshing}
            aria-label="Refresh data"
          >
            <RefreshCw
              className={cn("h-4 w-4", isRefreshing && "animate-spin")}
            />
            <span className="hidden sm:inline">Refresh</span>
          </Button>

          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 xl:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-label="Toggle navigation"
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-slate-200 bg-white xl:hidden">
          <nav className="mx-auto flex max-w-7xl flex-col px-4 py-3 sm:px-6">
            {NAV_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
