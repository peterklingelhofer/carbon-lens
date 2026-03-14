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

export interface Organization {
  id: string;
  name: string;
  slug: string;
  tier: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
}

export interface PlanInfo {
  tier: string;
  name: string;
  daily_limit: number;
  price_cents: number;
  features: string[];
}

export interface BillingStatus {
  api_key_id: string | null;
  tier: string;
  plan: PlanInfo;
  today_usage: number;
  daily_limit: number;
  remaining: number;
}

export interface RegionLookup {
  provider: string;
  region: string;
}
