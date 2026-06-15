import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { intensityColor } from "../lib/intensity";
import { card } from "../styles";
import { InfoTip } from "./InfoTip";

const PROVIDERS = ["aws", "gcp", "azure", "scaleway", "ovh", "hetzner"];
const DEFAULT_REGION: Record<string, string> = {
  aws: "us-east-1",
  gcp: "us-central1",
  azure: "eastus",
  scaleway: "fr-par",
  ovh: "gra",
  hetzner: "fsn1",
};

const muted: React.CSSProperties = { color: "var(--gray-500)", fontSize: "0.78rem" };

// Grid of the next ~7 days x 24 hours, each cell coloured by projected carbon
// intensity, so the cleanest hours to run a job jump out at a glance.
function Heatmap({ provider, region }: { provider: string; region: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["forecast-heatmap", provider, region],
    queryFn: () => api.carbonForecast(provider, region, 168),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  if (isLoading) return <p style={muted}>Loading forecast…</p>;
  if (isError || !data || data.points.length < 2)
    return <p style={muted}>No forecast available for this region.</p>;

  // Bucket points into local-time date -> hour -> intensity.
  const byDate = new Map<string, (number | null)[]>();
  for (const p of data.points) {
    const d = new Date(p.timestamp);
    const key = d.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    if (!byDate.has(key)) byDate.set(key, Array(24).fill(null));
    const row = byDate.get(key);
    if (row) row[d.getHours()] = p.carbon_intensity_gco2_kwh;
  }
  const rows = [...byDate.entries()];
  const method =
    data.method === "entsoe_day_ahead"
      ? "ENTSO-E day-ahead for the first ~48h, then a time-of-day model"
      : "a time-of-day model";

  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: "0.7rem" }}>
          <thead>
            <tr>
              <th aria-label="day" />
              {Array.from({ length: 24 }, (_, h) => (
                <th
                  // biome-ignore lint/suspicious/noArrayIndexKey: fixed 24-hour columns, index is the hour
                  key={h}
                  style={{ width: 15, color: "var(--gray-400)", fontWeight: 400, padding: 0 }}
                >
                  {h % 6 === 0 ? h : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, hours]) => (
              <tr key={label}>
                <td style={{ paddingRight: 8, whiteSpace: "nowrap", color: "var(--gray-500)" }}>
                  {label}
                </td>
                {hours.map((v, h) => (
                  <td
                    // biome-ignore lint/suspicious/noArrayIndexKey: fixed 24-hour columns, index is the hour
                    key={h}
                    title={
                      v == null
                        ? `${label} ${h}:00 — no data`
                        : `${label} ${h}:00 — ${Math.round(v)} gCO₂/kWh`
                    }
                    style={{
                      width: 15,
                      height: 15,
                      background: v == null ? "var(--gray-100)" : intensityColor(v),
                      border: "1px solid var(--surface)",
                    }}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ ...muted, marginTop: 8 }}>
        Greener = cleaner; each cell is one local-time hour. Projection from {method} — directional
        guidance, not a precise prediction.
      </p>
    </div>
  );
}

export function CleanWindowHeatmap() {
  const [provider, setProvider] = useState("aws");
  const [region, setRegion] = useState(DEFAULT_REGION.aws);

  const { data: regions } = useQuery({
    queryKey: ["regions", provider],
    queryFn: () => api.regions(provider),
    staleTime: 60 * 60_000,
  });

  return (
    <div style={{ ...card, marginTop: "1.5rem" }}>
      <h2
        style={{ margin: "0 0 0.25rem", fontSize: "1.1rem", display: "flex", alignItems: "center" }}
      >
        7-day clean-window outlook
        <InfoTip
          label="clean-window outlook"
          text="Projected carbon intensity for each hour over the next week, so you can pick the greenest time to run flexible jobs. EU zones use ENTSO-E's real day-ahead forecast for ~48h; beyond that (and elsewhere) it's a local time-of-day model."
        />
      </h2>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "0.75rem 0" }}>
        {PROVIDERS.map((p) => (
          <button
            type="button"
            key={p}
            onClick={() => {
              setProvider(p);
              setRegion(DEFAULT_REGION[p]);
            }}
            style={{
              padding: "0.3rem 0.9rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: provider === p ? "var(--btn-green)" : "var(--surface)",
              color: provider === p ? "white" : "var(--gray-700)",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            {p}
          </button>
        ))}
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          aria-label="Region"
          style={{
            padding: "0.3rem 0.6rem",
            borderRadius: 6,
            border: "1px solid var(--gray-200)",
            background: "var(--surface)",
            color: "inherit",
            fontSize: "0.8rem",
          }}
        >
          {regions ? (
            regions.map((r) => (
              <option key={r.region} value={r.region}>
                {r.region}
                {r.location ? ` — ${r.location}` : ""}
              </option>
            ))
          ) : (
            <option value={region}>{region}</option>
          )}
        </select>
      </div>
      <Heatmap provider={provider} region={region} />
    </div>
  );
}
