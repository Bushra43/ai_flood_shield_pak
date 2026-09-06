"use client";

import { AiCommunityAlert } from "@/components/alerts/AiCommunityAlert";
import { SystemArchitecture } from "@/components/architecture/SystemArchitecture";
import { RiverFlowChart } from "@/components/charts/RiverFlowChart";
import { AboutSection } from "@/components/dashboard/AboutSection";
import { CurrentVsForecast } from "@/components/dashboard/CurrentVsForecast";
import { DataSources } from "@/components/dashboard/DataSources";
import { FloodAlertHero } from "@/components/dashboard/FloodAlertHero";
import { Header } from "@/components/dashboard/Header";
import { HistoricalTable } from "@/components/dashboard/HistoricalTable";
import { MetricCards } from "@/components/dashboard/MetricCards";
import { EmptyState, LoadingState } from "@/components/dashboard/States";
import { DecisionEngine } from "@/components/model/DecisionEngine";
import { MlPredictionPanel } from "@/components/model/MlPredictionPanel";
import { ModelDevelopment } from "@/components/model/ModelDevelopment";
import { ProjectInfo } from "@/components/model/ProjectInfo";
import { Section } from "@/components/ui/section";
import { useFloodShieldData } from "@/lib/hooks/useFloodShieldData";
import { MOCK_MODEL_INFO } from "@/data/mock";

export function DashboardShell() {
  const { data, isLoading, isRefreshing, refresh } = useFloodShieldData();
  const status = data.status;
  const history = data.history;
  const modelInfo = data.modelInfo ?? MOCK_MODEL_INFO;

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#e8f1f4_0%,_#f5f8fb_45%,_#eef2f6_100%)]">
      <Header
        lastUpdated={status?.date ?? data.lastFetchedAt}
        mode={data.mode}
        isRefreshing={isRefreshing}
        onRefresh={refresh}
      />

      <main className="mx-auto max-w-7xl space-y-14 px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12">
        <section id="overview" className="scroll-mt-28 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-800">
                AI-Powered Flood Prediction & Early Warning System
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
                AI FLOODSHIELD PAK
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
                Real-time flood intelligence combining official hydrological
                data, machine learning and generative AI.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white/80 px-4 py-3 text-right shadow-sm backdrop-blur">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Monitoring Focus
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                CHENAB RIVER • MARALA STATION
              </p>
            </div>
          </div>

          {isLoading ? <LoadingState /> : null}

          {!isLoading && !status ? (
            <EmptyState message="No FloodShield status data is available." />
          ) : null}

          {data.errorMessage ? (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {data.errorMessage}
            </p>
          ) : null}

          {!isLoading && status ? (
            <div className="animate-fade-in space-y-6">
              <FloodAlertHero status={status} />
              <MetricCards status={status} />
            </div>
          ) : null}
        </section>

        {!isLoading && status ? (
          <>
            <Section
              id="live-monitoring"
              eyebrow="Live Monitoring"
              title="Hydrological Situation"
              description="Observed Chenab River flows at Marala with official FFD forecast context."
            >
              <div className="space-y-6">
                <RiverFlowChart history={history} status={status} />
                <CurrentVsForecast status={status} />
              </div>
            </Section>

            <Section
              id="ai-prediction"
              eyebrow="AI Prediction"
              title="Model Intelligence & Alert Fusion"
              description="Machine-learning prediction, risk fusion and community-facing bilingual alerts."
            >
              <div className="space-y-6">
                <MlPredictionPanel status={status} />
                <DecisionEngine status={status} />
                <AiCommunityAlert status={status} />
              </div>
            </Section>

            <Section
              id="historical-data"
              eyebrow="Historical Data"
              title="Observation Record"
              description="Recent Marala station observations used for situational monitoring."
            >
              {history.length === 0 ? (
                <EmptyState message="No historical observations available yet." />
              ) : (
                <HistoricalTable history={history} />
              )}
            </Section>

            <Section
              eyebrow="Model Development"
              title="Engineering Story"
              description="How archival FFD data becomes a live FloodShield prediction and alert system."
            >
              <div className="space-y-6">
                <ModelDevelopment />
                <ProjectInfo modelInfo={modelInfo} />
              </div>
            </Section>

            <Section
              id="system-architecture"
              eyebrow="Architecture"
              title="Deployable FloodShield Stack"
              description="Training and live inference paths rendered as system components."
            >
              <SystemArchitecture />
            </Section>

            <Section
              eyebrow="Credibility"
              title="Data Provenance"
              description="Official sources that underwrite FloodShield intelligence."
            >
              <DataSources />
            </Section>

            <Section id="about" eyebrow="Project" title="About FloodShield">
              <AboutSection />
            </Section>
          </>
        ) : null}
      </main>

      <footer className="border-t border-slate-200/80 bg-white/70">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>AI FloodShield PAK — University AI/ML Research Prototype</p>
          <p>Chenab River • Marala Station • Decision-support only</p>
        </div>
      </footer>
    </div>
  );
}
