import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CloudRegion, CarbonIntensity, CarbonUpdate } from "../api/types";
import { useState, useEffect, useRef, useCallback } from "react";
import { section as sectionFn, card } from "../styles";

const section = sectionFn(1100);

function intensityColor(val: number): string {
  if (val <= 50) return "var(--green-500)";
  if (val <= 150) return "var(--green-400)";
  if (val <= 300) return "var(--yellow-400)";
  if (val <= 500) return "var(--orange-400)";
  return "var(--red-400)";
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
            fontWeight: 600,
            textTransform: "uppercase",
            fontSize: "0.8rem",
            color:
              region.provider === "aws"
                ? "var(--orange-400)"
                : region.provider === "gcp"
                  ? "var(--blue-500)"
                  : "var(--blue-400)",
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

  const { data: regions, isLoading: regionsLoading } = useQuery({
    queryKey: ["regions", provider],
    queryFn: () => api.regions(provider || undefined),
  });

  const { data: savings } = useQuery({
    queryKey: ["savings"],
    queryFn: () => api.savings(),
  });

  const displayRegions = regions?.slice(0, 20) ?? [];
  const intensities = useRegionIntensities(displayRegions);

  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem" }}>Carbon Dashboard</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Live carbon intensity data powering the API. 11 sources, 90+ cloud regions, updated every minute.
      </p>

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

      {/* Live WebSocket feed */}
      <LivePanel />

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
              <div
                style={{
                  fontSize: "0.7rem",
                  textTransform: "uppercase",
                  fontWeight: 600,
                  color:
                    d.provider === "aws"
                      ? "var(--orange-400)"
                      : d.provider === "gcp"
                        ? "var(--blue-500)"
                        : "var(--blue-400)",
                }}
              >
                {d.provider}
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
