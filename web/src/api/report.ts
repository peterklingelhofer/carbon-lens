import { useQuery } from "@tanstack/react-query";

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
}

export interface CleanComputeReport {
  generated_at: string;
  days_analyzed: number;
  most_shiftable: ShiftableGrid[];
  greenest_regions: GreenRegion[];
}

const SNAPSHOT_URL = import.meta.env.VITE_SNAPSHOT_URL || "";
// The report sits next to snapshot.json on the data branch.
export const REPORT_URL = SNAPSHOT_URL
  ? SNAPSHOT_URL.replace("snapshot.json", "clean_compute_report.json")
  : "";

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
