import { REPORT_URL, useCleanComputeHistory, useCleanComputeReport } from "../api/report";
import { MiniSparkline } from "../components/MiniSparkline";
import { timeAgo } from "../lib/format";

// A public, citable "State of Clean Compute": which grids reward carbon-aware
// scheduling most (biggest intra-day swing) and which regions are greenest to host
// on (lowest typical intensity), from the published rolling history.
export function CleanCompute() {
  const { data, isLoading, isError } = useCleanComputeReport();
  const { data: history } = useCleanComputeHistory();
  const trend = (history?.days ?? []).filter((d) => d.greenest_mean_gco2_kwh != null);
  const cal = data?.forecast_calibration;
  const calVerdict =
    cal && cal.calibration_ratio >= 0.85 && cal.calibration_ratio <= 1.15
      ? "well-calibrated"
      : cal && cal.calibration_ratio < 0.85
        ? "over-promised"
        : "under-promised";

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

      {trend.length >= 2 && (
        <section style={{ marginBottom: "2rem" }}>
          <h2 style={{ fontSize: "1.15rem", margin: "0 0 0.25rem" }}>Trend</h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "0 0 0.5rem" }}>
            Average typical intensity of the greenest regions, by day — is clean compute getting
            cleaner?
          </p>
          <MiniSparkline
            values={trend.map((d) => d.greenest_mean_gco2_kwh as number)}
            labels={trend.map((d) => d.date.slice(5))}
            mark="last"
            ariaLabel="Greenest-region average carbon intensity over time"
          />
          <div style={{ fontSize: "0.65rem", color: "var(--gray-400)", marginTop: 2 }}>
            {trend.length} days · lower is cleaner
          </div>
        </section>
      )}

      {cal && cal.samples > 0 && (
        <section style={{ marginBottom: "2rem" }}>
          <h2 style={{ fontSize: "1.15rem", margin: "0 0 0.25rem" }}>Forecast accuracy</h2>
          <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: "0 0 0.5rem" }}>
            How submit-time predicted reductions compared to the run-time re-measured actuals,
            across {cal.samples} verified shifted run{cal.samples === 1 ? "" : "s"} — the honest
            counterpart to any avoided-CO₂ claim.
          </p>
          <p style={{ fontSize: "0.95rem", margin: 0 }}>
            Calibration ratio <strong>{cal.calibration_ratio.toFixed(2)}</strong>{" "}
            <span
              style={{
                color: calVerdict === "well-calibrated" ? "var(--green-text)" : "#b45309",
              }}
            >
              ({calVerdict})
            </span>
            <span style={{ color: "var(--gray-500)" }}>
              {" "}
              · predicted {Math.round(cal.mean_predicted_gco2_kwh)} vs actual{" "}
              {Math.round(cal.mean_actual_gco2_kwh)} gCO₂/kWh · mean error ±
              {Math.round(cal.mean_abs_error_gco2_kwh)}
            </span>
          </p>
        </section>
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
                  {r.trend_pct != null && Math.abs(r.trend_pct) >= 1 && (
                    <span
                      style={{
                        marginLeft: 6,
                        fontSize: "0.78rem",
                        color: r.trend_pct < 0 ? "var(--green-text)" : "#b45309",
                      }}
                      title="Trend over the analysed window (negative = getting cleaner)"
                    >
                      {r.trend_pct < 0 ? "↓" : "↑"} {Math.abs(Math.round(r.trend_pct))}%
                    </span>
                  )}
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
