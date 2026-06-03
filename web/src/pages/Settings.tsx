import { useSnapshot, snapshotEnabled } from "../api/snapshot";
import { section as sectionFn, card } from "../styles";

const section = sectionFn();
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
}

function Stat({ label, value, positive }: { label: string; value: string | number; positive?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: "1.5rem", color: positive ? "var(--green-text)" : "inherit" }}>
        {value}
      </div>
    </div>
  );
}

export function Settings() {
  const { data: snapshot, isLoading, isError } = useSnapshot();

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
        Where every reading comes from, and how fresh it is. The public API is free and
        open — no key required — and rate-limited to keep it responsive for everyone.
        Browse every endpoint in the{" "}
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--green-text)", fontWeight: 600, textDecoration: "underline" }}
        >
          interactive Swagger docs ↗
        </a>
        .
      </p>

      {/* Live data freshness — read from the published snapshot (GitHub CDN), so it
          has no API cold-start or CORS dependency and always loads. */}
      <div style={card}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Live data</h2>
        {snapshot ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem" }}>
              <Stat label="Grid zones live" value={snapshot.summary.live_zones} positive />
              <Stat label="Estimated" value={snapshot.summary.estimated_zones} />
              <Stat label="Cloud regions" value={snapshot.regions.length} />
              <Stat label="Updated" value={timeAgo(snapshot.generated_at)} />
            </div>
            <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "1rem 0 0" }}>
              Real grid-operator data, refreshed roughly every 30 minutes from a scheduled
              job — never mock data. "Estimated" zones (no live feed available) are clearly
              labelled wherever they appear.
            </p>
          </>
        ) : !snapshotEnabled ? (
          <p style={{ color: "var(--gray-500)", fontSize: "0.9rem" }}>
            Live-data snapshot isn't configured for this deployment.
          </p>
        ) : isError ? (
          <p style={{ color: "var(--gray-500)", fontSize: "0.9rem" }}>
            Couldn't load the data snapshot just now — refresh to try again.
          </p>
        ) : (
          <p style={{ color: "var(--gray-400)" }}>{isLoading ? "Loading…" : "—"}</p>
        )}
      </div>

      {/* Data sources */}
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
