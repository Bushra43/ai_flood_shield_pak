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

const DEFAULT_TIMEOUT_MS = 90_000;

const DEPLOYED_API_BASE_URL = "https://sardar19-floodshield-api.hf.space";

/**
 * Backend base URL.
 * - Unset → live Hugging Face Space
 * - Empty string → built-in demo data
 * - Any other value → that API (local FastAPI, etc.)
 */
export function getApiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (raw !== undefined) {
    const base = raw.trim();
    if (!base) return null;
    return base.replace(/\/$/, "");
  }
  return DEPLOYED_API_BASE_URL;
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

function isHuggingFaceSpace(base: string): boolean {
  return /hf\.space|huggingface\.co/i.test(base);
}

function parseGradioSse<T>(text: string): T {
  const events = text.split("\n\n");
  let lastError: string | null = null;

  for (const event of events) {
    const lines = event.split("\n");
    const eventName = lines
      .find((line) => line.startsWith("event:"))
      ?.slice(6)
      .trim();
    const dataLine = lines.find((line) => line.startsWith("data:"));
    if (!dataLine) continue;

    const raw = dataLine.slice(5).trim();
    if (!raw || raw === "null") continue;

    let data: unknown;
    try {
      data = JSON.parse(raw);
    } catch {
      continue;
    }

    if (eventName === "error") {
      const err = data as { error?: string };
      lastError = err.error ?? "Gradio error";
      continue;
    }

    if (data && typeof data === "object") {
      const record = data as Record<string, unknown>;
      const output = record.output as { data?: unknown[] } | undefined;
      if (output?.data && output.data.length > 0) {
        return output.data[0] as T;
      }
      if (Array.isArray(record.data) && record.data.length > 0) {
        return record.data[0] as T;
      }
    }
  }

  throw new Error(lastError ?? "Gradio response missing data");
}

async function fetchGradio<T>(
  base: string,
  apiName: string,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    const started = await fetch(`${base}/gradio_api/call/${apiName}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ data: [] }),
      cache: "no-store",
      signal: controller.signal,
    });

    if (!started.ok) {
      throw new Error(`Gradio call failed (${started.status}) for ${apiName}`);
    }

    const payload = (await started.json()) as { event_id?: string };
    if (!payload.event_id) {
      throw new Error(`Gradio call missing event_id for ${apiName}`);
    }

    const stream = await fetch(
      `${base}/gradio_api/call/${apiName}/${payload.event_id}`,
      {
        headers: { Accept: "text/event-stream" },
        cache: "no-store",
        signal: controller.signal,
      },
    );

    if (!stream.ok) {
      throw new Error(`Gradio stream failed (${stream.status}) for ${apiName}`);
    }

    return parseGradioSse<T>(await stream.text());
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", onAbort);
  }
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
    const [statusResult, historyResult, modelResult] = isHuggingFaceSpace(base)
      ? await Promise.allSettled([
          fetchGradio<FloodStatus>(base, "status", signal),
          fetchGradio<HistoryPoint[]>(base, "history", signal),
          fetchGradio<ModelInfo>(base, "model_info", signal),
        ])
      : await Promise.allSettled([
          fetchJson<FloodStatus>(base, "/api/status?refresh=false", signal),
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
