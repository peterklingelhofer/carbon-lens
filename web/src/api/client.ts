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
  HealthResponse,
  Organization,
  PlanInfo,
  ProofJob,
  RegionLookup,
  RouteRequest,
  RouteResponse,
  SimulateResponse,
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
  },

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
