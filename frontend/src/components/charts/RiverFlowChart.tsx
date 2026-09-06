"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatShortDate } from "@/lib/format";
import type { FloodStatus, HistoryPoint } from "@/types/floodshield";

interface RiverFlowChartProps {
  history: HistoryPoint[];
  status: FloodStatus;
}

export function RiverFlowChart({ history, status }: RiverFlowChartProps) {
  const lastDate = history[history.length - 1]?.date ?? status.date;
  const forecastDate = addDays(lastDate, 1);

  const chartData = [
    ...history.map((point, index) => ({
      date: point.date,
      label: formatShortDate(point.date),
      inflow: point.inflow,
      outflow: point.outflow,
      forecastMin: index === history.length - 1 ? status.ffd_forecast_min : null,
      forecastMax: index === history.length - 1 ? status.ffd_forecast_max : null,
      isLatest: index === history.length - 1,
    })),
    {
      date: forecastDate,
      label: formatShortDate(forecastDate),
      inflow: null,
      outflow: null,
      forecastMin: status.ffd_forecast_min,
      forecastMax: status.ffd_forecast_max,
      isLatest: false,
    },
  ];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Chenab River Flow — Marala
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Observed inflow/outflow with FFD 24-hour forecast band
            </p>
          </div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Flow (thousand cusecs)
          </p>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[320px] w-full sm:h-[380px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{ top: 12, right: 12, left: 0, bottom: 8 }}
            >
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "#64748b", fontSize: 12 }}
                axisLine={{ stroke: "#cbd5e1" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={42}
                label={{
                  value: "Thousand cusecs",
                  angle: -90,
                  position: "insideLeft",
                  offset: 10,
                  style: { fill: "#94a3b8", fontSize: 11 },
                }}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 12,
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 8px 24px rgba(15,23,42,0.08)",
                }}
                formatter={(value, name) => {
                  if (value == null || typeof value !== "number") return ["—", String(name)];
                  const labels: Record<string, string> = {
                    inflow: "Inflow",
                    outflow: "Outflow",
                    forecastMin: "Forecast min",
                    forecastMax: "Forecast max",
                  };
                  return [`${value.toFixed(1)}k cusecs`, labels[String(name)] ?? String(name)];
                }}
              />
              <Legend />
              <ReferenceArea
                x1={formatShortDate(lastDate)}
                x2={formatShortDate(forecastDate)}
                fill="#0f766e"
                fillOpacity={0.06}
              />
              <ReferenceLine
                x={formatShortDate(lastDate)}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                label={{
                  value: "Forecast →",
                  position: "insideTopRight",
                  fill: "#64748b",
                  fontSize: 11,
                }}
              />
              <Area
                type="monotone"
                dataKey="forecastMax"
                stroke="none"
                fill="#14b8a6"
                fillOpacity={0.18}
                name="Forecast max"
                connectNulls
              />
              <Area
                type="monotone"
                dataKey="forecastMin"
                stroke="none"
                fill="#ffffff"
                fillOpacity={1}
                name="Forecast min"
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="inflow"
                name="Inflow"
                stroke="#0369a1"
                strokeWidth={2.5}
                dot={(props) => {
                  const { cx, cy, payload } = props;
                  if (cx == null || cy == null) return null;
                  if (payload?.isLatest) {
                    return (
                      <circle
                        key={`inflow-${payload.date}`}
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill="#0369a1"
                        stroke="#fff"
                        strokeWidth={2}
                      />
                    );
                  }
                  return (
                    <circle
                      key={`inflow-${payload?.date ?? cx}`}
                      cx={cx}
                      cy={cy}
                      r={3}
                      fill="#0369a1"
                    />
                  );
                }}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="outflow"
                name="Outflow"
                stroke="#0f766e"
                strokeWidth={2.5}
                strokeDasharray="6 4"
                dot={{ r: 3, fill: "#0f766e" }}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Shaded region shows the official FFD 24-hour forecast range (
          {status.ffd_forecast_text} thousand cusecs). Latest observation is
          highlighted on the inflow series.
        </p>
      </CardContent>
    </Card>
  );
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}
