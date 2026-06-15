import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { type CarbonSnapshot, snapshotEnabled, useSnapshot } from "../api/snapshot";
import type { CarbonIntensity, CarbonUpdate, CloudRegion } from "../api/types";
import { CustomZoneLookup } from "../components/CustomZoneLookup";
import { InfoTip } from "../components/InfoTip";
import { DATA_QUALITY_TIP, DATA_QUALITY_TIP_RICH } from "../copy";
import { timeAgo } from "../lib/format";
import { card, providerChip, section as sectionFn } from "../styles";

const section = sectionFn(1100);

function formatLoad(mw?: number | null): string | null {
  if (mw == null) return null;
  return mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw)} MW`;
}

function intensityColor(val: number): string {
  if (val <= 50) return "var(--green-500)";
  if (val <= 150) return "var(--green-400)";
  if (val <= 300) return "var(--amber)";
  if (val <= 500) return "var(--orange-400)";
  return "var(--red-400)";
}

function QualityTag({ quality }: { quality?: CarbonIntensity["quality"] }) {
  if (quality !== "estimated") return null;
  return (
    <span
      title={DATA_QUALITY_TIP}
      style={{
        marginLeft: 6,
        padding: "0 6px",
        borderRadius: 4,
        fontSize: "0.65rem",
        fontWeight: 600,
        color: "var(--amber)",
        border: "1px solid var(--amber)",
        verticalAlign: "middle",
      }}
    >
      est.
    </span>
  );
}

// Surfaces data freshness: a "last live reading" badge when the snapshot
// bridged a transient upstream gap with this zone's last live reading,
// otherwise just the reading's age when it's noticeably stale. Keeps fresh rows
// uncluttered.
function FreshnessTag({ intensity }: { intensity: CarbonIntensity }) {
  const ageMs = Date.now() - new Date(intensity.timestamp).getTime();
  if (intensity.carried_forward) {
    return (
      <span
        title={`Last live reading from ${timeAgo(intensity.timestamp)} - its upstream feed was briefly unavailable, so the snapshot kept the real value rather than dropping to an estimate.`}
        style={{
          display: "block",
          fontSize: "0.7rem",
          color: "var(--amber)",
        }}
      >
        last live reading · {timeAgo(intensity.timestamp)}
      </span>
    );
  }
  if (ageMs > 90 * 60 * 1000) {
    return (
      <span style={{ display: "block", fontSize: "0.7rem", color: "var(--gray-400)" }}>
        {timeAgo(intensity.timestamp)}
      </span>
    );
  }
  return null;
}

function SnapshotBanner({ snapshot }: { snapshot: CarbonSnapshot }) {
  const { live_zones, estimated_zones } = snapshot.summary;
  return (
    <p
      style={{
        color: "var(--gray-500)",
        marginBottom: "2rem",
        fontSize: "0.9rem",
      }}
    >
      <strong style={{ color: "var(--green-text)" }}>{live_zones} grid zones live</strong> from real
      grid-operator APIs
      <InfoTip label="live vs estimated" text={DATA_QUALITY_TIP_RICH} />
      {estimated_zones > 0 && (
        <>
          {" "}
          · {estimated_zones} estimated (intermittent upstream, tagged{" "}
          <span style={{ color: "var(--amber)", fontWeight: 600 }}>est.</span>)
        </>
      )}{" "}
      · updated {timeAgo(snapshot.generated_at)}
    </p>
  );
}

function IntensityBar({ value, max = 800 }: { value: number; max?: number }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div
      style={{
        height: 8,
        borderRadius: 4,
        background: "var(--gray-100)",
        overflow: "hidden",
        width: "100%",
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${pct}%`,
          borderRadius: 4,
          background: intensityColor(value),
          transition: "width 0.3s",
        }}
      />
    </div>
  );
}

