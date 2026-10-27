"use client";

import { useState } from "react";
import { AiCommunityAlert } from "@/components/alerts/AiCommunityAlert";
import { RiverFlowChart } from "@/components/charts/RiverFlowChart";
import { AboutSection } from "@/components/dashboard/AboutSection";
import { FloodAlertHero } from "@/components/dashboard/FloodAlertHero";
import { Header } from "@/components/dashboard/Header";
import { HistoricalTable } from "@/components/dashboard/HistoricalTable";
import { EmptyState, LoadingState } from "@/components/dashboard/States";
import { WeeklyRiskOutlook } from "@/components/dashboard/WeeklyRiskOutlook";
import { MOCK_STATUS } from "@/data/mock";
import { useFloodShieldData } from "@/lib/hooks/useFloodShieldData";

type DashboardTab =
  | "risk"
  | "community"
  | "monitoring"
  | "historical"
  | "about";

export function DashboardShell() {
  const { data, isLoading, isRefreshing, refresh } = useFloodShieldData();
  const [activeTab, setActiveTab] = useState<DashboardTab>("risk");
  const status = data.status ?? (isLoading ? null : MOCK_STATUS);
  const history = data.history;

  return (
    <div className="min-h-screen bg-[image:var(--page-gradient)]">
      <Header
        lastUpdated={status?.date ?? data.lastFetchedAt}
        mode={data.mode}
        bulletinStatus={status?.forecast_status}
        isRefreshing={isRefreshing}
        onRefresh={refresh}
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab as DashboardTab)}
      />

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12">
        <section className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-800 dark:text-teal-300">
                AI-Powered Flood Prediction & Early Warning System
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50 sm:text-4xl">
                AI FLOODSHIELD PAK
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600 dark:text-slate-300 sm:text-base">
                Real-time flood intelligence combining official hydrological
                data, machine learning and generative AI.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white/80 px-4 py-3 text-right shadow-sm backdrop-blur dark:border-slate-700 dark:bg-slate-900/80">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Monitoring Focus
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
                CHENAB RIVER • MARALA STATION
              </p>
            </div>
          </div>

          {data.errorMessage ? (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-100">
              {data.errorMessage}
            </p>
          ) : null}
        </section>

        {isLoading && !status ? <LoadingState /> : null}

        {!isLoading && !status ? (
          <EmptyState message="No FloodShield status data is available." />
        ) : null}

        {status ? (
          <div className="animate-fade-in min-h-[28rem]">
            {activeTab === "risk" ? (
              <section id="risk-level" className="space-y-6">
                <FloodAlertHero status={status} />
                <WeeklyRiskOutlook />
              </section>
            ) : null}

            {activeTab === "community" ? (
              <section id="community-alert">
                <AiCommunityAlert status={status} />
              </section>
            ) : null}

            {activeTab === "monitoring" ? (
              <section id="live-monitoring" className="space-y-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-800 dark:text-teal-300">
                    Live Monitoring
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
                    Hydrological Situation
                  </h2>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                    Observed Chenab River flows at Marala station.
                  </p>
                </div>
                <RiverFlowChart history={history} status={status} />
              </section>
            ) : null}

            {activeTab === "historical" ? (
              <section id="historical-data" className="space-y-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-800 dark:text-teal-300">
                    Historical Data
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
                    Observation Record
                  </h2>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                    Recent Marala station observations used for situational
                    monitoring.
                  </p>
                </div>
                {history.length === 0 ? (
                  <EmptyState message="No historical observations available yet." />
                ) : (
                  <HistoricalTable history={history} />
                )}
              </section>
            ) : null}

            {activeTab === "about" ? (
              <section id="about">
                <AboutSection />
              </section>
            ) : null}
          </div>
        ) : null}
      </main>

      <footer className="border-t border-slate-200/80 bg-white/70 dark:border-slate-800 dark:bg-slate-950/70">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-sm text-slate-500 dark:text-slate-400 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>AI FloodShield PAK — University AI/ML Research Prototype</p>
          <p>Chenab River • Marala Station • Decision-support only</p>
        </div>
      </footer>
    </div>
  );
}
