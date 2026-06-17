import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { InfoTip } from "./InfoTip";

// "Where carbon-aware scheduling helps most" — grid zones ranked by how much a daily
// job would save shifting from its dirtiest to cleanest hour. High = a big intra-day
// swing (variable wind/solar) so timing matters; low = flat grids where it barely
// helps. From /carbon/shiftability; hidden until enough history has accumulated.
export function ShiftabilityPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["shiftability"],
    queryFn: () => api.shiftability(14, 10),
    staleTime: 60 * 60_000,
    retry: 1,
  });

  if (isLoading || isError || !data || data.zones.length === 0) return null;
  const max = data.zones[0].shift_savings_pct || 1;

  return (
    <div style={{ marginTop: "2rem" }}>
      <h2
        style={{
          fontSize: "1.1rem",
          margin: "0 0 0.25rem",
          display: "inline-flex",
          alignItems: "center",
        }}
      >
        Where carbon-aware scheduling helps most
        <InfoTip
          label="shiftability"
          text="For each grid zone, how much a daily job would save by running at its cleanest hour instead of its dirtiest, from the last 14 days of history. High means a big intra-day swing (lots of variable wind/solar) so timing pays off; near zero means a flat grid where shifting barely helps. It tells you where the effort is worth it."
        />
      </h2>
      <p style={{ fontSize: "0.8rem", color: "var(--gray-500)", margin: "0 0 0.75rem" }}>
        % a daily job would save by shifting from the dirtiest to the cleanest hour (UTC).
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {data.zones.map((z) => (
          <div key={z.grid_zone} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 200, fontSize: "0.82rem" }}>
              <span style={{ fontWeight: 600 }}>{z.grid_zone}</span>{" "}
              <span style={{ color: "var(--gray-500)" }}>{z.location}</span>
            </div>
            <div style={{ flex: 1, background: "var(--gray-200)", borderRadius: 4, height: 14 }}>
              <div
                style={{
                  width: `${Math.max(2, (z.shift_savings_pct / max) * 100)}%`,
                  height: "100%",
                  borderRadius: 4,
                  background: "var(--btn-green)",
                }}
              />
            </div>
            <div style={{ width: 96, textAlign: "right", fontSize: "0.82rem" }}>
              <span style={{ color: "var(--green-text)", fontWeight: 600 }}>
                {Math.round(z.shift_savings_pct)}%
              </span>{" "}
              <span style={{ color: "var(--gray-400)", fontSize: "0.7rem" }}>
                {String(z.cleanest_hour_utc).padStart(2, "0")}h
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
