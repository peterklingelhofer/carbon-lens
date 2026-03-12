import type {
  CarbonIntensity,
  CarbonSavingsReport,
  CloudRegion,
  HealthResponse,
  RouteRequest,
  RouteResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  route: (body: RouteRequest) =>
    request<RouteResponse>("/api/v1/route", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  regions: (provider?: string) =>
    request<CloudRegion[]>(
      `/api/v1/regions${provider ? `?provider=${provider}` : ""}`
    ),

  carbonIntensity: (provider: string, region: string) =>
    request<CarbonIntensity>(`/api/v1/carbon/${provider}/${region}`),

  savings: () => request<CarbonSavingsReport>("/api/v1/accounting/savings"),

  providers: () =>
    request<{
      configured: Record<string, boolean>;
      missing: Record<string, boolean>;
      total_configured: number;
      total_available: number;
    }>("/health/providers"),

  plans: () =>
    request<
      Array<{
        name: string;
        daily_limit: number;
        price_cents: number;
        features: string[];
      }>
    >("/api/v1/billing/plans"),

  billingStatus: () =>
    request<{
      api_key_id: string | null;
      tier: string;
      today_usage: number;
      daily_limit: number;
      remaining: number;
    }>("/api/v1/billing/status"),
};
