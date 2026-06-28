import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { API_BASE, api } from "../api/client";
import type { CarbonIntensity, RouteResponse } from "../api/types";
import { InfoTip } from "../components/InfoTip";
import { StatCard } from "../components/StatCard";
import { TableHeadCell } from "../components/TableHeadCell";
import { EMISSIONS_TIP, GRID_ZONE_TIP, SOURCE_TIP, TABLE_RENEWABLE_TIP } from "../copy";
import { intensityVarColor } from "../lib/intensity";
import { card, inputStyle, labelStyle, sectionStyle, td } from "../styles";

const section = sectionStyle(1100);

const PROVIDERS = ["aws", "gcp", "azure"] as const;

const POPULAR_REGIONS: Record<string, string[]> = {
  aws: ["us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-southeast-1", "ca-central-1"],
  gcp: [
    "us-central1",
    "europe-north1",
    "europe-west1",
    "us-east4",
    "asia-southeast1",
    "australia-southeast1",
  ],
  azure: ["eastus", "westeurope", "norwayeast", "uksouth", "australiaeast", "canadacentral"],
};

export function ApiExplorer() {
  const [provider, setProvider] = useState("aws");
  const [region, setRegion] = useState("us-east-1");
  const [intensityResult, setIntensityResult] = useState<CarbonIntensity | null>(null);
  const [routeResult, setRouteResult] = useState<RouteResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"intensity" | "route" | "batch">("intensity");
  const TAB_KEYS = ["intensity", "route", "batch"] as const;
  const handleTabKeyDown = (e: React.KeyboardEvent, tabKey: (typeof TAB_KEYS)[number]) => {
    const i = TAB_KEYS.indexOf(tabKey);
    let next = i;
    if (e.key === "ArrowRight") next = (i + 1) % TAB_KEYS.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + TAB_KEYS.length) % TAB_KEYS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TAB_KEYS.length - 1;
    else return;
    e.preventDefault();
    const nextKey = TAB_KEYS[next];
    setActiveTab(nextKey);
    document.getElementById(`api-tab-${nextKey}`)?.focus();
  };

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
      <h1
        style={{
          marginBottom: "0.5rem",
          display: "flex",
          alignItems: "center",
        }}
      >
        API explorer
        <InfoTip
          label="API"
          text="An API (application programming interface) lets other software request data from this service. This page lets you try those requests by hand and see the live response your code would get."
        />
      </h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "1rem" }}>
        Try the carbon API by hand. Each query returns the latest reading - live where a
        grid-operator feed exists, a clearly-labelled estimate otherwise. No key required;
        rate-limited to 100 requests/min per IP.
      </p>
      <p style={{ marginBottom: "2rem", fontSize: "0.9rem" }}>
        Prefer the full reference?{" "}
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: "var(--green-text)",
            fontWeight: 600,
            textDecoration: "underline",
          }}
        >
          Open the interactive Swagger docs ↗
        </a>{" "}
        <span style={{ color: "var(--gray-500)" }}>
          (every endpoint, with request/response schemas - also at{" "}
          <code style={{ fontSize: "0.8rem" }}>/redoc</code> and{" "}
          <code style={{ fontSize: "0.8rem" }}>/openapi.json</code>)
        </span>
      </p>

      {/* Tabs */}
      <div
        role="tablist"
        aria-label="API endpoints"
        style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}
      >
        {(
          [
            { key: "intensity", label: "GET Carbon Intensity" },
            { key: "route", label: "POST Route" },
            { key: "batch", label: "POST Batch" },
          ] as const
        ).map((tab) => (
          <button
            type="button"
            role="tab"
            id={`api-tab-${tab.key}`}
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            aria-selected={activeTab === tab.key}
            tabIndex={activeTab === tab.key ? 0 : -1}
            onKeyDown={(e) => handleTabKeyDown(e, tab.key)}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: activeTab === tab.key ? "var(--btn-green)" : "var(--surface)",
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
        <div
          role="tabpanel"
          aria-labelledby="api-tab-intensity"
          // biome-ignore lint/a11y/noNoninteractiveTabindex: WAI-ARIA tabpanel pattern requires tabIndex=0 so Tab from the tablist moves focus into the panel
          tabIndex={0}
          style={{ ...card, marginBottom: "2rem" }}
        >
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>
            GET /api/v1/carbon/{"{provider}"}/{"{region}"}
          </h2>
          <p
            style={{
              color: "var(--gray-500)",
              fontSize: "0.85rem",
              margin: "0 0 1rem",
            }}
          >
            Get the latest carbon intensity for any cloud region.
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
              <label style={labelStyle} htmlFor="api-provider">
                Cloud Provider
              </label>
              <select
                id="api-provider"
                aria-label="Cloud provider"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setRegion(POPULAR_REGIONS[e.target.value]?.[0] || "");
                }}
                style={inputStyle}
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>
                    {p.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle} htmlFor="api-region">
                Region
              </label>
              <select
                id="api-region"
                aria-label="Region"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                style={inputStyle}
              >
                {(allRegions || [])
                  .filter((r) => r.provider === provider)
                  .map((r) => (
                    <option key={r.region} value={r.region}>
                      {r.region} ({r.location})
                    </option>
                  ))}
                {!allRegions &&
                  POPULAR_REGIONS[provider]?.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          {/* curl example */}
          <div style={codeBlockStyle}>
            <code>
              curl {API_BASE}/api/v1/carbon/{provider}/{region}
            </code>
          </div>

          <button
            type="button"
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
        <div
          role="tabpanel"
          aria-labelledby="api-tab-route"
          // biome-ignore lint/a11y/noNoninteractiveTabindex: WAI-ARIA tabpanel pattern requires tabIndex=0 so Tab from the tablist moves focus into the panel
          tabIndex={0}
          style={{ ...card, marginBottom: "2rem" }}
        >
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>POST /api/v1/route</h2>
          <p
            style={{
              color: "var(--gray-500)",
              fontSize: "0.85rem",
              margin: "0 0 1rem",
            }}
          >
            Find the greenest cloud region across all providers right now.
          </p>

          <div style={codeBlockStyle}>
            <code style={{ whiteSpace: "pre" }}>{`curl -X POST ${API_BASE}/api/v1/route \\
  -H "Content-Type: application/json" \\
  -d '{"constraints": {"providers": ["aws","gcp","azure"], "carbon_weight": 1.0}}'`}</code>
          </div>

          <button
            type="button"
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
        <div
          role="tabpanel"
          aria-labelledby="api-tab-batch"
          // biome-ignore lint/a11y/noNoninteractiveTabindex: WAI-ARIA tabpanel pattern requires tabIndex=0 so Tab from the tablist moves focus into the panel
          tabIndex={0}
          style={{ ...card, marginBottom: "2rem" }}
        >
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>POST /api/v1/carbon/batch</h2>
          <p
            style={{
              color: "var(--gray-500)",
              fontSize: "0.85rem",
              margin: "0 0 1rem",
            }}
          >
            Query multiple regions in a single call. Returns carbon data for each.
          </p>

          <div style={codeBlockStyle}>
            <code style={{ whiteSpace: "pre" }}>{`curl -X POST ${API_BASE}/api/v1/carbon/batch \\
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
            type="button"
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
                      <TableHeadCell label="Region" />
                      <TableHeadCell label="gCO₂/kWh" tip={EMISSIONS_TIP} align="right" />
                      <TableHeadCell label="Renewable %" tip={TABLE_RENEWABLE_TIP} align="right" />
                      <TableHeadCell label="Source" tip={SOURCE_TIP} />
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(batchMutation.data)
                      .sort(
                        ([, a], [, b]) => a.carbon_intensity_gco2_kwh - b.carbon_intensity_gco2_kwh,
                      )
                      .map(([key, val]) => (
                        <tr key={key} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                          <td
                            style={{
                              ...td,
                              fontFamily: "var(--mono)",
                              fontSize: "0.8rem",
                            }}
                          >
                            {key}
                          </td>
                          <td
                            style={{
                              ...td,
                              textAlign: "right",
                              fontWeight: 600,
                              color: intensityVarColor(val.carbon_intensity_gco2_kwh),
                            }}
                          >
                            {val.carbon_intensity_gco2_kwh}
                          </td>
                          <td
                            style={{
                              ...td,
                              textAlign: "right",
                              color:
                                val.renewable_percentage >= 70 ? "var(--green-text)" : "inherit",
                            }}
                          >
                            {val.renewable_percentage}%
                          </td>
                          <td
                            style={{
                              ...td,
                              fontSize: "0.8rem",
                              color: "var(--gray-500)",
                            }}
                          >
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
            <StatCard
              label="Carbon emissions"
              value={`${intensityResult.carbon_intensity_gco2_kwh}`}
              unit="gCO₂/kWh"
              positive={intensityResult.carbon_intensity_gco2_kwh <= 100}
              tip={EMISSIONS_TIP}
            />
            <StatCard
              label="Renewable"
              value={`${intensityResult.renewable_percentage}`}
              unit="%"
              positive={intensityResult.renewable_percentage >= 50}
              tip={TABLE_RENEWABLE_TIP}
            />
            <StatCard label="Grid Zone" value={intensityResult.grid_zone} tip={GRID_ZONE_TIP} />
            <StatCard label="Data Source" value={intensityResult.source} tip={SOURCE_TIP} />
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
          <h3 style={{ margin: "0 0 1rem", fontSize: "1rem" }}>Greenest Region Right Now</h3>
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
                <div style={{ fontWeight: 700, color: "var(--green-text)" }}>
                  {routeResult.recommended.carbon_intensity_gco2_kwh} gCO₂/kWh
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Renewable</div>
                <div style={{ fontWeight: 700, color: "var(--green-text)" }}>
                  {routeResult.recommended.renewable_percentage}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Savings</div>
                <div style={{ fontWeight: 700, color: "var(--green-text)" }}>
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
                      <TableHeadCell label="Provider" />
                      <TableHeadCell label="Region" />
                      <TableHeadCell label="gCO₂/kWh" tip={EMISSIONS_TIP} align="right" />
                      <TableHeadCell label="Renewable %" tip={TABLE_RENEWABLE_TIP} align="right" />
                    </tr>
                  </thead>
                  <tbody>
                    {routeResult.alternatives.slice(0, 10).map((alt) => (
                      <tr
                        key={`${alt.provider}-${alt.region}`}
                        style={{ borderBottom: "1px solid var(--gray-100)" }}
                      >
                        <td
                          style={{
                            ...td,
                            fontWeight: 600,
                            textTransform: "uppercase",
                            fontSize: "0.8rem",
                          }}
                        >
                          {alt.provider}
                        </td>
                        <td
                          style={{
                            ...td,
                            fontFamily: "var(--mono)",
                            fontSize: "0.8rem",
                          }}
                        >
                          {alt.region}
                        </td>
                        <td
                          style={{
                            ...td,
                            textAlign: "right",
                            fontWeight: 600,
                            color: intensityVarColor(alt.carbon_intensity_gco2_kwh),
                          }}
                        >
                          {alt.carbon_intensity_gco2_kwh}
                        </td>
                        <td
                          style={{
                            ...td,
                            textAlign: "right",
                            color: alt.renewable_percentage >= 70 ? "var(--green-text)" : "inherit",
                          }}
                        >
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
    background: "var(--btn-green)",
    color: "white",
    fontWeight: 600,
    cursor: pending ? "wait" : "pointer",
  };
}
