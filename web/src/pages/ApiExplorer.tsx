import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CarbonIntensity, RouteResponse } from "../api/types";
import { section as sectionFn, card } from "../styles";

const section = sectionFn(1100);

const PROVIDERS = ["aws", "gcp", "azure"] as const;

const POPULAR_REGIONS: Record<string, string[]> = {
  aws: ["us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-southeast-1", "ca-central-1"],
  gcp: ["us-central1", "europe-north1", "europe-west1", "us-east4", "asia-southeast1", "australia-southeast1"],
  azure: ["eastus", "westeurope", "norwayeast", "uksouth", "australiaeast", "canadacentral"],
};

export function ApiExplorer() {
  const [provider, setProvider] = useState("aws");
  const [region, setRegion] = useState("us-east-1");
  const [intensityResult, setIntensityResult] = useState<CarbonIntensity | null>(null);
  const [routeResult, setRouteResult] = useState<RouteResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"intensity" | "route" | "batch">("intensity");

  const { data: allRegions } = useQuery({
    queryKey: ["regions"],
    queryFn: () => api.regions(),
  });

  const intensityMutation = useMutation({
    mutationFn: () => api.carbonIntensity(provider, region),
    onSuccess: (data) => {
      setIntensityResult(data);
      setRouteResult(null);
    },
  });

  const routeMutation = useMutation({
    mutationFn: () =>
      api.route({
        constraints: {
          providers: ["aws", "gcp", "azure"],
          carbon_weight: 1.0,
          cost_weight: 0.0,
        },
      }),
    onSuccess: (data) => {
      setRouteResult(data);
      setIntensityResult(null);
    },
  });

  const batchMutation = useMutation({
    mutationFn: () =>
      api.carbonIntensityBatch([
        { provider: "aws", region: "us-east-1" },
        { provider: "aws", region: "eu-west-1" },
        { provider: "gcp", region: "europe-north1" },
        { provider: "gcp", region: "us-central1" },
        { provider: "azure", region: "norwayeast" },
        { provider: "azure", region: "eastus" },
      ]),
  });

  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem" }}>API Explorer</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Test the Carbon Intensity API interactively. Every query hits live data sources.
      </p>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        {([
          { key: "intensity", label: "GET Carbon Intensity" },
          { key: "route", label: "POST Route" },
          { key: "batch", label: "POST Batch" },
        ] as const).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: activeTab === tab.key ? "var(--green-600)" : "var(--surface)",
              color: activeTab === tab.key ? "white" : "var(--gray-700)",
              cursor: "pointer",
              fontWeight: activeTab === tab.key ? 600 : 400,
              fontSize: "0.85rem",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Carbon Intensity Tab */}
      {activeTab === "intensity" && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>
            GET /api/v1/carbon/{"{provider}"}/{"{region}"}
          </h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "0 0 1rem" }}>
            Get real-time carbon intensity for any cloud region.
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 2fr",
              gap: "1rem",
              marginBottom: "1rem",
            }}
          >
            <div>
              <label style={labelStyle}>Cloud Provider</label>
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setRegion(POPULAR_REGIONS[e.target.value]?.[0] || "");
                }}
                style={inputStyle}
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>{p.toUpperCase()}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Region</label>
              <select value={region} onChange={(e) => setRegion(e.target.value)} style={inputStyle}>
                {(allRegions || [])
                  .filter((r) => r.provider === provider)
                  .map((r) => (
                    <option key={r.region} value={r.region}>
                      {r.region} ({r.location})
                    </option>
                  ))}
                {!allRegions && POPULAR_REGIONS[provider]?.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>

          {/* curl example */}
          <div style={codeBlockStyle}>
            <code>curl http://localhost:8000/api/v1/carbon/{provider}/{region}</code>
          </div>

          <button
            onClick={() => intensityMutation.mutate()}
            disabled={intensityMutation.isPending}
            style={buttonStyle(intensityMutation.isPending)}
          >
            {intensityMutation.isPending ? "Querying..." : "Send Request"}
          </button>
        </div>
      )}

      {/* Route Tab */}
      {activeTab === "route" && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>
            POST /api/v1/route
          </h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "0 0 1rem" }}>
            Find the greenest cloud region across all providers right now.
          </p>

          <div style={codeBlockStyle}>
            <code style={{ whiteSpace: "pre" }}>{`curl -X POST http://localhost:8000/api/v1/route \\
  -H "Content-Type: application/json" \\
  -d '{"constraints": {"providers": ["aws","gcp","azure"], "carbon_weight": 1.0}}'`}</code>
          </div>

          <button
            onClick={() => routeMutation.mutate()}
            disabled={routeMutation.isPending}
            style={buttonStyle(routeMutation.isPending)}
          >
            {routeMutation.isPending ? "Routing..." : "Find Greenest Region"}
          </button>
        </div>
      )}

      {/* Batch Tab */}
      {activeTab === "batch" && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>
            POST /api/v1/carbon/batch
          </h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "0 0 1rem" }}>
            Query multiple regions in a single call. Returns carbon data for each.
          </p>

          <div style={codeBlockStyle}>
            <code style={{ whiteSpace: "pre" }}>{`curl -X POST http://localhost:8000/api/v1/carbon/batch \\
  -H "Content-Type: application/json" \\
  -d '[
    {"provider": "aws", "region": "us-east-1"},
    {"provider": "aws", "region": "eu-west-1"},
    {"provider": "gcp", "region": "europe-north1"},
    {"provider": "gcp", "region": "us-central1"},
    {"provider": "azure", "region": "norwayeast"},
    {"provider": "azure", "region": "eastus"}
  ]'`}</code>
          </div>

          <button
            onClick={() => batchMutation.mutate()}
            disabled={batchMutation.isPending}
            style={buttonStyle(batchMutation.isPending)}
          >
            {batchMutation.isPending ? "Querying..." : "Send Batch Request"}
          </button>

          {/* Batch Result */}
          {batchMutation.data && (
            <div style={{ marginTop: "1.5rem" }}>
              <h3 style={{ fontSize: "0.95rem", marginBottom: "0.75rem" }}>Response</h3>
              <div style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                      <th style={th}>Region</th>
                      <th style={{ ...th, textAlign: "right" }}>gCO2/kWh</th>
                      <th style={{ ...th, textAlign: "right" }}>Renewable %</th>
                      <th style={th}>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(batchMutation.data)
                      .sort(([, a], [, b]) => a.carbon_intensity_gco2_kwh - b.carbon_intensity_gco2_kwh)
                      .map(([key, val]) => (
                        <tr key={key} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                          <td style={{ ...td, fontFamily: "var(--mono)", fontSize: "0.8rem" }}>{key}</td>
                          <td style={{
                            ...td, textAlign: "right", fontWeight: 600,
                            color: val.carbon_intensity_gco2_kwh <= 50 ? "var(--green-600)" :
                                   val.carbon_intensity_gco2_kwh <= 200 ? "var(--green-500)" : "var(--orange-400)",
                          }}>
                            {val.carbon_intensity_gco2_kwh}
                          </td>
                          <td style={{
                            ...td, textAlign: "right",
                            color: val.renewable_percentage >= 70 ? "var(--green-600)" : "inherit",
                          }}>
                            {val.renewable_percentage}%
                          </td>
                          <td style={{ ...td, fontSize: "0.8rem", color: "var(--gray-500)" }}>
                            {val.source}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Single Intensity Result */}
      {intensityResult && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h3 style={{ margin: "0 0 1rem", fontSize: "1rem" }}>Response</h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "1rem",
              marginBottom: "1rem",
            }}
          >
            <ResultCard
              label="Carbon Intensity"
              value={`${intensityResult.carbon_intensity_gco2_kwh}`}
              unit="gCO2/kWh"
              positive={intensityResult.carbon_intensity_gco2_kwh <= 100}
            />
            <ResultCard
              label="Renewable"
              value={`${intensityResult.renewable_percentage}`}
              unit="%"
              positive={intensityResult.renewable_percentage >= 50}
            />
            <ResultCard
              label="Grid Zone"
              value={intensityResult.grid_zone}
            />
            <ResultCard
              label="Data Source"
              value={intensityResult.source}
            />
          </div>
          <div style={codeBlockStyle}>
            <code style={{ whiteSpace: "pre", fontSize: "0.8rem" }}>
              {JSON.stringify(intensityResult, null, 2)}
            </code>
          </div>
        </div>
      )}

      {/* Route Result */}
      {routeResult && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h3 style={{ margin: "0 0 1rem", fontSize: "1rem" }}>
            Greenest Region Right Now
          </h3>
          <div
            style={{
              padding: "1rem",
              borderRadius: 8,
              background: "rgba(34, 197, 94, 0.08)",
              border: "1px solid var(--green-200)",
              marginBottom: "1rem",
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "0.75rem",
              }}
            >
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Provider</div>
                <div style={{ fontWeight: 700, textTransform: "uppercase" }}>
                  {routeResult.recommended.provider}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Region</div>
                <div style={{ fontWeight: 600, fontFamily: "var(--mono)" }}>
                  {routeResult.recommended.region}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Carbon</div>
                <div style={{ fontWeight: 700, color: "var(--green-600)" }}>
                  {routeResult.recommended.carbon_intensity_gco2_kwh} gCO2/kWh
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Renewable</div>
                <div style={{ fontWeight: 700, color: "var(--green-600)" }}>
                  {routeResult.recommended.renewable_percentage}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Savings</div>
                <div style={{ fontWeight: 700, color: "var(--green-600)" }}>
                  {routeResult.recommended.carbon_savings_vs_worst_pct.toFixed(1)}%
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>vs worst option</div>
              </div>
            </div>
          </div>

          {/* Alternatives */}
          {routeResult.alternatives.length > 0 && (
            <>
              <h4 style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>
                Alternatives ({routeResult.alternatives.length})
              </h4>
              <div style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                      <th style={th}>Provider</th>
                      <th style={th}>Region</th>
                      <th style={{ ...th, textAlign: "right" }}>gCO2/kWh</th>
                      <th style={{ ...th, textAlign: "right" }}>Renewable %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {routeResult.alternatives.slice(0, 10).map((alt, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                        <td style={{ ...td, fontWeight: 600, textTransform: "uppercase", fontSize: "0.8rem" }}>
                          {alt.provider}
                        </td>
                        <td style={{ ...td, fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
                          {alt.region}
                        </td>
                        <td style={{
                          ...td, textAlign: "right", fontWeight: 600,
                          color: alt.carbon_intensity_gco2_kwh <= 50 ? "var(--green-600)" :
                                 alt.carbon_intensity_gco2_kwh <= 200 ? "var(--green-500)" : "var(--orange-400)",
                        }}>
                          {alt.carbon_intensity_gco2_kwh}
                        </td>
                        <td style={{
                          ...td, textAlign: "right",
                          color: alt.renewable_percentage >= 70 ? "var(--green-600)" : "inherit",
                        }}>
                          {alt.renewable_percentage}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ResultCard({
  label,
  value,
  unit,
  positive,
}: {
  label: string;
  value: string | number;
  unit?: string;
  positive?: boolean;
}) {
  return (
    <div
      style={{
        padding: "0.75rem",
        borderRadius: 8,
        border: "1px solid var(--gray-200)",
        background: "var(--surface-alt)",
      }}
    >
      <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>{label}</div>
      <div
        style={{
          fontSize: "1.3rem",
          fontWeight: 700,
          color: positive ? "var(--green-700)" : "inherit",
        }}
      >
        {value}
        {unit && (
          <span style={{ fontSize: "0.75rem", fontWeight: 400, marginLeft: 4 }}>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: "0.8rem",
  color: "var(--gray-500)",
  display: "block",
  marginBottom: 4,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.5rem",
  borderRadius: 6,
  border: "1px solid var(--gray-200)",
  fontSize: "0.9rem",
  boxSizing: "border-box",
};

const codeBlockStyle: React.CSSProperties = {
  fontFamily: "var(--mono)",
  fontSize: "0.8rem",
  background: "var(--surface-alt)",
  padding: "1rem",
  borderRadius: 8,
  overflow: "auto",
  marginBottom: "1rem",
};

function buttonStyle(pending: boolean): React.CSSProperties {
  return {
    padding: "0.75rem 2rem",
    borderRadius: 8,
    border: "none",
    background: "var(--green-600)",
    color: "white",
    fontWeight: 600,
    cursor: pending ? "wait" : "pointer",
  };
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem",
  fontSize: "0.75rem",
  fontWeight: 600,
  color: "var(--gray-500)",
};

const td: React.CSSProperties = { padding: "0.5rem", fontSize: "0.85rem" };
