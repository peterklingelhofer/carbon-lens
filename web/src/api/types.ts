export interface RegionRecommendation {
  provider: string;
  region: string;
  grid_zone: string;
  carbon_intensity_gco2_kwh: number;
  renewable_percentage: number;
  score: number;
  carbon_savings_vs_worst_pct: number;
}

export interface RouteResponse {
  recommended: RegionRecommendation;
  alternatives: RegionRecommendation[];
  request_id: string;
  timestamp: string;
}

export interface RouteRequest {
  constraints: {
    providers: string[];
    candidate_regions?: string[];
    data_residency?: string[];
    carbon_weight?: number;
    cost_weight?: number;
  };
}

export interface CloudRegion {
  provider: string;
  region: string;
  grid_zone: string;
  location: string;
  latitude: number;
  longitude: number;
}

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
}

export interface EmissionsRecord {
  request_id: string;
  timestamp: string;
  chosen_provider: string;
  chosen_region: string;
  chosen_grid_zone: string;
  chosen_carbon_intensity: number;
  worst_carbon_intensity: number;
  carbon_saved_gco2_kwh: number;
}

export interface CarbonSavingsReport {
  total_requests: number;
  total_carbon_saved_gco2_kwh: number;
  avg_renewable_percentage: number;
  records: EmissionsRecord[];
}

export interface HealthResponse {
  status: string;
  version: string;
  carbon_source: string;
}

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

export interface RegionLookup {
  provider: string;
  region: string;
}

// --- Compliance types ---

export interface UsageIngestionRequest {
  org_id: string;
  provider: string;
  period_start: string;
  period_end: string;
  credentials?: Record<string, string>;
}

export interface UsageIngestionResponse {
  records_ingested: number;
  total_energy_kwh: number;
  providers_covered: string[];
  regions_covered: string[];
}

export interface CalculationResponse {
  calculations_count: number;
  total_emissions_kgco2e: number;
  scope2_kgco2e: number;
  scope3_kgco2e: number;
  data_sources_used: string[];
}

export interface ComplianceReportSummary {
  id: string;
  report_name: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  total_kgco2e: number;
  total_energy_kwh: number;
  carbon_saved_percentage: number;
}

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

export interface GreenSLA {
  id: string;
  org_id: string;
  name: string;
  max_carbon_intensity_gco2_kwh: number;
  min_renewable_percentage: number;
  providers: string[];
  regions: string[];
  check_frequency: SLACheckFrequency;
  alert_channels: string[];
  webhook_url: string;
  created_at: string;
  updated_at: string;
  active: boolean;
}

export interface SLASummary {
  id: string;
  name: string;
  org_id: string;
  status: SLAStatusValue;
  max_carbon_intensity_gco2_kwh: number;
  min_renewable_percentage: number;
  check_frequency: SLACheckFrequency;
  last_checked: string | null;
  active: boolean;
}

export interface BreachedRegion {
  provider: string;
  region: string;
  carbon_intensity_gco2_kwh: number;
  renewable_percentage: number;
}

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

export interface SLAReport {
  id: string;
  sla_id: string;
  org_id: string;
  org_name: string;
  sla_name: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  total_checks: number;
  compliant_checks: number;
  warning_checks: number;
  breached_checks: number;
  compliance_percentage: number;
  avg_carbon_intensity_gco2_kwh: number;
  max_carbon_intensity_gco2_kwh: number;
  avg_renewable_percentage: number;
  min_renewable_percentage: number;
  target_max_carbon: number;
  target_min_renewable: number;
  checks_by_day: Record<string, Record<string, unknown>>;
  worst_regions: Record<string, unknown>[];
  best_regions: Record<string, unknown>[];
  methodology: string;
  data_sources: string[];
  reporting_standard: string;
}

export interface SLAMonitorStatus {
  running: boolean;
  checks_completed: number;
  breaches_detected: number;
  slas_monitored: number;
  recent_alerts: number;
}

export interface AlertEvent {
  id: string;
  sla_id: string;
  sla_name: string;
  channel: string;
  sent_at: string;
  status: SLAStatusValue;
  details: Record<string, unknown>;
  delivery_status: string;
}

// --- Carbon-aware scheduler ---

export type ScheduleStrategy = "lowest_carbon" | "highest_renewable" | "balanced";

export interface TimeSlot {
  start: string;
  end: string;
  provider: string;
  region: string;
  grid_zone: string;
  carbon_intensity_gco2_kwh: number;
  renewable_percentage: number;
  score: number;
}

export interface ScheduleRecommendation {
  id: string;
  recommended: TimeSlot;
  alternatives: TimeSlot[];
  job_duration_minutes: number;
  window_start: string;
  window_end: string;
  strategy: ScheduleStrategy;
  carbon_saved_vs_now_pct: number;
  evaluated_slots: number;
}

export interface CronSchedule {
  id: string;
  name: string;
  org_id: string;
  job_duration_minutes: number;
  providers: string[];
  preferred_regions: string[];
  strategy: ScheduleStrategy;
  max_delay_hours: number;
  created_at: string;
  active: boolean;
}
