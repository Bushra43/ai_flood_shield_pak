"use client";

import { Menu, Moon, RefreshCw, Shield, Sun, X } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HARDCODED_LAST_UPDATED_LABEL } from "@/data/hardcodedDisplay";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import type { DataSourceMode } from "@/types/floodshield";

const NAV_ITEMS = [
  { href: "#risk-level", label: "Risk Level", tab: "risk" },
  { href: "#community-alert", label: "Community Alert", tab: "community" },
  { href: "#live-monitoring", label: "Live Monitoring", tab: "monitoring" },
  { href: "#historical-data", label: "Historical Data", tab: "historical" },
  { href: "#about", label: "About", tab: "about" },
] as const;

interface HeaderProps {
  lastUpdated: string | null;
  mode: DataSourceMode;
  bulletinStatus?: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  activeTab?: string;
  onTabChange?: (tab: string) => void;
}

export function Header({
  mode,
  isRefreshing,
  onRefresh,
  activeTab,
  onTabChange,
}: HeaderProps) {
  const [open, setOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();

  function handleNav(tab: string) {
    onTabChange?.(tab);
    setOpen(false);
  }

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-[var(--header-bg)] backdrop-blur-md dark:border-slate-800/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-900 text-white shadow-sm dark:bg-teal-700">
            <Shield className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold tracking-[0.04em] text-slate-900 dark:text-slate-50 sm:text-base">
              AI FLOODSHIELD PAK
            </p>
            <p className="truncate text-[11px] text-slate-500 dark:text-slate-400 sm:text-xs">
              Flood Intelligence & Early Warning
            </p>
          </div>
        </div>

        <nav className="hidden items-center gap-1 lg:flex">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.tab}
              type="button"
              onClick={() => handleNav(item.tab)}
              className={cn(
                "rounded-lg px-2.5 py-2 text-xs font-medium transition-colors",
                activeTab === item.tab
                  ? "bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-slate-50"
                  : "text-slate-600 hover:bg-white hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-50",
              )}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <Badge variant="live">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            LIVE
          </Badge>

          {(mode === "mock" || mode === "error") && (
            <Badge variant="demo" className="hidden sm:inline-flex">
              Demo Data
            </Badge>
          )}
          {mode === "local" && (
            <Badge variant="demo" className="hidden sm:inline-flex">
              Local Data
            </Badge>
          )}
          {mode === "cache" && (
            <Badge variant="demo" className="hidden sm:inline-flex">
              Cached
            </Badge>
          )}

          <div className="hidden text-right sm:block">
            <p className="text-[10px] uppercase tracking-wider text-slate-400">
              Last updated
            </p>
            <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
              {HARDCODED_LAST_UPDATED_LABEL}
            </p>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title={theme === "dark" ? "Light mode" : "Dark mode"}
          >
            {theme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>

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
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 lg:hidden dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            onClick={() => setOpen((v) => !v)}
            aria-label="Toggle navigation"
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-slate-200 bg-white lg:hidden dark:border-slate-800 dark:bg-slate-950">
          <nav className="mx-auto flex max-w-7xl flex-col px-4 py-3 sm:px-6">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.tab}
                type="button"
                onClick={() => handleNav(item.tab)}
                className={cn(
                  "rounded-lg px-3 py-2.5 text-left text-sm font-medium",
                  activeTab === item.tab
                    ? "bg-slate-50 text-slate-900 dark:bg-slate-800 dark:text-slate-50"
                    : "text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800",
                )}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
