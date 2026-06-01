import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useSnapshot, type CarbonSnapshot } from "../api/snapshot";
import type { CloudRegion, CarbonIntensity, CarbonUpdate } from "../api/types";
import { useState, useEffect, useRef, useCallback } from "react";
import { section as sectionFn, card, providerChip } from "../styles";

const section = sectionFn(1100);

function intensityColor(val: number): string {
  if (val <= 50) return "var(--green-500)";
  if (val <= 150) return "var(--green-400)";
  if (val <= 300) return "var(--amber)";
  if (val <= 500) return "var(--orange-400)";
  return "var(--red-400)";
}

function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
}

function QualityTag({ quality }: { quality?: CarbonIntensity["quality"] }) {
  if (quality !== "estimated") return null;
  return (
    <span
      title="Estimated from a heuristic / weather model — the upstream grid API for this zone is intermittent"
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

function SnapshotBanner({ snapshot }: { snapshot: CarbonSnapshot }) {
  const { live_zones, estimated_zones } = snapshot.summary;
  return (
    <p style={{ color: "var(--gray-500)", marginBottom: "2rem", fontSize: "0.9rem" }}>
      <strong style={{ color: "var(--green-700)" }}>{live_zones} grid zones live</strong> from
      real grid-operator APIs
      {estimated_zones > 0 && (
        <>
          {" "}
          · {estimated_zones} estimated (intermittent upstream, tagged{" "}
          <span style={{ color: "var(--amber)", fontWeight: 600 }}>est.</span>)
        </>
      )}{" "}
      · updated {timeAgo(snapshot.generated_at)}. No mock data.
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

function RegionRow({
  region,
  intensity,
}: {
  region: CloudRegion;
  intensity?: CarbonIntensity;
}) {
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
      <td style={{ padding: "0.5rem", fontFamily: "var(--mono)", fontSize: "0.85rem" }}>
        {region.region}
      </td>
      <td style={{ padding: "0.5rem", fontSize: "0.85rem" }}>{region.grid_zone}</td>
      <td style={{ padding: "0.5rem", fontSize: "0.85rem" }}>{region.location}</td>
      <td style={{ padding: "0.5rem", width: 120 }}>
        {intensity ? (
          <div>
            <IntensityBar value={intensity.carbon_intensity_gco2_kwh} />
            <span style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>
              {intensity.carbon_intensity_gco2_kwh} gCO2/kWh
              <QualityTag quality={intensity.quality} />
            </span>
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
              color: intensity.renewable_percentage >= 70 ? "var(--green-600)" : "var(--gray-600)",
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

export function Dashboard() {
  const [provider, setProvider] = useState<string>("");

  const { data: snapshot } = useSnapshot();
  const usingSnapshot = !!snapshot;

  const { data: apiRegions, isLoading: apiRegionsLoading } = useQuery({
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

  const displayRegions = regions?.slice(0, 20) ?? [];
  const apiIntensities = useRegionIntensities(usingSnapshot ? [] : displayRegions);
  const intensities = usingSnapshot ? snapshot.intensities : apiIntensities;

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
        <h1 style={{ margin: 0 }}>Carbon Dashboard</h1>
        <button
          onClick={() => routeSample.mutate()}
          disabled={routeSample.isPending}
          style={{
            padding: "0.55rem 1.25rem",
            borderRadius: 8,
            border: "none",
            background: "var(--green-600)",
            color: "white",
            fontWeight: 600,
            fontSize: "0.85rem",
            cursor: routeSample.isPending ? "wait" : "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {routeSample.isPending ? "Routing…" : "Route a sample workload"}
        </button>
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
          Live carbon intensity data powering the API. 11 cascading sources (6 live integrations), 75+ cloud regions.
        </p>
      )}
      {routeSample.data && (
        <p style={{ color: "var(--gray-600)", fontSize: "0.85rem", marginBottom: "2rem" }}>
          Routed to{" "}
          <strong style={{ textTransform: "uppercase" }}>
            {routeSample.data.recommended.provider}
          </strong>{" "}
          <code>{routeSample.data.recommended.region}</code> —{" "}
          {routeSample.data.recommended.carbon_intensity_gco2_kwh} gCO2/kWh,{" "}
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
            <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
              Total Requests Routed
            </div>
            <div style={{ fontSize: "2rem", fontWeight: 700, color: "var(--green-700)" }}>
              {savings.total_requests}
            </div>
          </div>
          <div style={card}>
            <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
              Carbon Saved
            </div>
            <div style={{ fontSize: "2rem", fontWeight: 700, color: "var(--green-700)" }}>
              {savings.total_carbon_saved_gco2_kwh.toFixed(1)}{" "}
              <span style={{ fontSize: "0.9rem", fontWeight: 400 }}>gCO2/kWh</span>
            </div>
          </div>
          <div style={card}>
            <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
              Avg Renewable %
            </div>
            <div style={{ fontSize: "2rem", fontWeight: 700, color: "var(--green-700)" }}>
              {savings.avg_renewable_percentage}%
            </div>
          </div>
        </div>
      )}

      {/* Live WebSocket feed — only when a live API backs it (not in static snapshot mode) */}
      {!usingSnapshot && <LivePanel />}

      {/* Filter */}
      <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem" }}>
        {["", "aws", "gcp", "azure"].map((p) => (
          <button
            key={p}
            onClick={() => setProvider(p)}
            style={{
              padding: "0.4rem 1rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: provider === p ? "var(--green-600)" : "var(--surface)",
              color: provider === p ? "white" : "var(--gray-700)",
              cursor: "pointer",
              fontWeight: provider === p ? 600 : 400,
              fontSize: "0.85rem",
            }}
          >
            {p || "All"}
          </button>
        ))}
      </div>

      {/* Regions table */}
      <div style={{ ...card, overflow: "auto" }}>
        {regionsLoading ? (
          <p>Loading regions...</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                <th style={{ textAlign: "left", padding: "0.5rem", fontSize: "0.8rem" }}>
                  Provider
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem", fontSize: "0.8rem" }}>
                  Region
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem", fontSize: "0.8rem" }}>
                  Grid Zone
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem", fontSize: "0.8rem" }}>
                  Location
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem", fontSize: "0.8rem" }}>
                  Carbon Intensity
                </th>
                <th
                  style={{
                    textAlign: "center",
                    padding: "0.5rem",
                    fontSize: "0.8rem",
                  }}
                >
                  Renewable %
                </th>
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
        {regions && regions.length > 20 && (
          <p style={{ textAlign: "center", color: "var(--gray-400)", marginTop: "1rem" }}>
            Showing 20 of {regions.length} regions. Use the API for full data.
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
    const wsUrl =
      (import.meta.env.VITE_WS_URL || "ws://localhost:8000") + "/ws/carbon";
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
                <span>{d.carbon_intensity_gco2_kwh} gCO2</span>
                <span
                  style={{
                    color:
                      d.renewable_percentage >= 70
                        ? "var(--green-600)"
                        : "var(--gray-500)",
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

    const lookups = regions.map((r) => ({ provider: r.provider, region: r.region }));
    api.carbonIntensityBatch(lookups).then((result) => {
      if (!cancelled) setData(result);
    }).catch(() => {
      // Batch failed — fall back to individual calls
      regions.forEach(async (r) => {
        try {
          const intensity = await api.carbonIntensity(r.provider, r.region);
          if (!cancelled) {
            setData((prev) => ({ ...prev, [`${r.provider}/${r.region}`]: intensity }));
          }
        } catch { /* swallow */ }
      });
    });

    return () => { cancelled = true; };
  }, [regions]);

  return data;
}
