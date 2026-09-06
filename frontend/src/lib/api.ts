import { MOCK_HISTORY, MOCK_MODEL_INFO, MOCK_STATUS } from "@/data/mock";
import {
  isValidHistory,
  isValidModelInfo,
  isValidStatus,
  readCachedDashboard,
  writeCachedDashboard,
} from "@/lib/storage";
import type {
  DashboardData,
  FloodStatus,
  HistoryPoint,
  ModelInfo,
} from "@/types/floodshield";

const DEFAULT_TIMEOUT_MS = 20_000;

/**
 * Backend base URL for when FloodShield is deployed / running locally.
 * Leave unset to serve built-in demo data from localStorage.
 */
export function getApiBaseUrl(): string | null {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!base) return null;
  return base.replace(/\/$/, "");
}

function localDashboard(
  overrides: Partial<DashboardData> = {},
): DashboardData {
  const fetchedAt = new Date().toISOString();
  const payload: DashboardData = {
    status: MOCK_STATUS,
    history: MOCK_HISTORY,
    modelInfo: MOCK_MODEL_INFO,
    mode: "local",
    lastFetchedAt: fetchedAt,
    errorMessage: null,
    ...overrides,
  };
  writeCachedDashboard(payload);
  return payload;
}

async function fetchJson<T>(
  base: string,
  path: string,
  signal?: AbortSignal,
): Promise<T> {
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

function fromCacheOrLocal(errorMessage: string | null): DashboardData {
  const cached = readCachedDashboard();
  if (cached?.status) {
    return {
      ...cached,
      mode: "cache",
      lastFetchedAt: cached.lastFetchedAt ?? new Date().toISOString(),
      errorMessage:
        errorMessage ??
        "Showing last saved FloodShield snapshot from local storage",
    };
  }

  return localDashboard({
    mode: "mock",
    errorMessage:
      errorMessage ?? "Backend unavailable — showing demo data",
  });
}

/**
 * Fetches FloodShield dashboard payloads from the Python backend.
 *
 * Resolution order:
 *  1. NEXT_PUBLIC_API_BASE_URL → live API (cached to localStorage)
 *  2. localStorage cache from a previous successful load
 *  3. Built-in local demo mock (also written to localStorage)
 */
export async function fetchDashboardData(
  signal?: AbortSignal,
): Promise<DashboardData> {
  const base = getApiBaseUrl();
  const fetchedAt = new Date().toISOString();

  if (!base) {
    const cached = readCachedDashboard();
    if (cached?.status && cached.mode === "local") {
      return {
        ...cached,
        mode: "local",
        lastFetchedAt: fetchedAt,
        errorMessage: null,
      };
    }
    return localDashboard({ lastFetchedAt: fetchedAt });
  }

  try {
    const refreshQuery = "?refresh=false";
    const [statusResult, historyResult, modelResult] = await Promise.allSettled([
      fetchJson<FloodStatus>(base, `/api/status${refreshQuery}`, signal),
      fetchJson<HistoryPoint[]>(base, "/api/history?limit=30", signal),
      fetchJson<ModelInfo>(base, "/api/model-info", signal),
    ]);

    const status =
      statusResult.status === "fulfilled" && isValidStatus(statusResult.value)
        ? statusResult.value
        : null;

    const history =
      historyResult.status === "fulfilled" &&
      isValidHistory(historyResult.value)
        ? historyResult.value
        : null;

    const modelInfo =
      modelResult.status === "fulfilled" &&
      isValidModelInfo(modelResult.value)
        ? modelResult.value
        : null;

    if (!status) {
      const reason =
        statusResult.status === "rejected"
          ? statusResult.reason instanceof Error
            ? statusResult.reason.message
            : "Status endpoint unavailable"
          : "Status endpoint returned an invalid payload";

      return fromCacheOrLocal(reason);
    }

    const payload: DashboardData = {
      status,
      history: history ?? [],
      modelInfo: modelInfo ?? MOCK_MODEL_INFO,
      mode: history && history.length === 0 ? "empty" : "api",
      lastFetchedAt: fetchedAt,
      errorMessage: null,
    };

    writeCachedDashboard(payload);
    return payload;
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unable to reach FloodShield API";

    return fromCacheOrLocal(message);
  }
}

export function getOfficialFfdBulletinUrl(): string {
  return "https://ffd.pmd.gov.pk/bulletin";
}

export function getOfficialFfdHomeUrl(): string {
  return "https://ffd.pmd.gov.pk/";
}
