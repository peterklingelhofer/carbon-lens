import { useQuery } from "@tanstack/react-query";
import type { CarbonIntensity, CloudRegion } from "./types";

// Static carbon snapshot published to a CDN by the `snapshot` GitHub Action.
// When VITE_SNAPSHOT_URL is set, the dashboard reads real data from here
// instead of calling the live API, so viewer traffic never hits upstream
// provider quotas. Falls back to the live API when the URL is unset.

export interface CarbonSnapshot {
  generated_at: string;
  regions: CloudRegion[];
  intensities: Record<string, CarbonIntensity>;
  summary: {
    live_zones: number;
    estimated_zones: number;
    mock_zones_dropped: number;
    carried_forward?: number;
    regions_published: number;
    degraded: string[];
  };
}

const SNAPSHOT_URL = import.meta.env.VITE_SNAPSHOT_URL || "";

export const snapshotEnabled = !!SNAPSHOT_URL;

// Derive data quality from a provider's source string. The snapshot builder
// stamps `quality` server-side, but the live API does not - so the live-API
// fallback (local dev without a snapshot) derives it here. Mirrors the Python
// `_quality` in scripts/build_snapshot.py.
export function qualityFromSource(source: string): "live" | "estimated" | "mock" {
  if (source.endsWith("_heuristic") || source === "open_meteo") return "estimated";
  if (source === "mock" || source === "electricity_maps_error") return "mock";
  return "live";
}

export function useSnapshot() {
  return useQuery({
    queryKey: ["snapshot"],
    queryFn: async (): Promise<CarbonSnapshot> => {
      const res = await fetch(SNAPSHOT_URL);
      if (!res.ok) throw new Error(`snapshot fetch failed: ${res.status}`);
      return res.json();
    },
    enabled: snapshotEnabled,
    // CDN serves ~5-min-fresh data; refetch on the same cadence.
    refetchInterval: 5 * 60 * 1000,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
