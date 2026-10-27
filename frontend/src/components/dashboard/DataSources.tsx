import { ExternalLink, Landmark, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { getOfficialFfdBulletinUrl, getOfficialFfdHomeUrl } from "@/lib/api";

export function DataSources() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="p-6 lg:col-span-2">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-900 text-white dark:bg-teal-700">
            <Landmark className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              Trusted Data Sources
            </h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              FloodShield consumes official hydrological bulletins and public
              agency reports. It does not replace government warning systems.
            </p>
          </div>
        </div>

        <div className="mt-6 space-y-4">
          <SourceRow
            title="Flood Forecasting Division — Pakistan Meteorological Department"
            detail="Primary official river observation and forecast source"
            href={getOfficialFfdHomeUrl()}
            linkLabel="ffd.pmd.gov.pk"
          />
          <SourceRow
            title="FFD Bulletins"
            detail="Live station inflow, outflow and 24-hour forecast updates"
            href={getOfficialFfdBulletinUrl()}
            linkLabel="Official bulletin"
          />
          <SourceRow
            title="Punjab PDMA Gauge Reports"
            detail="Complementary gauge context for provincial monitoring"
          />
          <SourceRow
            title="Punjab PDMA Rainfall Reports"
            detail="Supporting rainfall context for flood situational awareness"
          />
        </div>
      </Card>

      <Card className="border-teal-200 bg-teal-50/60 p-6 dark:border-teal-800 dark:bg-teal-950/40">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-teal-800 shadow-sm dark:bg-slate-900 dark:text-teal-300">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-teal-950 dark:text-teal-100">
          Independent Decision Support
        </h3>
        <p className="mt-3 text-sm leading-relaxed text-teal-900/80 dark:text-teal-200/80">
          FloodShield is an independent AI decision-support and research project
          that uses official source data. Official warnings issued by government
          authorities always take precedence.
        </p>
      </Card>
    </div>
  );
}

function SourceRow({
  title,
  detail,
  href,
  linkLabel,
}: {
  title: string;
  detail: string;
  href?: string;
  linkLabel?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-700 dark:bg-slate-800/50">
      <p className="font-semibold text-slate-900 dark:text-slate-100">{title}</p>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{detail}</p>
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-1.5 text-sm font-medium text-teal-800 hover:underline dark:text-teal-300"
        >
          {linkLabel ?? href}
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : null}
    </div>
  );
}
