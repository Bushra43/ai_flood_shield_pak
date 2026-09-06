import type {
  DashboardData,
  FloodStatus,
  HistoryPoint,
  ModelInfo,
} from "@/types/floodshield";

const CACHE_KEY = "floodshield:dashboard:v1";
const CACHE_META_KEY = "floodshield:api-base-url";

export function readCachedDashboard(): DashboardData | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = window.localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as DashboardData;
    if (!parsed || typeof parsed !== "object") return null;
    if (!parsed.status && (!parsed.history || parsed.history.length === 0)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeCachedDashboard(data: DashboardData): void {
  if (typeof window === "undefined") return;
  if (data.mode === "loading") return;

  try {
    window.localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? "";
    window.localStorage.setItem(CACHE_META_KEY, base);
  } catch {
    // Quota / private mode — ignore cache write failures.
  }
}

export function clearCachedDashboard(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(CACHE_KEY);
    window.localStorage.removeItem(CACHE_META_KEY);
  } catch {
    // ignore
  }
}

export function isValidStatus(data: unknown): data is FloodStatus {
  if (!data || typeof data !== "object") return false;
  const s = data as Record<string, unknown>;
  return (
    typeof s.date === "string" &&
    typeof s.river === "string" &&
    typeof s.station === "string" &&
    typeof s.current_inflow === "number" &&
    typeof s.final_alert === "string"
  );
}

export function isValidHistory(data: unknown): data is HistoryPoint[] {
  return (
    Array.isArray(data) &&
    data.every(
      (item) =>
        item &&
        typeof item === "object" &&
        typeof (item as HistoryPoint).date === "string" &&
        typeof (item as HistoryPoint).inflow === "number" &&
        typeof (item as HistoryPoint).outflow === "number",
    )
  );
}

export function isValidModelInfo(data: unknown): data is ModelInfo {
  return Boolean(data && typeof data === "object");
}
