/**
 * Live HTTP adapter — talks to FastAPI. Never mixes mock fixtures.
 * Admin token stored in sessionStorage; provider keys never touch the client store.
 */

import type {
  AdminSettingsView,
  CreateRunInput,
  CreateRunResponse,
  Feasibility,
  NovaApiClientLike,
  RunSnapshot,
} from "./mock-types";

const ADMIN_TOKEN_KEY = "nova_admin_token";

function apiBase(): string {
  // Empty string = same-origin (Caddy/proxy). Unset falls back to local API.
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL !== undefined) {
    return String(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
}

function adminToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
  else sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function getAdminToken(): string | null {
  return adminToken();
}

async function request<T>(
  path: string,
  init?: RequestInit & { auth?: boolean }
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (init?.auth) {
    const token = adminToken();
    if (!token) throw new Error("AUTH_REQUIRED");
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { code?: string; message_fa?: string; detail?: string };
      detail = body.code || body.message_fa || body.detail || "";
    } catch {
      detail = res.statusText;
    }
    if (res.status === 404) throw new Error(`RUN_NOT_FOUND:${detail}`);
    if (res.status === 401) throw new Error(`AUTH_FAILED:${detail}`);
    throw new Error(detail || `HTTP_${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function adminLogin(username: string, password: string): Promise<string> {
  const out = await request<{ access_token: string }>("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setAdminToken(out.access_token);
  return out.access_token;
}

export async function adminLogout(): Promise<void> {
  try {
    await request("/api/admin/logout", { method: "POST", auth: true });
  } catch {
    // ignore
  }
  setAdminToken(null);
}

export function eventsUrl(runId: string, lastEventId?: string | null): string {
  const q = lastEventId
    ? `?last_event_id=${encodeURIComponent(lastEventId)}`
    : "";
  return `${apiBase()}/api/runs/${encodeURIComponent(runId)}/events${q}`;
}

export const liveAdapter: NovaApiClientLike = {
  source: "live",

  async createRun(input: CreateRunInput): Promise<CreateRunResponse> {
    return request<CreateRunResponse>("/api/runs", {
      method: "POST",
      body: JSON.stringify({
        product: input.product,
        origin_country: input.origin_country,
        hs_code: input.hs_code,
      }),
    });
  },

  async getRun(id: string): Promise<RunSnapshot> {
    return request<RunSnapshot>(`/api/runs/${encodeURIComponent(id)}`);
  },

  async getMarkets(id: string) {
    return request(`/api/runs/${encodeURIComponent(id)}/markets`);
  },

  async selectCountry(id: string, countryCode: string): Promise<RunSnapshot> {
    return request<RunSnapshot>(`/api/runs/${encodeURIComponent(id)}/buyers`, {
      method: "POST",
      body: JSON.stringify({ country_code: countryCode }),
    });
  },

  async getBuyers(id: string) {
    const snap = await this.getRun(id);
    return snap.buyers;
  },

  async postFeasibility(id, costUpdates, assumptions) {
    return request<Feasibility>(`/api/runs/${encodeURIComponent(id)}/feasibility`, {
      method: "POST",
      body: JSON.stringify({ cost_updates: costUpdates ?? null, input_assumptions: assumptions }),
    });
  },

  async getReport(id: string) {
    return request(`/api/runs/${encodeURIComponent(id)}/report`);
  },

  async getAdminSettings(): Promise<AdminSettingsView> {
    return request<AdminSettingsView>("/api/admin/providers", { auth: true });
  },
};
