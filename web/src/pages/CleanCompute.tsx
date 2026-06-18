import { REPORT_URL, useCleanComputeReport } from "../api/report";
import { timeAgo } from "../lib/format";

// A public, citable "State of Clean Compute": which grids reward carbon-aware
// scheduling most (biggest intra-day swing) and which regions are greenest to host
// on (lowest typical intensity), from the published rolling history.
export function CleanCompute() {
  const { data, isLoading, isError } = useCleanComputeReport();

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "2rem 1.25rem" }}>
      <h1 style={{ fontSize: "1.6rem", margin: "0 0 0.25rem" }}>State of Clean Compute</h1>
      <p style={{ color: "var(--gray-500)", margin: "0 0 1.5rem", fontSize: "0.95rem" }}>
        Where carbon-aware computing pays off, from the last {data?.days_analyzed ?? 14} days of
        real grid data. Updated about every 30 minutes.{" "}
        {data && <span>Last updated {timeAgo(data.generated_at)}.</span>}
      </p>

      {!REPORT_URL && (
        <p style={{ color: "var(--gray-500)" }}>
          The published report isn't configured for this deployment.
        </p>
      )}
      {REPORT_URL && isLoading && <p style={{ color: "var(--gray-500)" }}>Loading…</p>}
      {REPORT_URL && isError && (
        <p style={{ color: "var(--gray-500)" }}>
          The report is still accumulating — check back once history has built up.
        </p>
      )}

      {data && (
        <div style={{ display: "grid", gap: "2rem" }}>
          <section>
            <h2 style={{ fontSize: "1.15rem", margin: "0 0 0.25rem" }}>
              Greenest regions to deploy
            </h2>
            <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "0 0 0.75rem" }}>
              Lowest typical (history-mean) carbon intensity — the honest basis for a 24/7
              deployment.
            </p>
            <ol style={{ margin: 0, paddingLeft: "1.25rem" }}>
              {data.greenest_regions.map((r) => (
                <li
                  key={`${r.provider}/${r.region}`}
                  style={{ marginBottom: 4, fontSize: "0.9rem" }}
                >
                  <strong>
                    {r.provider}/{r.region}
                  </strong>{" "}
                  <span style={{ color: "var(--gray-500)" }}>{r.location}</span>{" "}
                  <span style={{ color: "var(--green-text)" }}>
                    — {Math.round(r.typical_gco2_kwh)} gCO₂/kWh
                  </span>
                </li>
              ))}
            </ol>
          </section>

          <section>
            <h2 style={{ fontSize: "1.15rem", margin: "0 0 0.25rem" }}>
              Where carbon-aware scheduling helps most
            </h2>
            <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "0 0 0.75rem" }}>
              Biggest intra-day swing — % a daily job would save by running at the cleanest hour vs
              the dirtiest (UTC).
            </p>
            <ol style={{ margin: 0, paddingLeft: "1.25rem" }}>
              {data.most_shiftable.map((g) => (
                <li key={g.grid_zone} style={{ marginBottom: 4, fontSize: "0.9rem" }}>
                  <strong>{g.grid_zone}</strong>{" "}
                  <span style={{ color: "var(--gray-500)" }}>{g.location}</span>{" "}
                  <span style={{ color: "var(--green-text)" }}>
                    — {Math.round(g.shift_savings_pct)}% cleaner
                  </span>{" "}
                  <span style={{ color: "var(--gray-400)", fontSize: "0.8rem" }}>
                    at {String(g.cleanest_hour_utc).padStart(2, "0")}:00 UTC
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </div>
  );
}
