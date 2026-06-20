import { useState } from "react";
import { API_BASE, api } from "../api/client";
import type { RouteResponse } from "../api/types";
import { InfoTip } from "../components/InfoTip";
import { RegionComparison } from "../components/RegionComparison";
import { TableHeadCell } from "../components/TableHeadCell";
import { EMISSIONS_TIP, GRID_ZONE_TIP, TABLE_RENEWABLE_TIP } from "../copy";
import { intensityLabel } from "../lib/intensity";
import { card, sectionStyle } from "../styles";

const section = sectionStyle();

export function RouteDemo() {
  const [providers, setProviders] = useState<string[]>(["aws", "gcp", "azure"]);
  const [residency, setResidency] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RouteResponse | null>(null);
  const [error, setError] = useState("");

  const toggleProvider = (p: string) => {
    setProviders((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
  };

  const handleRoute = async () => {
    if (providers.length === 0) {
      setError("Select at least one provider.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.route({
        constraints: {
          providers,
          data_residency: residency ? [residency] : undefined,
          carbon_weight: 1.0,
        },
      });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={section}>
      <h1
        style={{
          marginBottom: "0.5rem",
          display: "flex",
          alignItems: "center",
        }}
      >
        Green route demo
        <InfoTip
          label="green route"
          text="Routing means choosing where to run a workload. This ranks every eligible region by your priorities and returns the greenest match. It's a recommendation you'd act on yourself (e.g. in a deploy script) - nothing is deployed or run here."
        />
      </h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Choose providers and how much to favour clean energy over cost, and see which region comes
        out greenest right now.
      </p>

      <RegionComparison />

      {/* Form */}
      <div style={card}>
        <h3 style={{ marginTop: 0, marginBottom: "1rem" }}>Configure Routing</h3>

        {/* Providers */}
        <fieldset style={{ border: "none", margin: "0 0 1.25rem", padding: 0, minWidth: 0 }}>
          <legend
            style={{
              fontWeight: 600,
              display: "block",
              marginBottom: "0.5rem",
            }}
          >
            Cloud Providers
          </legend>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {["aws", "gcp", "azure", "scaleway", "ovh", "hetzner"].map((p) => (
              <button
                type="button"
                key={p}
                onClick={() => toggleProvider(p)}
                aria-pressed={providers.includes(p)}
                style={{
                  padding: "0.5rem 1.25rem",
                  borderRadius: 6,
                  border: "2px solid",
                  borderColor: providers.includes(p) ? "var(--green-500)" : "var(--gray-200)",
                  background: providers.includes(p) ? "var(--green-50)" : "var(--surface)",
                  color: providers.includes(p) ? "var(--green-800)" : "var(--gray-600)",
                  cursor: "pointer",
                  fontWeight: 600,
                  textTransform: "uppercase",
                }}
              >
                {p}
              </button>
            ))}
          </div>
        </fieldset>

        {/* Data Residency */}
        <div style={{ marginBottom: "1.25rem" }}>
          <span
            style={{
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              marginBottom: "0.5rem",
            }}
          >
            Data Residency (optional)
            <InfoTip
              label="data residency"
              text="A rule about where your data is legally allowed to live - e.g. 'EU only' for GDPR. Restricting residency limits routing to regions in that area, so the greenest pick may differ."
            />
          </span>
          <select
            aria-label="Data residency"
            value={residency}
            onChange={(e) => setResidency(e.target.value)}
            style={{
              padding: "0.5rem 1rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              fontSize: "0.95rem",
              width: 200,
            }}
          >
            <option value="">Any region</option>
            <option value="US">US only</option>
            <option value="EU">EU only</option>
            <option value="CA">Canada only</option>
            <option value="AP">Asia-Pacific</option>
          </select>
        </div>

        {/* Ranking basis - honest about what the engine actually optimizes */}
        <div
          style={{
            marginBottom: "1.5rem",
            fontSize: "0.85rem",
            color: "var(--gray-500)",
          }}
        >
          Regions are ranked by{" "}
          <strong style={{ color: "var(--green-text)" }}>lowest carbon intensity</strong> right now,
          within your provider and residency filters. Cost-aware ranking (trading carbon against
          price) is on the roadmap - it isn't factored in yet.
        </div>

        <button
          type="button"
          onClick={handleRoute}
          disabled={loading}
          style={{
            padding: "0.75rem 2rem",
            borderRadius: 8,
            border: "none",
            background: loading ? "var(--gray-300)" : "var(--btn-green)",
            color: "white",
            fontWeight: 600,
            fontSize: "1rem",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Routing..." : "Find Greenest Region"}
        </button>

        {error && (
          <p role="alert" style={{ color: "var(--red-500)", marginTop: "1rem" }}>
            {error}
          </p>
        )}
      </div>

      {/* Result */}
      {result && (
        <>
          <div
            style={{
              ...card,
              // A translucent green wash over the theme-aware --card-bg, NOT the
              // fixed light --green-50 (which doesn't remap for dark mode and left
              // the adaptive light text invisible on a near-white corner).
              background:
                "linear-gradient(135deg, rgba(34,197,94,0.12), transparent), var(--card-bg)",
              borderColor: "var(--green-200)",
            }}
          >
            <div
              style={{
                fontSize: "0.8rem",
                color: "var(--gray-500)",
                marginBottom: "0.25rem",
              }}
            >
              Recommended Region
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: "1rem",
                flexWrap: "wrap",
              }}
            >
              <span
                style={{
                  fontSize: "1.5rem",
                  fontWeight: 700,
                  fontFamily: "var(--mono)",
                  color: "var(--green-800)",
                }}
              >
                {result.recommended.provider}/{result.recommended.region}
              </span>
              <span
                style={
                  {
                    ...intensityLabel(result.recommended.carbon_intensity_gco2_kwh),
                    fontWeight: 600,
                    fontSize: "0.9rem",
                  } as React.CSSProperties
                }
              >
                {intensityLabel(result.recommended.carbon_intensity_gco2_kwh).label}
              </span>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: "1rem",
                marginTop: "1.5rem",
              }}
            >
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>Grid Zone</div>
                <div style={{ fontWeight: 600 }}>{result.recommended.grid_zone}</div>
              </div>
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--gray-500)",
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                >
                  Carbon emissions
                  <InfoTip label="Carbon emissions" text={EMISSIONS_TIP} />
                </div>
                <div style={{ fontWeight: 600 }}>
                  {result.recommended.carbon_intensity_gco2_kwh} gCO₂/kWh
                </div>
              </div>
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--gray-500)",
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                >
                  Renewable %<InfoTip label="Renewable %" text={TABLE_RENEWABLE_TIP} />
                </div>
                <div
                  style={{
                    fontWeight: 600,
                    color:
                      result.recommended.renewable_percentage >= 70
                        ? "var(--green-text)"
                        : "inherit",
                  }}
                >
                  {result.recommended.renewable_percentage}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>Carbon Savings</div>
                <div style={{ fontWeight: 600, color: "var(--green-text)" }}>
                  {result.recommended.carbon_savings_vs_worst_pct.toFixed(1)}% greener
                </div>
              </div>
            </div>

            <p
              style={{
                margin: "1rem 0 0",
                fontSize: "0.78rem",
                color: "var(--gray-500)",
                lineHeight: 1.5,
              }}
            >
              Ranked by <strong>carbon intensity</strong> - which counts nuclear and hydro, not just
              renewables - so the greenest pick can show a lower renewable % than an alternative. To
              rank by renewable share instead, raise its weight in your priorities.
            </p>
          </div>

          {/* Alternatives */}
          {result.alternatives.length > 0 && (
            <div style={card}>
              <h3 style={{ marginTop: 0 }}>Alternatives ({result.alternatives.length})</h3>
              <div style={{ overflow: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: "0.85rem",
                  }}
                >
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                      <TableHeadCell
                        label="#"
                        tip="Rank by your carbon/cost priority. #1 is the recommended region above; these are the next-best."
                      />
                      <TableHeadCell
                        label="Region"
                        tip="The cloud provider and region - e.g. aws / eu-north-1."
                      />
                      <TableHeadCell label="Grid Zone" tip={GRID_ZONE_TIP} />
                      <TableHeadCell label="gCO₂/kWh" tip={EMISSIONS_TIP} align="right" />
                      <TableHeadCell label="Renewable" tip={TABLE_RENEWABLE_TIP} align="right" />
                      <TableHeadCell
                        label="Score"
                        tip="Ranking score derived from carbon intensity (lower = greener). It's a relative ordering within this result set, not a physical unit, and isn't comparable across different queries. Cost is not yet a factor."
                        align="right"
                      />
                    </tr>
                  </thead>
                  <tbody>
                    {result.alternatives.slice(0, 15).map((alt, i) => (
                      <tr
                        key={`${alt.provider}-${alt.region}`}
                        style={{ borderBottom: "1px solid var(--gray-100)" }}
                      >
                        <td
                          style={{
                            padding: "0.5rem",
                            color: "var(--gray-400)",
                          }}
                        >
                          {i + 2}
                        </td>
                        <td
                          style={{
                            padding: "0.5rem",
                            fontFamily: "var(--mono)",
                          }}
                        >
                          {alt.provider}/{alt.region}
                        </td>
                        <td style={{ padding: "0.5rem" }}>{alt.grid_zone}</td>
                        <td
                          style={{
                            padding: "0.5rem",
                            textAlign: "right",
                            color: intensityLabel(alt.carbon_intensity_gco2_kwh).color,
                          }}
                        >
                          {alt.carbon_intensity_gco2_kwh}
                        </td>
                        <td style={{ padding: "0.5rem", textAlign: "right" }}>
                          {alt.renewable_percentage}%
                        </td>
                        <td style={{ padding: "0.5rem", textAlign: "right" }}>
                          {alt.score.toFixed(3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* API request preview */}
          <div style={card}>
            <h3 style={{ marginTop: 0 }}>API Request</h3>
            <pre
              style={{
                background: "var(--surface-alt)",
                padding: "1rem",
                borderRadius: 8,
                overflow: "auto",
                fontSize: "0.8rem",
                fontFamily: "var(--mono)",
                lineHeight: 1.6,
              }}
            >
              {`curl -X POST ${API_BASE}/api/v1/route \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(
    {
      constraints: {
        providers,
        ...(residency ? { data_residency: [residency] } : {}),
        carbon_weight: 1.0,
      },
    },
    null,
    2,
  )}'`}
            </pre>
          </div>
        </>
      )}
    </div>
  );
}
