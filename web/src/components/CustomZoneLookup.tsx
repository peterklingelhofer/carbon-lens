import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { intensityColor } from "../lib/intensity";
import { card } from "../styles";
import { InfoTip } from "./InfoTip";

const muted: React.CSSProperties = { color: "var(--gray-500)", fontSize: "0.82rem" };

// Look up carbon intensity for any covered grid zone directly -- for on-prem /
// colocation workloads that aren't a cloud region but sit on a grid we cover.
export function CustomZoneLookup() {
  const { data: zones } = useQuery({
    queryKey: ["carbon-zones"],
    queryFn: () => api.carbonZones(),
    staleTime: 60 * 60_000,
  });
  const [zone, setZone] = useState("DE");

  const {
    data: ci,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["carbon-zone", zone],
    queryFn: () => api.carbonZone(zone),
    enabled: !!zone,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const selected = zones?.find((z) => z.grid_zone === zone);

  return (
    <div style={{ ...card, marginBottom: "2rem" }}>
      <h2
        style={{ margin: "0 0 0.25rem", fontSize: "1.1rem", display: "flex", alignItems: "center" }}
      >
        On-prem or any grid zone
        <InfoTip
          label="grid zone"
          text="Not on a big cloud? Pick the electricity grid zone your datacenter sits on to see its live carbon intensity — same data, no cloud region required."
        />
      </h2>
      <p style={{ ...muted, margin: "0 0 0.75rem" }}>
        Look up carbon intensity for any covered grid zone directly.
      </p>

      <select
        value={zone}
        onChange={(e) => setZone(e.target.value)}
        aria-label="Grid zone"
        style={{
          padding: "0.4rem 0.7rem",
          borderRadius: 6,
          border: "1px solid var(--gray-200)",
          background: "var(--surface)",
          color: "inherit",
          fontSize: "0.85rem",
          maxWidth: "100%",
        }}
      >
        {zones ? (
          zones.map((z) => (
            <option key={z.grid_zone} value={z.grid_zone}>
              {z.grid_zone} — {z.location}
            </option>
          ))
        ) : (
          <option value={zone}>{zone}</option>
        )}
      </select>

      {isLoading && <p style={{ ...muted, marginTop: "0.75rem" }}>Loading…</p>}
      {isError && <p style={{ ...muted, marginTop: "0.75rem" }}>Couldn't load this zone.</p>}
      {ci && !isLoading && (
        <div style={{ marginTop: "1rem" }}>
          <span
            style={{
              fontSize: "1.6rem",
              fontWeight: 700,
              color: intensityColor(ci.carbon_intensity_gco2_kwh),
            }}
          >
            {ci.carbon_intensity_gco2_kwh}
            <span style={{ fontSize: "0.8rem", fontWeight: 400, color: "var(--gray-500)" }}>
              {" "}
              gCO₂/kWh
            </span>
          </span>
          <span style={{ marginLeft: "1rem", color: "var(--green-text)", fontWeight: 600 }}>
            {ci.renewable_percentage}% renewable
          </span>
          {ci.marginal_intensity_gco2_kwh != null && (
            <span style={{ marginLeft: "1rem", ...muted }}>
              marginal ~{ci.marginal_intensity_gco2_kwh} gCO₂
            </span>
          )}
          {selected && selected.regions.length > 0 && (
            <p style={{ ...muted, marginTop: "0.5rem" }}>
              Cloud regions on this grid: {selected.regions.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
