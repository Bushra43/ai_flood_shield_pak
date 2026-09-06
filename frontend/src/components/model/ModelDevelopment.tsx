import {
  Bot,
  Brain,
  Database,
  FileText,
  Filter,
  FlaskConical,
  Package,
  Radio,
  Sparkles,
  Wrench,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STEPS = [
  { title: "Historical FFD PDFs", detail: "2024 + 2025", icon: FileText },
  { title: "PDF Data Extraction", detail: "Structured parsing", icon: Database },
  { title: "Data Cleaning", detail: "Quality controls", icon: Filter },
  { title: "Feature Engineering", detail: "Hydrological features", icon: Wrench },
  { title: "Chenab / Marala ML Dataset", detail: "Station-focused corpus", icon: FlaskConical },
  { title: "ML Model Training", detail: "Risk classification", icon: Brain },
  { title: "2026 Model Testing", detail: "Live-period evaluation", icon: Sparkles },
  { title: "floodshield_model.pkl", detail: "Deployable artifact", icon: Package },
  { title: "Live FFD Data", detail: "Bulletin ingestion", icon: Radio },
  { title: "FloodShield Prediction Engine", detail: "Risk fusion", icon: Brain },
  { title: "Qwen AI", detail: "Alert generation", icon: Bot },
  { title: "English + Urdu Community Alerts", detail: "Public communication", icon: Sparkles },
];

export function ModelDevelopment() {
  return (
    <Card className="p-6 sm:p-8">
      <div className="mb-8 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-800">
          Engineering Pipeline
        </p>
        <h3 className="mt-1 text-xl font-semibold text-slate-900 sm:text-2xl">
          From Raw Government Data to Real-Time AI Warnings
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-slate-500">
          End-to-end FloodShield workflow from archival FFD PDFs through trained
          model inference and bilingual community alerts.
        </p>
      </div>

      <div className="relative">
        <div className="absolute left-6 top-4 bottom-4 hidden w-px bg-gradient-to-b from-teal-700 via-teal-300 to-teal-700 md:block" />
        <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {STEPS.map((step, index) => {
            const Icon = step.icon;
            return (
              <li
                key={step.title}
                className={cn(
                  "relative rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md",
                  index === STEPS.length - 1 && "border-teal-300 bg-teal-50/50",
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-900 text-white">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Stage {String(index + 1).padStart(2, "0")}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">
                      {step.title}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">{step.detail}</p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </Card>
  );
}