function RegionRow({ region, intensity }: { region: CloudRegion; intensity?: CarbonIntensity }) {
  return (
    <tr style={{ borderBottom: "1px solid var(--gray-100)" }}>
      <td style={{ padding: "0.5rem" }}>
        <span
          style={{
            textTransform: "uppercase",
            fontSize: "0.8rem",
            ...providerChip(region.provider),
          }}
        >
          {region.provider}
        </span>
      </td>
      <td
        style={{
          padding: "0.5rem",
          fontFamily: "var(--mono)",
          fontSize: "0.85rem",
        }}
      >
        {region.region}
      </td>
      <td style={{ padding: "0.5rem", fontSize: "0.85rem" }}>{region.grid_zone}</td>
      <td style={{ padding: "0.5rem", fontSize: "0.85rem" }}>{region.location}</td>
      <td style={{ padding: "0.5rem", width: 120 }}>
        {intensity ? (
          <div>
            <IntensityBar value={intensity.carbon_intensity_gco2_kwh} />
            <span style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>
              {intensity.carbon_intensity_gco2_kwh} gCO₂/kWh
              <QualityTag quality={intensity.quality} />
            </span>
            {intensity.consumption_intensity_gco2_kwh != null && (
              <span style={{ display: "block", fontSize: "0.7rem", color: "var(--gray-400)" }}>
                consumed ~{intensity.consumption_intensity_gco2_kwh} gCO₂
                <InfoTip
                  label="consumption-based intensity"
                  text="Flow-traced across the European grid: what this region actually consumes after imports and exports, versus what it generates locally (the figure above). They diverge when a region imports notably cleaner or dirtier power than it produces."
                />
              </span>
            )}
            {intensity.marginal_intensity_gco2_kwh != null && (
              <span style={{ display: "block", fontSize: "0.7rem", color: "var(--gray-400)" }}>
                marginal ~{intensity.marginal_intensity_gco2_kwh} gCO₂
                <InfoTip
                  label="marginal intensity"
                  text="Estimated emissions of an extra kWh of demand right now, set by the price-setting generator (usually the flexible gas peaker). That's what actually changes when you shift load, not the average. A heuristic from the fuel mix, not measured marginal data."
                />
              </span>
            )}
            {formatLoad(intensity.grid_load_mw) && (
              <span
                style={{
                  display: "block",
                  fontSize: "0.7rem",
                  color: "var(--gray-400)",
                }}
                title="Total load for the whole balancing authority (all consumers, not datacenter-specific)"
              >
                grid load {formatLoad(intensity.grid_load_mw)}
              </span>
            )}
            <FreshnessTag intensity={intensity} />
          </div>
        ) : (
          <span style={{ color: "var(--gray-400)", fontSize: "0.8rem" }}>loading...</span>
        )}
      </td>
      <td style={{ padding: "0.5rem", textAlign: "center" }}>
        {intensity ? (
          <span
            style={{
              fontWeight: 600,
              color: intensity.renewable_percentage >= 70 ? "var(--green-text)" : "var(--gray-600)",
            }}
          >
            {intensity.renewable_percentage}%
          </span>
        ) : (
          "..."
        )}
      </td>
    </tr>
  );
}

type SortKey = "provider" | "region" | "grid_zone" | "location" | "intensity" | "renewable";

const COLUMNS: {
  key: SortKey;
  label: string;
  align: "left" | "center";
  info?: string;
}[] = [
  { key: "provider", label: "Provider", align: "left" },
  { key: "region", label: "Region", align: "left" },
  {
    key: "grid_zone",
    label: "Grid Zone",
    align: "left",
    info: "The electricity grid (balancing authority) that powers this cloud region - e.g. PJM for US-East, CAISO for California.",
  },
  { key: "location", label: "Location", align: "left" },
  {
    key: "intensity",
    label: "Carbon Intensity",
    align: "left",
    info: "Carbon emitted per unit of electricity, in gCO₂/kWh (grams of CO₂ per kilowatt-hour). Lower is greener. This captures ALL low-carbon sources - including nuclear - so it's the most accurate 'how clean' measure, which is why it's the default sort.",
  },
  {
    key: "renewable",
    label: "Renewable %",
    align: "center",
    info: "Share of the grid's electricity from renewables - wind, solar, hydro - right now. Important: this EXCLUDES nuclear, so renewable % won't always track carbon intensity. A nuclear-heavy grid like France can be very low-carbon yet show a low renewable %, and a high-renewable grid can still be dirty if the rest is coal. For the true 'cleanest' ranking, sort by Carbon Intensity (lower = greener).",
  },
];

// Text columns sort alphabetically; numeric columns (intensity, renewable) sort
// by value. Rows missing intensity data sort last in both directions.
function sortRegions(
  rows: CloudRegion[],
  intensities: Record<string, CarbonIntensity>,
  key: SortKey,
  dir: "asc" | "desc",
): CloudRegion[] {
  const numeric = key === "intensity" || key === "renewable";
  const value = (r: CloudRegion): string | number | undefined => {
    const i = intensities[`${r.provider}/${r.region}`];
    if (key === "intensity") return i?.carbon_intensity_gco2_kwh;
    if (key === "renewable") return i?.renewable_percentage;
    return r[key as "provider" | "region" | "grid_zone" | "location"];
  };
  return [...rows].sort((a, b) => {
    const va = value(a);
    const vb = value(b);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    const cmp = numeric ? (va as number) - (vb as number) : String(va).localeCompare(String(vb));
    return dir === "asc" ? cmp : -cmp;
  });
}

