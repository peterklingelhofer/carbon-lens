import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, getApiKey, setApiKey } from "../api/client";
import { section as sectionFn, card } from "../styles";

const section = sectionFn();

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: ok ? "var(--green-500)" : "var(--gray-300)",
        marginRight: 8,
        verticalAlign: "middle",
      }}
    />
  );
}

export function Settings() {
  const [apiKey, setApiKeyState] = useState(getApiKey());
  const [saved, setSaved] = useState(false);

  function saveApiKey() {
    setApiKey(apiKey.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const { data: providers, isLoading } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.providers(),
  });

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
  });

  const { data: billing } = useQuery({
    queryKey: ["billing-status"],
    queryFn: () => api.billingStatus(),
  });

  return (
    <div style={section}>
      <style>{`
        @media (max-width: 600px) {
          .settings-table { font-size: 0.75rem !important; }
          .settings-table th, .settings-table td { padding: 0.35rem !important; }
          .settings-table code { font-size: 0.65rem !important; word-break: break-all; }
        }
      `}</style>
      <h1 style={{ marginBottom: "0.5rem" }}>Settings</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        System status, provider credentials, and usage overview.
      </p>

      {/* API Key */}
      <div style={card}>
        <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>Your API Key</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          Sent as the <code>X-API-Key</code> header on every request. Stored only in this browser.
          The public demo runs without one; a deployment with{" "}
          <code>CARBON_MESH_API_KEY_REQUIRED=true</code> needs a valid key.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKeyState(e.target.value)}
            placeholder="cmesh_..."
            style={{
              flex: 1,
              minWidth: 240,
              padding: "0.5rem 0.75rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              fontFamily: "var(--mono)",
              fontSize: "0.85rem",
            }}
          />
          <button
            onClick={saveApiKey}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: 6,
              border: "none",
              background: "var(--green-600)",
              color: "white",
              fontWeight: 600,
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            {saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>

      {/* System Status */}
      <div style={card}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>System Status</h2>
        {health ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase" }}>Status</div>
              <div style={{ fontWeight: 600, color: health.status === "ok" ? "var(--green-600)" : "var(--orange-400)" }}>
                {health.status}
              </div>
            </div>
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase" }}>Version</div>
              <div style={{ fontWeight: 600 }}>{health.version}</div>
            </div>
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase" }}>Carbon Source</div>
              <div style={{ fontWeight: 600 }}>{health.carbon_source}</div>
            </div>
          </div>
        ) : (
          <p style={{ color: "var(--gray-400)" }}>Loading...</p>
        )}
      </div>

      {/* Usage */}
      {billing && (
        <div style={card}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Today's Usage</h2>
          <div style={{ display: "flex", alignItems: "center", gap: "1.5rem", flexWrap: "wrap" }}>
            <div>
              <span style={{ fontSize: "2rem", fontWeight: 700, color: "var(--green-700)" }}>
                {billing.today_usage}
              </span>
              <span style={{ color: "var(--gray-500)", marginLeft: 4 }}>
                / {billing.daily_limit.toLocaleString()}
              </span>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div
                style={{
                  height: 8,
                  borderRadius: 4,
                  background: "var(--gray-100)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${Math.min((billing.today_usage / billing.daily_limit) * 100, 100)}%`,
                    borderRadius: 4,
                    background:
                      billing.today_usage / billing.daily_limit > 0.9
                        ? "var(--red-400)"
                        : "var(--green-500)",
                    transition: "width 0.3s",
                  }}
                />
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", marginTop: 4 }}>
                {billing.remaining.toLocaleString()} requests remaining ({billing.tier} tier)
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Provider Status */}
      <div style={card}>
        <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>
          Carbon Data Providers
          {providers && (
            <span style={{ fontWeight: 400, fontSize: "0.85rem", color: "var(--gray-500)", marginLeft: 8 }}>
              {providers.total_configured}/{providers.total_available} active
            </span>
          )}
        </h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          Providers with credentials deliver real-time grid data. No-key providers work out of the box.
        </p>

        {isLoading ? (
          <p style={{ color: "var(--gray-400)" }}>Loading provider status...</p>
        ) : providers ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "0.5rem" }}>
            {Object.entries(providers.configured).map(([name]) => (
              <div key={name} style={{ padding: "0.5rem", display: "flex", alignItems: "center" }}>
                <StatusDot ok={true} />
                <span style={{ fontSize: "0.9rem" }}>{name}</span>
              </div>
            ))}
            {Object.entries(providers.missing).map(([name]) => (
              <div key={name} style={{ padding: "0.5rem", display: "flex", alignItems: "center" }}>
                <StatusDot ok={false} />
                <span style={{ fontSize: "0.9rem", color: "var(--gray-500)" }}>{name}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {/* Setup Guide */}
      <div style={{ ...card, overflow: "auto" }}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Add Provider Credentials</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          All data providers are free. Add API keys to your <code>.env</code> file or platform dashboard:
        </p>
        <table className="settings-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Provider</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Coverage</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Env Variable</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Sign Up</th>
            </tr>
          </thead>
          <tbody>
            {[
              { name: "EIA", coverage: "US grid (real-time)", env: "CARBON_MESH_EIA_API_KEY", url: "https://www.eia.gov/opendata/" },
              { name: "GridStatus", coverage: "US ISOs", env: "CARBON_MESH_GRID_STATUS_API_KEY", url: "https://www.gridstatus.io/" },
              { name: "ENTSO-E", coverage: "Europe (35 countries)", env: "CARBON_MESH_ENTSOE_TOKEN", url: "https://transparency.entsoe.eu/" },
              { name: "Electricity Maps", coverage: "Global (paid)", env: "CARBON_MESH_ELECTRICITY_MAPS_API_KEY", url: "https://api-portal.electricitymaps.com/" },
            ].map((p) => (
              <tr key={p.name} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                <td style={{ padding: "0.5rem", fontWeight: 600 }}>{p.name}</td>
                <td style={{ padding: "0.5rem" }}>{p.coverage}</td>
                <td style={{ padding: "0.5rem" }}>
                  <code style={{ fontSize: "0.8rem", background: "var(--surface-alt)", padding: "2px 6px", borderRadius: 4 }}>
                    {p.env}
                  </code>
                </td>
                <td style={{ padding: "0.5rem" }}>
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "var(--green-600)", textDecoration: "none" }}
                  >
                    Get free key
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
