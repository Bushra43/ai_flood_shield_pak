"use client";

import { Brain, CircleDot, MapPin, Radio, Waves } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { formatPercent } from "@/lib/format";
import { getRiskStyle } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { FloodStatus } from "@/types/floodshield";

interface MlPredictionPanelProps {
  status: FloodStatus;
}

export function MlPredictionPanel({ status }: MlPredictionPanelProps) {
  const risk = getRiskStyle(status.ml_next_day_risk);
  const confidence =
    status.ml_confidence == null
      ? 0
      : Math.max(0, Math.min(100, status.ml_confidence));
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (confidence / 100) * circumference;

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-800">
              FloodShield ML
            </p>
            <h3 className="mt-1 text-lg font-semibold text-slate-900">
              FloodShield ML Prediction
            </h3>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-800">
            <Brain className="h-5 w-5" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Tomorrow&apos;s predicted condition
            </p>
            <p className={cn("mt-2 text-4xl font-bold tracking-tight", risk.text)}>
              {risk.label}
            </p>
            <div className="mt-3">
              <StatusPill level={status.ml_next_day_risk} />
            </div>
          </div>

          <div className="mx-auto flex flex-col items-center">
            <div className="relative h-36 w-36">
              <svg className="h-full w-full -rotate-90" viewBox="0 0 128 128">
                <circle
                  cx="64"
                  cy="64"
                  r={radius}
                  fill="none"
                  stroke="#e2e8f0"
                  strokeWidth="10"
                />
                <circle
                  cx="64"
                  cy="64"
                  r={radius}
                  fill="none"
                  stroke="#0f766e"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={offset}
                  className="transition-all duration-700 ease-out"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-mono text-2xl font-bold text-slate-900">
                  {formatPercent(confidence)}
                </span>
                <span className="text-[10px] uppercase tracking-wider text-slate-500">
                  Confidence
                </span>
              </div>
            </div>
            <p className="mt-2 text-xs font-medium text-slate-500">
              Classifier confidence
            </p>
          </div>
        </div>

        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900">
          Classifier confidence represents the model&apos;s confidence in its
          predicted class and should not be interpreted as a guaranteed
          probability of flooding.
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          <MetaItem icon={<Radio className="h-4 w-4" />} label="Model status" value="Online" />
          <MetaItem icon={<CircleDot className="h-4 w-4" />} label="Prediction horizon" value="7-day outlook (day +1…+7)" />
          <MetaItem icon={<MapPin className="h-4 w-4" />} label="Monitoring station" value="Marala" />
          <MetaItem icon={<Waves className="h-4 w-4" />} label="River" value="Chenab" />
        </div>
      </CardContent>
    </Card>
  );
}

function MetaItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex items-center gap-2 text-slate-500">
        {icon}
        <span className="text-[11px] font-semibold uppercase tracking-wider">
          {label}
        </span>
      </div>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}
