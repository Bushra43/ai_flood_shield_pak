"use client";

import { ArrowDownUp, Database } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { formatDisplayDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { HistoryPoint } from "@/types/floodshield";

interface HistoricalTableProps {
  history: HistoryPoint[];
}

type SortKey = "date" | "inflow" | "outflow";

export function HistoricalTable({ history }: HistoricalTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [asc, setAsc] = useState(true);
  const [showAll, setShowAll] = useState(false);

  const latestDate = history[history.length - 1]?.date;

  const rows = useMemo(() => {
    const sorted = [...history].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return asc
        ? Number(av) - Number(bv)
        : Number(bv) - Number(av);
    });
    return showAll ? sorted : sorted.slice(-8);
  }, [history, sortKey, asc, showAll]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(true);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              Recent Marala Observations
            </h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Inflow, outflow and risk level for Chenab at Marala
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowAll((v) => !v)}
          >
            <Database className="h-4 w-4" />
            {showAll ? "Collapse Dataset" : "View Full Historical Dataset"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <SortableHead
                  label="Date"
                  active={sortKey === "date"}
                  onClick={() => toggleSort("date")}
                />
                <SortableHead
                  label="Inflow"
                  active={sortKey === "inflow"}
                  onClick={() => toggleSort("inflow")}
                />
                <SortableHead
                  label="Outflow"
                  active={sortKey === "outflow"}
                  onClick={() => toggleSort("outflow")}
                />
                <th className="px-4 py-3 font-semibold">Risk Level</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isLatest = row.date === latestDate;
                return (
                  <tr
                    key={row.date}
                    className={cn(
                      "border-t border-slate-100 transition-colors dark:border-slate-800",
                      isLatest
                        ? "bg-teal-50/70 dark:bg-teal-950/40"
                        : "bg-white hover:bg-slate-50/80 dark:bg-slate-900 dark:hover:bg-slate-800/80",
                    )}
                  >
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                      {formatDisplayDate(row.date)}
                      {isLatest ? (
                        <span className="ml-2 rounded-full bg-teal-800 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                          Latest
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700 dark:text-slate-300">
                      {row.inflow.toFixed(1)}k
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700 dark:text-slate-300">
                      {row.outflow.toFixed(1)}k
                    </td>
                    <td className="px-4 py-3">
                      <StatusPill level="Normal" size="sm" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function SortableHead({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <th className="px-4 py-3">
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 font-semibold uppercase tracking-wider",
          active
            ? "text-teal-800 dark:text-teal-300"
            : "text-slate-500 dark:text-slate-400",
        )}
      >
        {label}
        <ArrowDownUp className="h-3.5 w-3.5" />
      </button>
    </th>
  );
}
