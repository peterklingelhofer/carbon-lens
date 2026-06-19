import { useQuery } from "@tanstack/react-query";
import type { BestTime, CarbonIntensity, CloudRegion } from "./types";

// Static carbon snapshot published to a CDN by the `snapshot` GitHub Action.
// When VITE_SNAPSHOT_URL is set, the dashboard reads real data from here
// instead of calling the live API, so viewer traffic never hits upstream
// provider quotas. Falls back to the live API when the URL is unset.

// The precomputed run-now/wait decision per region, baked into the snapshot by the
// builder so the frontend (and SDK) read it straight from the CDN -- no live API call,
// no cold start. Same shape and logic as the API's /carbon/signal endpoint.
export interface CarbonSignal {
  provider: string;
  region: string;
  grid_zone: string;
  intensity_gco2_kwh: number;
  state: "green" | "yellow" | "red";
  advice: "run_now" | "wait_for_cleaner";
  cleaner_window_in_hours: number | null;
  cleaner_window_intensity_gco2_kwh: number | null;
  marginal_intensity_gco2_kwh: number | null;
  marginal_note: string | null;
  marginal_basis: string;
  clean_surplus: boolean;
  surplus_window_in_hours: number | null;
}

// A compact 24h forecast curve baked into the snapshot (point 0 = current reading).
// Each point is {t: timestamp, c: gCO2/kWh} -- only what the sparkline needs.
export interface CarbonSnapshotForecast {
  grid_zone: string;
  provider: string;
  region: string;
  method: string;
  generated_at: string | null;
  clean_surplus_hours: number[];
  points: { t: string; c: number }[];
}

export interface CarbonSnapshot {
  generated_at: string;
  regions: CloudRegion[];
  intensities: Record<string, CarbonIntensity>;
  // Optional: older snapshots predate precomputed signals/forecasts, so may be absent.
  signals?: Record<string, CarbonSignal>;
  forecasts?: Record<string, CarbonSnapshotForecast>;
  best_time?: Record<string, BestTime>;
  summary: {
    live_zones: number;
    estimated_zones: number;
    mock_zones_dropped: number;
    carried_forward?: number;
    regions_published: number;
    signals_published?: number;
    forecasts_published?: number;
    best_time_published?: number;
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

// The precomputed signal for one region, read from the cached snapshot (no extra
// fetch). Undefined when snapshots are disabled or this region has no signal yet.
export function useSignal(provider: string, region: string): CarbonSignal | undefined {
  const { data } = useSnapshot();
  return data?.signals?.[`${provider}/${region}`];
}

// The precomputed 24h forecast for one region from the cached snapshot (no extra
// fetch). Undefined when snapshots are disabled or this region has no forecast yet.
export function useForecastSnapshot(
  provider: string,
  region: string,
): CarbonSnapshotForecast | undefined {
  const { data } = useSnapshot();
  return data?.forecasts?.[`${provider}/${region}`];
}

// The precomputed greenest-hour BestTime for one region from the cached snapshot (no
// extra fetch). Undefined when snapshots are disabled or this region has none yet.
export function useBestTimeSnapshot(provider: string, region: string): BestTime | undefined {
  const { data } = useSnapshot();
  return data?.best_time?.[`${provider}/${region}`];
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
