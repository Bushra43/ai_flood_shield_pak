import { MOCK_HISTORY, MOCK_MODEL_INFO, MOCK_STATUS } from "@/data/mock";
import type {
  DashboardData,
  FloodStatus,
  HistoryPoint,
  ModelInfo,
} from "@/types/floodshield";

const DEFAULT_TIMEOUT_MS = 6000;

function getBaseUrl(): string | null {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) return null;
  return base.replace(/\/$/, "");
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const base = getBaseUrl();
  if (!base) {
    throw new Error("API base URL is not configured");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    const response = await fetch(`${base}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Request failed (${response.status}) for ${path}`);
    }

    return (await response.json()) as T;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", onAbort);
  }
}

function isValidStatus(data: unknown): data is FloodStatus {
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

function isValidHistory(data: unknown): data is HistoryPoint[] {
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

/**
 * Fetches FloodShield dashboard payloads from the Python backend.
 * Falls back to realistic mock data when the API is unavailable.
 */
export async function fetchDashboardData(
  signal?: AbortSignal,
): Promise<DashboardData> {
  const base = getBaseUrl();
  const fetchedAt = new Date().toISOString();

  if (!base) {
    return {
      status: MOCK_STATUS,
      history: MOCK_HISTORY,
      modelInfo: MOCK_MODEL_INFO,
      mode: "mock",
      lastFetchedAt: fetchedAt,
      errorMessage: null,
    };
  }

  try {
    const [statusResult, historyResult, modelResult] = await Promise.allSettled([
      fetchJson<FloodStatus>("/api/status", signal),
      fetchJson<HistoryPoint[]>("/api/history", signal),
      fetchJson<ModelInfo>("/api/model-info", signal),
    ]);

    const status =
      statusResult.status === "fulfilled" && isValidStatus(statusResult.value)
        ? statusResult.value
        : null;

    const history =
      historyResult.status === "fulfilled" && isValidHistory(historyResult.value)
        ? historyResult.value
        : null;

    const modelInfo =
      modelResult.status === "fulfilled" && modelResult.value
        ? modelResult.value
        : null;

    if (!status && !history) {
      return {
        status: MOCK_STATUS,
        history: MOCK_HISTORY,
        modelInfo: modelInfo ?? MOCK_MODEL_INFO,
        mode: "mock",
        lastFetchedAt: fetchedAt,
        errorMessage: "Backend unavailable — showing demo data",
      };
    }

    if (!status) {
      return {
        status: MOCK_STATUS,
        history: history ?? MOCK_HISTORY,
        modelInfo: modelInfo ?? MOCK_MODEL_INFO,
        mode: "mock",
        lastFetchedAt: fetchedAt,
        errorMessage: "Status endpoint unavailable — using demo status",
      };
    }

    return {
      status,
      history: history ?? [],
      modelInfo: modelInfo ?? MOCK_MODEL_INFO,
      mode: history && history.length === 0 ? "empty" : "api",
      lastFetchedAt: fetchedAt,
      errorMessage: null,
    };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unable to reach FloodShield API";

    return {
      status: MOCK_STATUS,
      history: MOCK_HISTORY,
      modelInfo: MOCK_MODEL_INFO,
      mode: "mock",
      lastFetchedAt: fetchedAt,
      errorMessage: message,
    };
  }
}

export function getOfficialFfdBulletinUrl(): string {
  return "https://ffd.pmd.gov.pk/bulletin";
}

export function getOfficialFfdHomeUrl(): string {
  return "https://ffd.pmd.gov.pk/";
}
