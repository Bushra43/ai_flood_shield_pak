"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchDashboardData } from "@/lib/api";
import { readCachedDashboard } from "@/lib/storage";
import type { DashboardData } from "@/types/floodshield";

const initialState: DashboardData = {
  status: null,
  history: [],
  modelInfo: null,
  mode: "loading",
  lastFetchedAt: null,
  errorMessage: null,
};

function getHydratedState(): DashboardData {
  const cached = readCachedDashboard();
  if (cached?.status) {
    return {
      ...cached,
      mode: "loading",
      errorMessage: null,
    };
  }
  return initialState;
}

export function useFloodShieldData() {
  const [data, setData] = useState<DashboardData>(initialState);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    setData(getHydratedState());
    setHasHydrated(true);
  }, []);

  const load = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    else {
      setData((prev) => ({
        ...prev,
        mode: prev.status ? prev.mode : "loading",
        errorMessage: null,
      }));
    }

    const result = await fetchDashboardData();
    setData(result);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    if (!hasHydrated) return;
    void load(false);
  }, [hasHydrated, load]);

  return {
    data,
    isLoading: data.mode === "loading" && !data.status,
    isRefreshing,
    refresh: () => load(true),
  };
}
