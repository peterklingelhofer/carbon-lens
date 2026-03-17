import type {
  BillingStatus,
  BrokerStats,
  CalculationResponse,
  CarbonIntensity,
  CarbonPolicy,
  CarbonSavingsReport,
  CloudRegion,
  ComplianceReport,
  ComplianceReportSummary,
  ComputeOption,
  ExecuteResponse,
  HealthResponse,
  JobEvent,
  JobResult,
  Organization,
  PlanInfo,
  PollerStatus,
  ProofJob,
  RegionLookup,
  RouteRequest,
  RouteResponse,
  SimulateResponse,
  SpotPriceQuote,
  UsageIngestionRequest,
  UsageIngestionResponse,
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

  // ZK Broker
  zk: {
    availableJobs: (network?: string) =>
      request<ProofJob[]>(
        `/api/v1/zk/jobs/available${network ? `?network=${network}` : ""}`
      ),

    simulate: (body: {
      network?: string;
      bounty_usd?: number;
      circuit_size?: number;
      min_vram_gb?: number;
      max_carbon_intensity?: number | null;
    }) =>
      request<SimulateResponse>("/api/v1/zk/simulate", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    stats: () => request<BrokerStats>("/api/v1/zk/stats"),

    policy: () => request<CarbonPolicy>("/api/v1/zk/policy"),

    updatePolicy: (policy: CarbonPolicy) =>
      request<CarbonPolicy>("/api/v1/zk/policy", {
        method: "PUT",
        body: JSON.stringify(policy),
      }),

    computeOptions: (minVram?: number) =>
      request<ComputeOption[]>(
        `/api/v1/zk/compute/available${minVram ? `?min_vram_gb=${minVram}` : ""}`
      ),

    execute: (body: { job: ProofJob }) =>
      request<ExecuteResponse>("/api/v1/zk/jobs/execute", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    jobStatus: (jobId: string) =>
      request<JobResult | null>(`/api/v1/zk/jobs/${jobId}/status`),

    cancelJob: (jobId: string) =>
      request<{ job_id: string; cancelled: boolean }>(
        `/api/v1/zk/jobs/${jobId}/cancel`,
        { method: "POST" }
      ),

    activeJobs: () =>
      request<{ count: number; jobs: Record<string, unknown> }>(
        "/api/v1/zk/jobs/active"
      ),

    spotPrices: () =>
      request<SpotPriceQuote[]>("/api/v1/zk/compute/spot-prices"),

    metrics: () => request<Record<string, unknown>>("/api/v1/zk/metrics"),

    events: (limit?: number) =>
      request<JobEvent[]>(
        `/api/v1/zk/events${limit ? `?limit=${limit}` : ""}`
      ),

    proverNetworks: () =>
      request<
        Array<{
          network: string;
          proof_system: string;
          image: string;
          gpu_required: boolean;
          min_vram_gb: number;
        }>
      >("/api/v1/zk/runtime/networks"),

    pollerStatus: () =>
      request<PollerStatus>("/api/v1/zk/poller/status"),

    startPoller: () =>
      request<PollerStatus>("/api/v1/zk/poller/start", { method: "POST" }),

    stopPoller: () =>
      request<PollerStatus>("/api/v1/zk/poller/stop", { method: "POST" }),
  },

  // SLA Monitoring
  sla: {
    list: (orgId: string) =>
      request<Array<Record<string, unknown>>>(`/api/v1/sla/list?org_id=${orgId}`),

    create: (body: {
      org_id: string;
      name: string;
      max_carbon_intensity_gco2_kwh: number;
      min_renewable_percentage: number;
      providers?: string[];
    }) =>
      request<Record<string, unknown>>("/api/v1/sla/create", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    get: (slaId: string) =>
      request<Record<string, unknown>>(`/api/v1/sla/${slaId}`),

    check: (slaId: string) =>
      request<Record<string, unknown>>(`/api/v1/sla/${slaId}/check`, {
        method: "POST",
      }),

    status: (slaId: string) =>
      request<Record<string, unknown> | null>(`/api/v1/sla/${slaId}/status`),

    checks: (slaId: string, limit?: number) =>
      request<Array<Record<string, unknown>>>(
        `/api/v1/sla/${slaId}/checks${limit ? `?limit=${limit}` : ""}`
      ),

    generateReport: (slaId: string, body: { org_name: string; period_days?: number }) =>
      request<Record<string, unknown>>(`/api/v1/sla/${slaId}/report`, {
        method: "POST",
        body: JSON.stringify(body),
      }),

    reports: (slaId: string) =>
      request<Array<Record<string, unknown>>>(`/api/v1/sla/${slaId}/reports`),

    startMonitor: (orgId: string) =>
      request<Record<string, unknown>>(`/api/v1/sla/monitor/start?org_id=${orgId}`, {
        method: "POST",
      }),

    stopMonitor: () =>
      request<Record<string, unknown>>("/api/v1/sla/monitor/stop", {
        method: "POST",
      }),

    monitorStatus: () =>
      request<Record<string, unknown>>("/api/v1/sla/monitor/status"),

    alerts: (limit?: number) =>
      request<Array<Record<string, unknown>>>(
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
      request<Record<string, unknown>>("/api/v1/scheduler/find-window", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    bestNow: (durationMinutes?: number, providers?: string) =>
      request<Record<string, unknown>>(
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
      request<Record<string, unknown>>("/api/v1/scheduler/schedules", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    listSchedules: (orgId: string) =>
      request<Array<Record<string, unknown>>>(
        `/api/v1/scheduler/schedules?org_id=${orgId}`
      ),

    getSchedule: (id: string) =>
      request<Record<string, unknown>>(`/api/v1/scheduler/schedules/${id}`),

    deleteSchedule: (id: string) =>
      request<{ deleted: string }>(`/api/v1/scheduler/schedules/${id}`, {
        method: "DELETE",
      }),

    nextWindow: (id: string) =>
      request<Record<string, unknown>>(
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
