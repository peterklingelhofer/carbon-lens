import { useState } from "react";
import { api } from "../api/client";
import type { RouteResponse } from "../api/types";
import { section as sectionFn, card } from "../styles";

const section = sectionFn();

function intensityLabel(val: number): { label: string; color: string } {
  if (val <= 50) return { label: "Very Clean", color: "var(--green-600)" };
  if (val <= 150) return { label: "Clean", color: "var(--green-500)" };
  if (val <= 300) return { label: "Moderate", color: "var(--yellow-400)" };
  if (val <= 500) return { label: "Dirty", color: "var(--orange-400)" };
  return { label: "Very Dirty", color: "var(--red-500)" };
}

export function RouteDemo() {
  const [providers, setProviders] = useState<string[]>(["aws", "gcp", "azure"]);
  const [residency, setResidency] = useState("");
  const [carbonWeight, setCarbonWeight] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RouteResponse | null>(null);
  const [error, setError] = useState("");

  const toggleProvider = (p: string) => {
    setProviders((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
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
          carbon_weight: carbonWeight,
          cost_weight: Math.round((1 - carbonWeight) * 100) / 100,
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
      <h1 style={{ marginBottom: "0.5rem" }}>Green Route Demo</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Find the greenest cloud region for your workload right now.
      </p>

      {/* Form */}
      <div style={card}>
        <h3 style={{ marginTop: 0, marginBottom: "1rem" }}>Configure Routing</h3>

        {/* Providers */}
        <div style={{ marginBottom: "1.25rem" }}>
          <label style={{ fontWeight: 600, display: "block", marginBottom: "0.5rem" }}>
            Cloud Providers
          </label>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {["aws", "gcp", "azure"].map((p) => (
              <button
                key={p}
                onClick={() => toggleProvider(p)}
                style={{
                  padding: "0.5rem 1.25rem",
                  borderRadius: 6,
                  border: "2px solid",
                  borderColor: providers.includes(p)
                    ? "var(--green-500)"
                    : "var(--gray-200)",
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
        </div>

        {/* Data Residency */}
        <div style={{ marginBottom: "1.25rem" }}>
          <label style={{ fontWeight: 600, display: "block", marginBottom: "0.5rem" }}>
            Data Residency (optional)
          </label>
          <select
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

        {/* Carbon Weight */}
        <div style={{ marginBottom: "1.5rem" }}>
          <label style={{ fontWeight: 600, display: "block", marginBottom: "0.5rem" }}>
            Optimization Priority
          </label>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <span style={{ fontSize: "0.85rem", color: "var(--gray-500)" }}>Cost</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={carbonWeight}
              onChange={(e) => setCarbonWeight(parseFloat(e.target.value))}
              style={{ flex: 1 }}
            />
            <span style={{ fontSize: "0.85rem", color: "var(--green-600)", fontWeight: 600 }}>
              Carbon
            </span>
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--gray-400)", marginTop: "0.25rem" }}>
            Carbon: {(carbonWeight * 100).toFixed(0)}% / Cost:{" "}
            {((1 - carbonWeight) * 100).toFixed(0)}%
          </div>
        </div>

        <button
          onClick={handleRoute}
          disabled={loading}
          style={{
            padding: "0.75rem 2rem",
            borderRadius: 8,
            border: "none",
            background: loading ? "var(--gray-300)" : "var(--green-600)",
            color: "white",
            fontWeight: 600,
            fontSize: "1rem",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Routing..." : "Find Greenest Region"}
        </button>

        {error && (
          <p style={{ color: "var(--red-500)", marginTop: "1rem" }}>{error}</p>
        )}
      </div>

      {/* Result */}
      {result && (
        <>
          <div
            style={{
              ...card,
              background: "linear-gradient(135deg, var(--green-50), var(--surface))",
              borderColor: "var(--green-200)",
            }}
          >
            <div style={{ fontSize: "0.8rem", color: "var(--gray-500)", marginBottom: "0.25rem" }}>
              Recommended Region
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "1rem", flexWrap: "wrap" }}>
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
                style={{
                  ...intensityLabel(result.recommended.carbon_intensity_gco2_kwh),
                  fontWeight: 600,
                  fontSize: "0.9rem",
                } as React.CSSProperties}
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
                <div style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>
                  Carbon Intensity
                </div>
                <div style={{ fontWeight: 600 }}>
                  {result.recommended.carbon_intensity_gco2_kwh} gCO2/kWh
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>Renewable %</div>
                <div
                  style={{
                    fontWeight: 600,
                    color:
                      result.recommended.renewable_percentage >= 70
                        ? "var(--green-600)"
                        : "inherit",
                  }}
                >
                  {result.recommended.renewable_percentage}%
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>
                  Carbon Savings
                </div>
                <div style={{ fontWeight: 600, color: "var(--green-600)" }}>
                  {result.recommended.carbon_savings_vs_worst_pct.toFixed(1)}% greener
                </div>
              </div>
            </div>
          </div>

          {/* Alternatives */}
          {result.alternatives.length > 0 && (
            <div style={card}>
              <h3 style={{ marginTop: 0 }}>
                Alternatives ({result.alternatives.length})
              </h3>
              <div style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                      <th style={{ textAlign: "left", padding: "0.5rem" }}>#</th>
                      <th style={{ textAlign: "left", padding: "0.5rem" }}>Region</th>
                      <th style={{ textAlign: "left", padding: "0.5rem" }}>Grid Zone</th>
                      <th style={{ textAlign: "right", padding: "0.5rem" }}>gCO2/kWh</th>
                      <th style={{ textAlign: "right", padding: "0.5rem" }}>Renewable</th>
                      <th style={{ textAlign: "right", padding: "0.5rem" }}>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.alternatives.slice(0, 15).map((alt, i) => (
                      <tr
                        key={`${alt.provider}-${alt.region}`}
                        style={{ borderBottom: "1px solid var(--gray-100)" }}
                      >
                        <td style={{ padding: "0.5rem", color: "var(--gray-400)" }}>
                          {i + 2}
                        </td>
                        <td style={{ padding: "0.5rem", fontFamily: "var(--mono)" }}>
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
              {`curl -X POST http://localhost:8000/api/v1/route \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(
    {
      constraints: {
        providers,
        ...(residency ? { data_residency: [residency] } : {}),
        carbon_weight: carbonWeight,
        cost_weight: Math.round((1 - carbonWeight) * 100) / 100,
      },
    },
    null,
    2
  )}'`}
            </pre>
          </div>
        </>
      )}
    </div>
  );
}
