import { useQuery } from "@tanstack/react-query";
import { dataBranchUrl } from "./snapshot";
import type { SitingOption, SitingRecommendation } from "./types";

// The "state of clean compute" report, published to the data branch every 30 min by
// the snapshot cron (scripts/build_clean_compute_report.py). We read it from the same
// CDN as the snapshot -- no API call, fixed cost.

export interface ShiftableGrid {
  grid_zone: string;
  location: string;
  shift_savings_pct: number;
  cleanest_hour_utc: number;
  samples: number;
}

export interface GreenRegion {
  provider: string;
  region: string;
  location: string;
  typical_gco2_kwh: number;
  // Within-window trend: negative = getting cleaner, positive = dirtier. May be absent.
  trend_pct?: number | null;
}

export interface CleanComputeReport {
  generated_at: string;
  days_analyzed: number;
  most_shiftable: ShiftableGrid[];
  greenest_regions: GreenRegion[];
  forecast_calibration?: ForecastCalibration | null;
}

const HOURS_PER_YEAR = 8760;

// Build the same SitingRecommendation the /carbon/siting endpoint returns, but from the
// published greenest-regions report, so the siting picker runs fully static off the CDN
// report instead of waking the API.
export function sitingFromGreenest(
  greenest: GreenRegion[],
  providers: string[],
  watts: number,
  daysAnalyzed: number,
): SitingRecommendation {
  const powerKw = watts ? watts / 1000 : null;
  const annualKg = (typical: number) =>
    powerKw != null ? Math.round(((typical * powerKw * HOURS_PER_YEAR) / 1000) * 10) / 10 : null;

  const options: SitingOption[] = greenest
    .filter((r) => providers.includes(r.provider))
    .map((r) => ({
      provider: r.provider,
      region: r.region,
      grid_zone: "",
      location: r.location,
      typical_gco2_kwh: r.typical_gco2_kwh,
      basis: "history",
      annual_kg: annualKg(r.typical_gco2_kwh),
    }))
    .sort((a, b) => a.typical_gco2_kwh - b.typical_gco2_kwh);

  let saved: number | null = null;
  if (powerKw != null && options.length > 1) {
    const delta = options[options.length - 1].typical_gco2_kwh - options[0].typical_gco2_kwh;
    saved = Math.round(((delta * powerKw * HOURS_PER_YEAR) / 1000) * 10) / 10;
  }
  return {
    recommended: options[0],
    options,
    annual_kg_saved_vs_worst: saved,
    power_watts: watts || null,
    days_analyzed: daysAnalyzed,
  };
}

// Forecast accuracy from a deployment's impact ledger: how submit-time predicted
// reductions compared to the run-time re-measured actuals. Absent unless published.
export interface ForecastCalibration {
  samples: number;
  mean_predicted_gco2_kwh: number;
  mean_actual_gco2_kwh: number;
  // actual / predicted: <1 over-promised, >1 under-promised, ~1 well-calibrated.
  calibration_ratio: number;
  mean_abs_error_gco2_kwh: number;
  days: number;
}

// The report sits next to snapshot.json on the data branch.
export const REPORT_URL = dataBranchUrl("clean_compute_report.json");

export function useCleanComputeReport() {
  return useQuery({
    queryKey: ["clean-compute-report"],
    queryFn: async (): Promise<CleanComputeReport> => {
      const res = await fetch(REPORT_URL);
      if (!res.ok) throw new Error(`report fetch failed: ${res.status}`);
      return res.json();
    },
    enabled: !!REPORT_URL,
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
}

export interface ReportHistoryDay {
  date: string;
  greenest_mean_gco2_kwh: number | null;
  top_shiftability_pct: number | null;
}

export interface CleanComputeHistory {
  days: ReportHistoryDay[];
}

export const HISTORY_URL = dataBranchUrl("clean_compute_history.json");

export function useCleanComputeHistory() {
  return useQuery({
    queryKey: ["clean-compute-history"],
    queryFn: async (): Promise<CleanComputeHistory> => {
      const res = await fetch(HISTORY_URL);
      if (!res.ok) throw new Error(`history fetch failed: ${res.status}`);
      return res.json();
    },
    enabled: !!HISTORY_URL,
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
}
