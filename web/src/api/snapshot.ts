import { useQuery } from "@tanstack/react-query";
import type { BestTime, CarbonIntensity, CloudRegion, GridZoneSummary } from "./types";

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

// Precomputed current weather drivers per region (Open-Meteo), baked into the snapshot.
export interface SnapshotWeather {
  wind_speed_kmh: number;
  solar_irradiance_w_m2: number;
  source?: string;
}

export interface CarbonSnapshot {
  generated_at: string;
  regions: CloudRegion[];
  intensities: Record<string, CarbonIntensity>;
  // Optional: older snapshots predate precomputed signals/forecasts, so may be absent.
  signals?: Record<string, CarbonSignal>;
  forecasts?: Record<string, CarbonSnapshotForecast>;
  best_time?: Record<string, BestTime>;
  weather?: Record<string, SnapshotWeather>;
  summary: {
    live_zones: number;
    estimated_zones: number;
    mock_zones_dropped: number;
    carried_forward?: number;
    regions_published: number;
    signals_published?: number;
    forecasts_published?: number;
    best_time_published?: number;
    weather_published?: number;
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

// The precomputed weather drivers for one region from the cached snapshot (no extra
// fetch). Undefined when snapshots are disabled or this region has no weather yet.
export function useWeatherSnapshot(provider: string, region: string): SnapshotWeather | undefined {
  const { data } = useSnapshot();
  return data?.weather?.[`${provider}/${region}`];
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

// One compact rolling-history point: timestamp, carbon (gCO2/kWh), renewable %.
export interface HistoryArchivePoint {
  t: string;
  c: number;
  r: number;
}

// The rolling history archive sits next to snapshot.json on the data branch.
export const HISTORY_ARCHIVE_URL = SNAPSHOT_URL
  ? SNAPSHOT_URL.replace("snapshot.json", "history.json")
  : "";

// One region's rolling carbon history from the published archive (history.json on the
// CDN) -- the same data /carbon/history returns, but static. The whole archive is a
// single cached fetch shared across every region the viewer opens. Undefined when the
// archive is unavailable (so callers can fall back to the live API).
export function useRegionHistoryArchive(
  provider: string,
  region: string,
): HistoryArchivePoint[] | undefined {
  const { data } = useQuery({
    queryKey: ["history-archive"],
    queryFn: async (): Promise<{ series: Record<string, HistoryArchivePoint[]> }> => {
      const res = await fetch(HISTORY_ARCHIVE_URL);
      if (!res.ok) throw new Error(`history archive fetch failed: ${res.status}`);
      return res.json();
    },
    enabled: !!HISTORY_ARCHIVE_URL,
    refetchInterval: 5 * 60 * 1000,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
  return data?.series?.[`${provider}/${region}`];
}

// All covered grid zones, each with the cloud regions on it -- the static equivalent of
// GET /carbon/zones, derived from the snapshot's region list. Empty without a snapshot.
export function gridZonesFromSnapshot(snapshot: CarbonSnapshot | undefined): GridZoneSummary[] {
  if (!snapshot) return [];
  const byZone = new Map<string, GridZoneSummary>();
  for (const r of snapshot.regions) {
    const summary = byZone.get(r.grid_zone);
    if (summary) summary.regions.push(`${r.provider}/${r.region}`);
    else
      byZone.set(r.grid_zone, {
        grid_zone: r.grid_zone,
        location: r.location,
        regions: [`${r.provider}/${r.region}`],
      });
  }
  return [...byZone.values()].sort((a, b) => a.grid_zone.localeCompare(b.grid_zone));
}

// Carbon intensity for a grid zone, from any snapshot region on that zone -- the static
// equivalent of GET /carbon/{zone}. Undefined when the zone isn't in the snapshot.
export function zoneIntensityFromSnapshot(
  snapshot: CarbonSnapshot | undefined,
  zone: string,
): CarbonIntensity | undefined {
  if (!snapshot) return undefined;
  for (const ci of Object.values(snapshot.intensities)) {
    if (ci.grid_zone === zone) return ci;
  }
  return undefined;
}

export interface GreenestRegion {
  provider: string;
  region: string;
  carbon_intensity_gco2_kwh: number;
  renewable_percentage: number;
}

// The greenest region (lowest current intensity) among the given providers, derived from
// the snapshot -- the static equivalent of carbon-weighted /route. Undefined without a
// snapshot or when no provider matches.
export function greenestRegion(
  snapshot: CarbonSnapshot | undefined,
  providers: string[],
): GreenestRegion | undefined {
  if (!snapshot) return undefined;
  let best: GreenestRegion | undefined;
  for (const [key, ci] of Object.entries(snapshot.intensities)) {
    const slash = key.indexOf("/");
    const provider = key.slice(0, slash);
    if (!providers.includes(provider)) continue;
    if (!best || ci.carbon_intensity_gco2_kwh < best.carbon_intensity_gco2_kwh) {
      best = {
        provider,
        region: key.slice(slash + 1),
        carbon_intensity_gco2_kwh: ci.carbon_intensity_gco2_kwh,
        renewable_percentage: ci.renewable_percentage,
      };
    }
  }
  return best;
}
