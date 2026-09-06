import { Card } from "@/components/ui/card";
import type { ModelInfo } from "@/types/floodshield";

interface ProjectInfoProps {
  modelInfo: ModelInfo;
}

export function ProjectInfo({ modelInfo }: ProjectInfoProps) {
  const facts = [
    { label: "Training Data", value: modelInfo.training_data ?? "2024–2025" },
    {
      label: "Testing / Live Evaluation",
      value: modelInfo.testing_evaluation ?? "2026",
    },
    { label: "River", value: modelInfo.river ?? "Chenab" },
    { label: "Station", value: modelInfo.station ?? "Marala" },
    { label: "Data Source", value: modelInfo.data_source ?? "FFD / PMD" },
    {
      label: "ML Engine",
      value: modelInfo.ml_engine ?? "Flood Risk Classification",
    },
    { label: "Generative AI", value: modelInfo.generative_ai ?? "Qwen" },
    { label: "Live Data", value: modelInfo.live_data ?? "FFD Bulletin" },
    {
      label: "Output",
      value: modelInfo.output ?? "Bilingual Early Warning",
    },
  ];

  const metrics = [
    { label: "Accuracy", value: modelInfo.accuracy },
    { label: "Precision", value: modelInfo.precision },
    { label: "Recall", value: modelInfo.recall },
    { label: "F1 Score", value: modelInfo.f1_score },
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="p-6 lg:col-span-2">
        <h3 className="text-lg font-semibold text-slate-900">
          Project / Model Information
        </h3>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {facts.map((fact) => (
            <div
              key={fact.label}
              className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
            >
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                {fact.label}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {fact.value}
              </p>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-6">
        <h3 className="text-lg font-semibold text-slate-900">
          Evaluation Metrics
        </h3>
        <p className="mt-2 text-sm text-slate-500">
          Metrics appear once the backend supplies final evaluation scores.
        </p>
        <div className="mt-5 space-y-3">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3"
            >
              <span className="text-sm font-medium text-slate-700">
                {metric.label}
              </span>
              <span className="font-mono text-sm font-semibold text-slate-500">
                {metric.value == null
                  ? "Awaiting final evaluation"
                  : `${Number(metric.value).toFixed(1)}%`}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
