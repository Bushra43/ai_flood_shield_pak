import { Card } from "@/components/ui/card";

export function AboutSection() {
  return (
    <Card className="p-6 sm:p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-800">
        About
      </p>
      <h3 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
        AI FloodShield PAK
      </h3>
      <div className="mt-4 max-w-4xl space-y-4 text-[15px] leading-7 text-slate-700">
        <p>
          AI FloodShield PAK is an AI-powered flood detection, prediction and
          early-warning project designed to make flood intelligence easier to
          understand for communities in Pakistan.
        </p>
        <p>
          The system combines official hydrological observations with
          machine-learning predictions and generative AI to transform technical
          river information into clear English and Urdu alerts.
        </p>
      </div>
      <p className="mt-6 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        FloodShield is a decision-support and research system. Official warnings
        issued by government authorities always take precedence.
      </p>
    </Card>
  );
}
