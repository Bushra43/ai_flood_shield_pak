"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchDashboardData } from "@/lib/api";
import type { DashboardData } from "@/types/floodshield";

const initialState: DashboardData = {
  status: null,
  history: [],
  modelInfo: null,
  mode: "loading",
  lastFetchedAt: null,
  errorMessage: null,
};

export function useFloodShieldData() {
  const [data, setData] = useState<DashboardData>(initialState);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const load = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    else setData((prev) => ({ ...prev, mode: "loading", errorMessage: null }));

    const controller = new AbortController();
    const result = await fetchDashboardData(controller.signal);
    setData(result);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  return {
    data,
    isLoading: data.mode === "loading",
    isRefreshing,
    refresh: () => load(true),
  };
}
