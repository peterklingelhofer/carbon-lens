import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { REPORT_URL, sitingFromGreenest, useCleanComputeReport } from "../api/report";
import { InfoTip } from "./InfoTip";

const PROVIDERS = ["aws", "gcp", "azure"];

// "Greenest region to deploy" — picks where to PERMANENTLY host a 24/7 workload by
// typical (history-mean) carbon intensity, and, given a continuous load, the annual
// kg each region would emit. Distinct from per-request routing: region choice is a
// permanent, high-leverage decision (a region can be many times cleaner forever).
// Runs fully static off the published clean-compute report on the CDN (filtering and
// the annual-kg math happen client-side); falls back to /carbon/siting without it.
export function SitingPicker() {
  const [providers, setProviders] = useState<string[]>(PROVIDERS);
  const [watts, setWatts] = useState<number>(500);

  const toggle = (p: string) =>
    setProviders((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]));

  const report = useCleanComputeReport();
  const providersCsv = providers.join(",");
  const {
    data: apiData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["siting", providersCsv, watts],
    queryFn: () => api.siting(providersCsv, watts || undefined),
    enabled: !REPORT_URL && providers.length > 0, // CDN report has it -> skip the API
    staleTime: 30 * 60_000,
    retry: 1,
  });

  const data = report.data
    ? sitingFromGreenest(report.data.greenest_regions, providers, watts, report.data.days_analyzed)
    : apiData;

  return (
    <div style={{ marginTop: "2rem" }}>
      <h2
        style={{
          fontSize: "1.1rem",
          margin: "0 0 0.25rem",
          display: "inline-flex",
          alignItems: "center",
        }}
      >
        Greenest region to deploy
        <InfoTip
          label="siting"
          text="Where to PERMANENTLY host a 24/7 workload, ranked by typical (history-mean) carbon intensity — the honest basis for an always-on deployment, unlike the instantaneous value used for per-request routing. With a continuous load it shows each region's annual CO2. Region choice is permanent and high-leverage: a region can be many times cleaner, forever."
        />
      </h2>
      <div
        style={{
          display: "flex",
          gap: 14,
          alignItems: "center",
          flexWrap: "wrap",
          margin: "0.5rem 0 0.75rem",
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          {PROVIDERS.map((p) => (
            <button
              type="button"
              key={p}
              onClick={() => toggle(p)}
              style={{
                padding: "3px 10px",
                borderRadius: 6,
                border: "1px solid var(--gray-300)",
                cursor: "pointer",
                fontSize: "0.8rem",
                background: providers.includes(p) ? "var(--btn-green)" : "transparent",
                color: providers.includes(p) ? "#fff" : "var(--gray-500)",
              }}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>
        <label style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
          Continuous load{" "}
          <input
            type="number"
            min={0}
            value={watts}
            onChange={(e) => setWatts(Number(e.target.value))}
            style={{ width: 80, padding: "2px 6px" }}
          />{" "}
          W
        </label>
      </div>

      {isLoading && <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>Loading…</div>}
      {isError && (
        <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
          Couldn't load siting data right now.
        </div>
      )}
      {data && data.options.length > 0 && (
        <>
          {data.annual_kg_saved_vs_worst != null && data.annual_kg_saved_vs_worst > 0 && (
            <p style={{ fontSize: "0.82rem", margin: "0 0 0.5rem" }}>
              Hosting in{" "}
              <strong>
                {data.recommended.provider}/{data.recommended.region}
              </strong>{" "}
              vs the worst candidate saves{" "}
              <strong style={{ color: "var(--green-text)" }}>
                ~{Math.round(data.annual_kg_saved_vs_worst)} kg CO₂/yr
              </strong>{" "}
              at {data.power_watts} W.
            </p>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {data.options.map((o, i) => (
              <div
                key={`${o.provider}/${o.region}`}
                style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "0.82rem" }}
              >
                <span style={{ width: 16, color: "var(--gray-400)" }}>{i + 1}</span>
                <span style={{ width: 200 }}>
                  <span style={{ fontWeight: i === 0 ? 700 : 500 }}>
                    {o.provider}/{o.region}
                  </span>{" "}
                  <span style={{ color: "var(--gray-500)" }}>{o.location}</span>
                </span>
                <span style={{ width: 110, textAlign: "right", color: "var(--green-text)" }}>
                  {Math.round(o.typical_gco2_kwh)} gCO₂/kWh
                </span>
                <span style={{ width: 90, textAlign: "right", color: "var(--gray-500)" }}>
                  {o.annual_kg != null ? `${Math.round(o.annual_kg)} kg/yr` : ""}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
