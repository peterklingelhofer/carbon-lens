import type {
  AlertEvent,
  BillingStatus,
  CalculationResponse,
  CarbonIntensity,
  CarbonSavingsReport,
  CloudRegion,
  ComplianceReport,
  ComplianceReportSummary,
  CronSchedule,
  GreenSLA,
  HealthResponse,
  Organization,
  PlanInfo,
  RegionLookup,
  RouteRequest,
  RouteResponse,
  ScheduleRecommendation,
  SLACheck,
  SLAMonitorStatus,
  SLAReport,
  SLASummary,
  UsageIngestionRequest,
  UsageIngestionResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const API_KEY_STORAGE_KEY = "carbon_mesh_api_key";

export function getApiKey(): string {
  try {
    return localStorage.getItem(API_KEY_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setApiKey(key: string): void {
  try {
    if (key) localStorage.setItem(API_KEY_STORAGE_KEY, key);
    else localStorage.removeItem(API_KEY_STORAGE_KEY);
  } catch {
    // localStorage unavailable (SSR/private mode) — no-op
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const apiKey = getApiKey();
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  // System
  health: () => request<HealthResponse>("/health"),

  providers: () =>
    request<{
      configured: Record<string, boolean>;
      missing: Record<string, boolean>;
      total_configured: number;
      total_available: number;
    }>("/health/providers"),

  // Routing
  route: (body: RouteRequest) =>
    request<RouteResponse>("/api/v1/route", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Regions
  regions: (provider?: string) =>
    request<CloudRegion[]>(
      `/api/v1/regions${provider ? `?provider=${provider}` : ""}`
    ),

  // Carbon data
  carbonIntensity: (provider: string, region: string) =>
    request<CarbonIntensity>(`/api/v1/carbon/${provider}/${region}`),

  carbonIntensityBatch: (regions: RegionLookup[]) =>
    request<Record<string, CarbonIntensity>>("/api/v1/carbon/batch", {
      method: "POST",
      body: JSON.stringify(regions),
    }),

  // Accounting
  savings: () => request<CarbonSavingsReport>("/api/v1/accounting/savings"),

  // Billing
  plans: () => request<PlanInfo[]>("/api/v1/billing/plans"),

  billingStatus: () => request<BillingStatus>("/api/v1/billing/status"),

  // Organizations
  orgs: {
    list: () => request<Organization[]>("/api/v1/orgs"),

    get: (slug: string) => request<Organization>(`/api/v1/orgs/${slug}`),

    create: (name: string) =>
      request<Organization>("/api/v1/orgs", {
        method: "POST",
        body: JSON.stringify({ name }),
      }),

    checkout: (orgId: string, plan: "pro" | "enterprise") =>
      request<{ checkout_url: string }>(`/api/v1/orgs/${orgId}/checkout`, {
        method: "POST",
        body: JSON.stringify({ plan }),
      }),
  },


  // SLA Monitoring
  sla: {
    list: (orgId: string) =>
      request<SLASummary[]>(`/api/v1/sla/list?org_id=${orgId}`),

    create: (body: {
      org_id: string;
      name: string;
      max_carbon_intensity_gco2_kwh: number;
      min_renewable_percentage: number;
      providers?: string[];
    }) =>
      request<GreenSLA>("/api/v1/sla/create", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    get: (slaId: string) =>
      request<GreenSLA>(`/api/v1/sla/${slaId}`),

    check: (slaId: string) =>
      request<SLACheck>(`/api/v1/sla/${slaId}/check`, {
        method: "POST",
      }),

    status: (slaId: string) =>
      request<SLACheck | null>(`/api/v1/sla/${slaId}/status`),

    checks: (slaId: string, limit?: number) =>
      request<SLACheck[]>(
        `/api/v1/sla/${slaId}/checks${limit ? `?limit=${limit}` : ""}`
      ),

    generateReport: (slaId: string, body: { org_name: string; period_days?: number }) =>
      request<SLAReport>(`/api/v1/sla/${slaId}/report`, {
        method: "POST",
        body: JSON.stringify(body),
      }),

    reports: (slaId: string) =>
      request<SLAReport[]>(`/api/v1/sla/${slaId}/reports`),

    startMonitor: (orgId: string) =>
      request<SLAMonitorStatus>(`/api/v1/sla/monitor/start?org_id=${orgId}`, {
        method: "POST",
      }),

    stopMonitor: () =>
      request<SLAMonitorStatus>("/api/v1/sla/monitor/stop", {
        method: "POST",
      }),

    monitorStatus: () =>
      request<SLAMonitorStatus>("/api/v1/sla/monitor/status"),

    alerts: (limit?: number) =>
      request<AlertEvent[]>(
        `/api/v1/sla/monitor/alerts${limit ? `?limit=${limit}` : ""}`
      ),
  },

  // Scheduler
  scheduler: {
    findWindow: (body: {
      job_duration_minutes?: number;
      providers?: string[];
      preferred_regions?: string[];
      strategy?: "lowest_carbon" | "highest_renewable" | "balanced";
      max_delay_hours?: number;
    }) =>
      request<ScheduleRecommendation>("/api/v1/scheduler/find-window", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    bestNow: (durationMinutes?: number, providers?: string) =>
      request<ScheduleRecommendation>(
        `/api/v1/scheduler/now?duration_minutes=${durationMinutes ?? 30}&providers=${providers ?? "aws,gcp,azure"}`
      ),

    createSchedule: (body: {
      name: string;
      org_id: string;
      job_duration_minutes?: number;
      providers?: string[];
      preferred_regions?: string[];
      strategy?: "lowest_carbon" | "highest_renewable" | "balanced";
      max_delay_hours?: number;
    }) =>
      request<CronSchedule>("/api/v1/scheduler/schedules", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    listSchedules: (orgId: string) =>
      request<CronSchedule[]>(
        `/api/v1/scheduler/schedules?org_id=${orgId}`
      ),

    getSchedule: (id: string) =>
      request<CronSchedule>(`/api/v1/scheduler/schedules/${id}`),

    deleteSchedule: (id: string) =>
      request<{ deleted: string }>(`/api/v1/scheduler/schedules/${id}`, {
        method: "DELETE",
      }),

    nextWindow: (id: string) =>
      request<ScheduleRecommendation>(
        `/api/v1/scheduler/schedules/${id}/next`,
        { method: "POST" }
      ),
  },

  // Carbon zones
  carbonZones: () =>
    request<Array<Record<string, unknown>>>("/api/v1/carbon/zones"),

  // Source health
  sourceHealth: () =>
    request<Record<string, unknown>>("/api/v1/status/sources"),

  // Compliance
  compliance: {
    ingestUsage: (body: UsageIngestionRequest) =>
      request<UsageIngestionResponse>("/api/v1/compliance/usage/ingest", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    calculate: (orgId: string, method: string = "location_based") =>
      request<CalculationResponse>("/api/v1/compliance/calculate", {
        method: "POST",
        body: JSON.stringify({ org_id: orgId, method }),
      }),

    generateReport: (body: {
      org_id: string;
      org_name: string;
      report_name?: string;
    }) =>
      request<ComplianceReport>("/api/v1/compliance/reports/generate", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    listReports: (orgId: string) =>
      request<ComplianceReportSummary[]>(
        `/api/v1/compliance/reports?org_id=${orgId}`
      ),

    getReport: (reportId: string, orgId: string) =>
      request<ComplianceReport>(
        `/api/v1/compliance/reports/${reportId}?org_id=${orgId}`
      ),
  },
};
