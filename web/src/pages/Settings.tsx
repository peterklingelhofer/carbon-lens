import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
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
  const { data: providers, isLoading } = useQuery({
    queryKey: ["providers"],
    queryFn: () => api.providers(),
  });

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
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
      <h1 style={{ marginBottom: "0.5rem" }}>Status</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Live system health and the data sources behind every reading. The public API
        is free and open — no key required — and rate-limited to keep it responsive
        for everyone.
      </p>

      {/* System Status */}
      <div style={card}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>System Status</h2>
        {health ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase" }}>Status</div>
              <div style={{ fontWeight: 600, color: health.status === "ok" ? "var(--green-text)" : "var(--orange-400)" }}>
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
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Data Sources & Setup</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
          All data providers are free. A self-hosted deployment adds keys to its <code>.env</code> file or platform dashboard:
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
              { name: "EIA", coverage: "US grid (real-time)", env: "CARBON_LENS_EIA_API_KEY", url: "https://www.eia.gov/opendata/" },
              { name: "GridStatus", coverage: "US ISOs", env: "CARBON_LENS_GRID_STATUS_API_KEY", url: "https://www.gridstatus.io/" },
              { name: "ENTSO-E", coverage: "Europe (35 countries)", env: "CARBON_LENS_ENTSOE_TOKEN", url: "https://transparency.entsoe.eu/" },
              { name: "Electricity Maps", coverage: "Global (paid)", env: "CARBON_LENS_ELECTRICITY_MAPS_API_KEY", url: "https://api-portal.electricitymaps.com/" },
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
                    style={{ color: "var(--green-text)", textDecoration: "none" }}
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