export function Dashboard() {
  const [provider, setProvider] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  // Default to carbon intensity ascending - lowest gCO₂/kWh first is the rigorous
  // "greenest" (counts nuclear/hydro), unlike renewable % which excludes nuclear.
  const [sortKey, setSortKey] = useState<SortKey | null>("intensity");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const { data: snapshot } = useSnapshot();
  const usingSnapshot = !!snapshot;

  const {
    data: apiRegions,
    isLoading: apiRegionsLoading,
    isError: apiRegionsError,
  } = useQuery({
    queryKey: ["regions", provider],
    queryFn: () => api.regions(provider || undefined),
    enabled: !usingSnapshot,
  });

  const regions = usingSnapshot
    ? provider
      ? snapshot.regions.filter((r) => r.provider === provider)
      : snapshot.regions
    : apiRegions;
  const regionsLoading = usingSnapshot ? false : apiRegionsLoading;

  const { data: savings } = useQuery({
    queryKey: ["savings"],
    queryFn: () => api.savings(),
  });

  const queryClient = useQueryClient();
  const routeSample = useMutation({
    mutationFn: () =>
      api.route({
        constraints: { providers: ["aws", "gcp", "azure"], carbon_weight: 1.0 },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["savings"] }),
  });

  // Fetch intensities for ALL regions (in snapshot mode they're already present),
  // sort the FULL set, THEN slice to 20 - otherwise "greenest" would only sort the
  // first 20 as-fetched, showing the wrong regions.
  const allRegions = regions ?? [];
  const apiIntensities = useRegionIntensities(usingSnapshot ? [] : allRegions);
  const intensities = usingSnapshot ? snapshot.intensities : apiIntensities;
  const q = search.trim().toLowerCase();
  const filteredRegions = q
    ? allRegions.filter((r) =>
        `${r.provider} ${r.region} ${r.grid_zone} ${r.location}`.toLowerCase().includes(q),
      )
    : allRegions;
  const sortedRegions = sortKey
    ? sortRegions(filteredRegions, intensities, sortKey, sortDir)
    : filteredRegions;
  const displayRegions = sortedRegions.slice(0, 20);

  return (
    <div style={section}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "1rem",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: "0.5rem",
        }}
      >
        <h1 style={{ margin: 0 }}>Grid Data</h1>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <button
            type="button"
            onClick={() => routeSample.mutate()}
            disabled={routeSample.isPending}
            style={{
              padding: "0.55rem 1.25rem",
              borderRadius: 8,
              border: "none",
              background: "var(--btn-green)",
              color: "white",
              fontWeight: 600,
              fontSize: "0.85rem",
              cursor: routeSample.isPending ? "wait" : "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {routeSample.isPending ? "Finding greenest region…" : "Route a sample workload"}
          </button>
          <InfoTip
            label="Route a sample workload"
            text="Asks the API for the greenest region right now, using a sample carbon-first setting, and shows what it recommends. Nothing is deployed or run - it's the recommendation you'd act on yourself (e.g. from a deploy script or a scheduler that re-checks before each run)."
          />
        </span>
      </div>
      {usingSnapshot ? (
        <SnapshotBanner snapshot={snapshot} />
      ) : (
        <p
          style={{
            color: "var(--gray-500)",
            marginBottom: routeSample.data ? "0.75rem" : "2rem",
          }}
        >
          Live carbon intensity data powering the API. 11 cascading sources
          <InfoTip
            label="cascading sources"
            text="The API tries data sources in priority order and uses the first that covers a zone - a real grid-operator feed where one exists, then a regional heuristic or weather-based estimate, falling back to labelled sample data. So coverage is broad and every reading is tagged with where it came from."
          />{" "}
          (6 live integrations), 75+ cloud regions.
        </p>
      )}
      {routeSample.data && (
        <p
          style={{
            color: "var(--gray-600)",
            fontSize: "0.85rem",
            marginBottom: "2rem",
          }}
        >
          Recommended:{" "}
          <strong style={{ textTransform: "uppercase" }}>
            {routeSample.data.recommended.provider}
          </strong>{" "}
          <code>{routeSample.data.recommended.region}</code> -{" "}
          {routeSample.data.recommended.carbon_intensity_gco2_kwh} gCO₂/kWh,{" "}
          {routeSample.data.recommended.renewable_percentage}% renewable.
        </p>
      )}

      {/* Stats cards */}
      {savings && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
            marginBottom: "2rem",
          }}
        >
          <div style={card}>
            <div
              style={{
                fontSize: "0.8rem",
                color: "var(--gray-500)",
                display: "flex",
                alignItems: "center",
              }}
            >
              Recommendations made
              <InfoTip
                label="Recommendations made"
                text="How many routing recommendations this demo server has produced - each click of 'Route a sample workload' counts. Tracked in memory, so it resets whenever the server restarts; it's this instance's activity, not an all-time total."
              />
            </div>
            <div
              style={{
                fontSize: "2rem",
                fontWeight: 700,
                color: "var(--green-text)",
              }}
            >
              {savings.total_requests}
            </div>
          </div>
          <div style={card}>
            <div
              style={{
                fontSize: "0.8rem",
                color: "var(--gray-500)",
                display: "flex",
                alignItems: "center",
              }}
            >
              Carbon-intensity gap (illustrative)
              <InfoTip
                label="Carbon-intensity gap"
                text="For each recommendation, the gap in carbon intensity (gCO₂/kWh) between the dirtiest candidate region and the greener one chosen, summed across recommendations. It's a rough indicator, not a real emissions total: per-kWh intensities aren't additive across workloads, and actual savings also depend on how much energy each job uses. In-memory for this server instance; resets on restart."
              />
            </div>
            <div
              style={{
                fontSize: "2rem",
                fontWeight: 700,
                color: "var(--green-text)",
              }}
            >
              {savings.total_carbon_saved_gco2_kwh.toFixed(1)}{" "}
              <span style={{ fontSize: "0.9rem", fontWeight: 400 }}>gCO₂/kWh</span>
            </div>
          </div>
          <div style={card}>
            <div
              style={{
                fontSize: "0.8rem",
                color: "var(--gray-500)",
                display: "flex",
                alignItems: "center",
              }}
            >
              Avg renewable % chosen
              <InfoTip
                label="Average renewable % chosen"
                text="Average renewable share of the regions this server has recommended so far."
              />
            </div>
            <div
              style={{
                fontSize: "2rem",
                fontWeight: 700,
                color: "var(--green-text)",
              }}
            >
              {savings.avg_renewable_percentage}%
            </div>
          </div>
        </div>
      )}

      {/* Live WebSocket feed - only when a live API backs it (not in static snapshot mode) */}
      {!snapshotEnabled && <LivePanel />}

      <CustomZoneLookup />

      {/* Filter */}
      <div
        style={{
          marginBottom: "1rem",
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {["", "aws", "gcp", "azure", "scaleway", "ovh", "hetzner"].map((p) => (
          <button
            type="button"
            key={p}
            onClick={() => setProvider(p)}
            style={{
              padding: "0.4rem 1rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: provider === p ? "var(--btn-green)" : "var(--surface)",
              color: provider === p ? "white" : "var(--gray-700)",
              cursor: "pointer",
              fontWeight: provider === p ? 600 : 400,
              fontSize: "0.85rem",
            }}
          >
            {p || "All"}
          </button>
        ))}
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search region, grid zone, or location…"
          aria-label="Search regions"
          style={{
            flex: "1 1 220px",
            minWidth: 180,
            padding: "0.4rem 0.75rem",
            borderRadius: 6,
            border: "1px solid var(--gray-200)",
            background: "var(--surface)",
            color: "inherit",
            fontSize: "0.85rem",
          }}
        />
      </div>

      {/* Regions table */}
      <div style={{ ...card, overflow: "auto" }}>
        {regionsLoading ? (
          <p style={{ color: "var(--gray-400)" }}>Loading regions…</p>
        ) : apiRegionsError && displayRegions.length === 0 ? (
          <p style={{ color: "var(--gray-500)" }}>
            Couldn't reach the API to load regions. It may be waking up (free tier, ~50s) - refresh
            in a moment.
          </p>
        ) : displayRegions.length === 0 ? (
          <p style={{ color: "var(--gray-400)" }}>No regions match this filter.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                {COLUMNS.map((col) => {
                  const active = sortKey === col.key;
                  return (
                    <th
                      key={col.key}
                      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                      style={{
                        textAlign: col.align,
                        padding: "0.5rem 0.25rem",
                      }}
                    >
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: col.align === "center" ? "center" : "flex-start",
                          width: "100%",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => toggleSort(col.key)}
                          title={`Sort by ${col.label}`}
                          style={{
                            background: "none",
                            border: "none",
                            font: "inherit",
                            fontSize: "0.8rem",
                            fontWeight: 600,
                            cursor: "pointer",
                            padding: "0.25rem",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            whiteSpace: "nowrap",
                            color: active ? "var(--green-text)" : "inherit",
                          }}
                        >
                          {col.label}
                          <span
                            aria-hidden
                            style={{
                              fontSize: "0.7rem",
                              opacity: active ? 1 : 0.35,
                            }}
                          >
                            {active ? (sortDir === "asc" ? "▲" : "▼") : "▴▾"}
                          </span>
                        </button>
                        {col.info && <InfoTip label={col.label} text={col.info} />}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {displayRegions.map((r) => (
                <RegionRow
                  key={`${r.provider}-${r.region}`}
                  region={r}
                  intensity={intensities[`${r.provider}/${r.region}`]}
                />
              ))}
            </tbody>
          </table>
        )}
        {sortedRegions.length > 20 && (
          <p
            style={{
              textAlign: "center",
              color: "var(--gray-400)",
              marginTop: "1rem",
            }}
          >
            Showing 20 of {sortedRegions.length}
            {q ? " matching" : ""} regions{q ? "" : " (sorted)"}. Refine your search or use the API
            for the full set.
          </p>
        )}
      </div>
    </div>
  );
}

function useCarbonStream() {
  const [updates, setUpdates] = useState<CarbonUpdate["data"]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const wsUrl = `${import.meta.env.VITE_WS_URL || "ws://localhost:8000"}/ws/carbon`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      // Subscribe with a 30-second interval for the demo
      ws.send(JSON.stringify({ interval_seconds: 30 }));
    };
    ws.onmessage = (event) => {
      try {
        const msg: CarbonUpdate = JSON.parse(event.data);
        if (msg.type === "carbon_update") {
          setUpdates(msg.data);
        }
      } catch {
        // ignore parse errors
      }
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { updates, connected, reconnect: connect };
}

function LivePanel() {
  const { updates, connected, reconnect } = useCarbonStream();

  return (
    <div style={{ ...card, marginBottom: "2rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "1.1rem" }}>
          Live Carbon Feed
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: connected ? "var(--green-500)" : "var(--red-400)",
              marginLeft: 8,
              verticalAlign: "middle",
            }}
            title={connected ? "Connected" : "Disconnected"}
          />
        </h2>
        {!connected && (
          <button
            type="button"
            onClick={reconnect}
            style={{
              padding: "0.3rem 0.8rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: "var(--surface)",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            Reconnect
          </button>
        )}
      </div>
      {updates.length === 0 ? (
        <p style={{ color: "var(--gray-400)", fontSize: "0.85rem" }}>
          {connected
            ? "Waiting for first update..."
            : "WebSocket not connected. Start the API server and click Reconnect."}
        </p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
            gap: "0.75rem",
          }}
        >
          {updates.map((d) => (
            <div
              key={`${d.provider}-${d.region}`}
              style={{
                padding: "0.75rem",
                borderRadius: 8,
                border: "1px solid var(--gray-200)",
                background: "var(--surface-alt)",
              }}
            >
              <div style={{ marginBottom: 4 }}>
                <span
                  style={{
                    fontSize: "0.7rem",
                    textTransform: "uppercase",
                    ...providerChip(d.provider),
                  }}
                >
                  {d.provider}
                </span>
              </div>
              <div
                style={{
                  fontFamily: "var(--mono)",
                  fontSize: "0.85rem",
                  marginBottom: 4,
                }}
              >
                {d.region}
              </div>
              <IntensityBar value={d.carbon_intensity_gco2_kwh} />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "0.7rem",
                  marginTop: 2,
                  color: "var(--gray-500)",
                }}
              >
                <span>{d.carbon_intensity_gco2_kwh} gCO₂</span>
                <span
                  style={{
                    color: d.renewable_percentage >= 70 ? "var(--green-text)" : "var(--gray-500)",
                  }}
                >
                  {d.renewable_percentage}% renew
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function useRegionIntensities(regions: CloudRegion[]) {
  const [data, setData] = useState<Record<string, CarbonIntensity>>({});

  // Batch fetch all regions in a single request
  useEffect(() => {
    if (regions.length === 0) return;
    let cancelled = false;

    const lookups = regions.map((r) => ({
      provider: r.provider,
      region: r.region,
    }));
    api
      .carbonIntensityBatch(lookups)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        // Batch failed - fall back to individual calls
        regions.forEach(async (r) => {
          try {
            const intensity = await api.carbonIntensity(r.provider, r.region);
            if (!cancelled) {
              setData((prev) => ({
                ...prev,
                [`${r.provider}/${r.region}`]: intensity,
              }));
            }
          } catch {
            /* swallow */
          }
        });
      });

    return () => {
      cancelled = true;
    };
  }, [regions]);

  return data;
}
