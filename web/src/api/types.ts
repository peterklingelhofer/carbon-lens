// These types alias the generated OpenAPI schema in schema.ts
// Run npm run gen:api to refresh it
import type { components } from "./schema";

export type RegionRecommendation = components["schemas"]["RegionRecommendation"];

export type RouteResponse = components["schemas"]["RouteResponse"];

// Hand-written: schema.JobConstraints marks carbon_weight and cost_weight as required,
// but Dashboard.tsx and others omit them to fall back to server defaults
export interface RouteRequest {
  constraints: {
    providers: string[];
    candidate_regions?: string[];
    data_residency?: string[];
    carbon_weight?: number;
    cost_weight?: number;
  };
}

export type CloudRegion = components["schemas"]["CloudRegion"];

// Hand-written: the API returns quality, carried_forward and consumption_intensity_gco2_kwh,
// which aren't in the generated schema yet. Dashboard, CarbonGlobe, RegionSpread, Landing
// and About all read them directly
export interface CarbonIntensity {
  grid_zone: string;
  carbon_intensity_gco2_kwh: number;
  renewable_percentage: number;
  timestamp: string;
  source: string;
  quality?: "live" | "estimated" | "mock";
  grid_load_mw?: number | null;
  // Set by the snapshot builder when a transient upstream gap was bridged with
  // this zone's last live reading (see scripts/build_snapshot.py carry-forward).
  carried_forward?: boolean;
  // Consumption-based intensity (flow-traced across imports/exports), for
  // European zones. Differs from the production-based value above when a region
  // imports notably cleaner or dirtier power than it generates.
  consumption_intensity_gco2_kwh?: number;
  // Estimated marginal emission factor (what an extra kWh would emit). A
  // heuristic from the fuel mix. Measured marginal data isn't available.
  marginal_intensity_gco2_kwh?: number;
  // Live generation breakdown by fuel type in MW (only fuels actually
  // generating). Present for sources with a real fuel mix, absent for
  // heuristic/weather-based estimates.
  power_breakdown_mw?: Record<string, number>;
}

export type CarbonForecast = components["schemas"]["CarbonForecast"];

// Hand-written: no schema counterpart
export interface GridZoneSummary {
  grid_zone: string;
  location: string;
  regions: string[];
}

export type CarbonHistoryPoint = components["schemas"]["CarbonHistoryPoint"];

export type CarbonHistory = components["schemas"]["CarbonHistory"];

export type SitingOption = components["schemas"]["SitingOption"];

export type SitingRecommendation = components["schemas"]["SitingRecommendation"];

export type ZoneShiftability = components["schemas"]["ZoneShiftability"];

export type ShiftabilityRanking = components["schemas"]["ShiftabilityRanking"];

export type BestTime = components["schemas"]["BestTime"];

export type WeatherConditions = components["schemas"]["WeatherConditions"];

export type EmissionsRecord = components["schemas"]["EmissionsRecord"];

export type CarbonSavingsReport = components["schemas"]["CarbonSavingsReport"];

// Hand-written: no schema counterpart
export interface HealthResponse {
  status: string;
  version: string;
  carbon_source: string;
}

// Hand-written: no schema counterpart, this is a websocket message shape
export interface CarbonUpdate {
  type: "carbon_update";
  timestamp: string;
  data: Array<{
    provider: string;
    region: string;
    grid_zone: string;
    carbon_intensity_gco2_kwh: number;
    renewable_percentage: number;
    timestamp: string;
    source: string;
  }>;
}

// Hand-written: no schema counterpart
export interface RegionLookup {
  provider: string;
  region: string;
}

// --- Compliance types ---

export type UsageIngestionRequest = components["schemas"]["UsageIngestionRequest"];

export type UsageIngestionResponse = components["schemas"]["UsageIngestionResponse"];

export type CalculationResponse = components["schemas"]["CalculationResponse"];

export type ComplianceReportSummary = components["schemas"]["ComplianceReportSummary"];

// Hand-written: schema marks data_sources and data_quality_summary optional,
// but Compliance.tsx reads both without a null check
export interface ComplianceReport {
  id: string;
  org_id: string;
  org_name: string;
  report_name: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  scope2_location_kgco2e: number;
  scope2_location_by_provider: Record<string, number>;
  scope2_location_by_region: Record<string, number>;
  scope2_market_kgco2e: number;
  scope2_market_by_provider: Record<string, number>;
  scope2_market_by_region: Record<string, number>;
  scope3_cat1_kgco2e: number;
  scope3_cat1_by_provider: Record<string, number>;
  scope3_cat1_by_service: Record<string, number>;
  total_kgco2e: number;
  total_energy_kwh: number;
  avg_renewable_percentage: number;
  total_cloud_regions_used: number;
  total_providers_used: number;
  carbon_saved_kgco2e: number;
  carbon_saved_percentage: number;
  methodology: string;
  data_sources: string[];
  data_quality_summary: Record<string, number>;
  reporting_standard: string;
  calculation_count: number;
  eu_taxonomy_eligible: boolean;
  eu_taxonomy_aligned: boolean;
  taxonomy_notes: string;
}

// --- Green SLA monitoring ---

export type SLAStatusValue = "compliant" | "warning" | "breached" | "unknown";
export type SLACheckFrequency = "hourly" | "daily" | "weekly";

export type GreenSLA = components["schemas"]["GreenSLA"];

export type SLASummary = components["schemas"]["SLASummary"];

// Hand-written: no schema counterpart, SLACheck's breached_regions is an
// untyped object list in the generated schema
export interface BreachedRegion {
  provider: string;
  region: string;
  carbon_intensity_gco2_kwh: number;
  renewable_percentage: number;
}

// Hand-written: schema types breached_regions as an optional Record<string, unknown>[],
// but SLAMonitor.tsx reads it as a required BreachedRegion[]
export interface SLACheck {
  id: string;
  sla_id: string;
  checked_at: string;
  status: SLAStatusValue;
  avg_carbon_intensity_gco2_kwh: number;
  max_carbon_intensity_gco2_kwh: number;
  min_carbon_intensity_gco2_kwh: number;
  avg_renewable_percentage: number;
  regions_checked: number;
  regions_compliant: number;
  regions_breached: number;
  breached_regions: BreachedRegion[];
  target_max_carbon: number;
  target_min_renewable: number;
}

export type SLAReport = components["schemas"]["SLAReport"];

// Hand-written: no schema counterpart
export interface SLAMonitorStatus {
  running: boolean;
  checks_completed: number;
  breaches_detected: number;
  slas_monitored: number;
  recent_alerts: number;
}

// --- Carbon-aware scheduler ---

export type ScheduleStrategy = "lowest_carbon" | "highest_renewable" | "balanced";

export type TimeSlot = components["schemas"]["TimeSlot"];

export type ScheduleRecommendation = components["schemas"]["ScheduleRecommendation"];
