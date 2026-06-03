import { useQuery } from "@tanstack/react-query";
import type { HealthResponse } from "../api/types";
import { useSnapshot, snapshotEnabled } from "../api/snapshot";
import { InfoTip } from "../components/InfoTip";
import { section as sectionFn, card } from "../styles";
import { timeAgo } from "../lib/format";
import { DATA_QUALITY_TIP } from "../copy";

const section = sectionFn();
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface ProvidersResponse {
  configured: Record<string, boolean>;
  missing: Record<string, boolean>;
  total_configured: number;
  total_available: number;
}

// Single, no-retry probe of the API with a short timeout. If it succeeds we show
// the live System Status + Provider cards; if it fails for ANY reason (cold start,
// or a browser/extension blocking the cross-origin request — e.g. Firefox ETP +
// uBlock), we silently fall back to the snapshot-only view. No retry storm, no
// endless spinner — at most one failed request in the console for blocked users.
async function probeApi(): Promise<{ health: HealthResponse; providers: ProvidersResponse }> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);
  try {
    const get = async <T,>(path: string): Promise<T> => {
      const res = await fetch(`${API_BASE}${path}`, { signal: ctrl.signal });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<T>;
    };
    const [health, providers] = await Promise.all([
      get<HealthResponse>("/health"),
      get<ProvidersResponse>("/health/providers"),
    ]);
    return { health, providers };
  } finally {
    clearTimeout(timer);
  }
}

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
  const { data: snapshot } = useSnapshot();

  // One shot, no retries — see probeApi() above.
  const { data: api } = useQuery({
    queryKey: ["api-probe"],
    queryFn: probeApi,
    retry: false,
    staleTime: 5 * 60 * 1000,
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
        How fresh the data is and where it comes from. The public API is free and open —
        no key required — and rate-limited to keep it responsive for everyone. Browse
        every endpoint in the{" "}
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

      {/* System Status — only rendered if the one-shot API probe succeeded. */}
      {api && (
        <div style={card}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>System Status</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase" }}>API</div>
              <div style={{ fontWeight: 600, color: api.health.status === "ok" ? "var(--green-text)" : "var(--orange-400)" }}>
                <StatusDot ok={api.health.status === "ok"} />
                {api.health.status === "ok" ? "operational" : api.health.status}
              </div>
            </div>
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase" }}>Version</div>
              <div style={{ fontWeight: 600 }}>{api.health.version}</div>
            </div>
            <div>
              <div style={{ fontSize: "0.75rem", color: "var(--gray-500)", textTransform: "uppercase", display: "inline-flex", alignItems: "center" }}>
                Carbon Source
                <InfoTip label="carbon source" text="Which data-source mode the API is running. 'hybrid' cascades through all providers (live feeds first, then estimates) — the normal setting." />
              </div>
              <div style={{ fontWeight: 600 }}>{api.health.carbon_source}</div>
            </div>
          </div>
        </div>
      )}

      {/* Live data — from the published snapshot (GitHub CDN). Always available,
          no cross-origin API call. Mirrors the globe's live-vs-estimated readout. */}
      <div style={card}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem", display: "flex", alignItems: "center" }}>
          Live data
          <InfoTip label="live vs estimated" text={DATA_QUALITY_TIP} />
        </h2>
        {snapshot ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem" }}>
              <Stat label="Grid zones live" value={snapshot.summary.live_zones} positive />
              <Stat label="Estimated" value={snapshot.summary.estimated_zones} />
              <Stat label="Cloud regions" value={snapshot.regions.length} />
              <Stat label="Updated" value={timeAgo(snapshot.generated_at)} />
            </div>
            <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "1rem 0 0" }}>
              Real grid-operator data, refreshed periodically from a scheduled job — never
              mock data. "Estimated" zones (no live feed available) are clearly labelled
              wherever they appear.
            </p>
          </>
        ) : !snapshotEnabled ? (
          <p style={{ color: "var(--gray-500)", fontSize: "0.9rem" }}>
            Live-data snapshot isn't configured for this deployment.
          </p>
        ) : (
          <p style={{ color: "var(--gray-400)" }}>Loading…</p>
        )}
      </div>

      {/* Provider status — only rendered if the one-shot API probe succeeded. */}
      {api && (
        <div style={card}>
          <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>
            Carbon Data Providers
            <span style={{ fontWeight: 400, fontSize: "0.85rem", color: "var(--gray-500)", marginLeft: 8 }}>
              {api.providers.total_configured}/{api.providers.total_available} active
            </span>
          </h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Providers with credentials deliver real-time grid data. No-key providers work out of the box.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "0.5rem" }}>
            {Object.entries(api.providers.configured).map(([name]) => (
              <div key={name} style={{ padding: "0.5rem", display: "flex", alignItems: "center" }}>
                <StatusDot ok={true} />
                <span style={{ fontSize: "0.9rem" }}>{name}</span>
              </div>
            ))}
            {Object.entries(api.providers.missing).map(([name]) => (
              <div key={name} style={{ padding: "0.5rem", display: "flex", alignItems: "center" }}>
                <StatusDot ok={false} />
                <span style={{ fontSize: "0.9rem", color: "var(--gray-500)" }}>{name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
