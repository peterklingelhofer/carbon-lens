import { useMutation, useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { api } from "../api/client";
import { InfoTip } from "../components/InfoTip";
import { RENEWABLE_TIP } from "../copy";
import { card, section as sectionFn } from "../styles";

const section = sectionFn(1100);

type Strategy = "lowest_carbon" | "highest_renewable" | "balanced";

const STRATEGIES: { value: Strategy; label: string; desc: string }[] = [
  { value: "lowest_carbon", label: "Lowest Carbon", desc: "Minimize gCO₂/kWh" },
  {
    value: "highest_renewable",
    label: "Highest Renewable",
    desc: "Maximize renewable %",
  },
  { value: "balanced", label: "Balanced", desc: "60% carbon + 40% renewable" },
];

const PROVIDERS = ["aws", "gcp", "azure"];

export function Scheduler() {
  // Find-window form state
  const [duration, setDuration] = useState(30);
  const [maxDelay, setMaxDelay] = useState(24);
  const [strategy, setStrategy] = useState<Strategy>("lowest_carbon");
  const [selectedProviders, setSelectedProviders] = useState<string[]>(["aws", "gcp", "azure"]);

  // Best-now query
  const bestNow = useQuery({
    queryKey: ["scheduler-now"],
    queryFn: () => api.scheduler.bestNow(30, selectedProviders.join(",")),
    refetchInterval: 60000,
  });

  // Find window mutation
  const findWindow = useMutation({
    mutationFn: () =>
      api.scheduler.findWindow({
        job_duration_minutes: duration,
        providers: selectedProviders,
        strategy,
        max_delay_hours: maxDelay,
      }),
  });

  const toggleProvider = (p: string) => {
    setSelectedProviders((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
  };

  const recommendation = findWindow.data;
  const recommended = recommendation?.recommended;
  const alternatives = recommendation?.alternatives ?? [];
  const nowRecommended = bestNow.data?.recommended;

  return (
    <div style={section}>
      <h1
        style={{
          marginBottom: "0.5rem",
          display: "flex",
          alignItems: "center",
        }}
      >
        Carbon-aware scheduler
        <InfoTip
          label="carbon-aware scheduling"
          text="Many jobs don't have to run at a fixed moment — CI/CD pipelines, ML training, nightly batch processing. Carbon-aware scheduling runs them when and where the grid is cleanest, cutting emissions for the same work. This tool finds that window for you; a CI runner or scheduler then executes the job — CarbonLens recommends, it doesn't run anything itself."
        />
      </h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Find the greenest time window and region for flexible jobs like batch processing, CI/CD
        pipelines, and ML training.
      </p>

      {/* Greenest Right Now */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "1rem",
          marginBottom: "2rem",
        }}
      >
        <div style={card}>
          <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.1rem" }}>Greenest Region Now</h2>
          {bestNow.isLoading ? (
            <div style={{ color: "var(--gray-400)", fontSize: "0.85rem" }}>Loading...</div>
          ) : nowRecommended ? (
            <>
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  alignItems: "baseline",
                  marginBottom: "0.5rem",
                }}
              >
                <span
                  style={{
                    fontSize: "1.4rem",
                    fontWeight: 700,
                    color: "var(--green-text)",
                    textTransform: "uppercase",
                  }}
                >
                  {nowRecommended.provider}
                </span>
                <span
                  style={{
                    fontSize: "1rem",
                    fontFamily: "var(--mono)",
                    color: "var(--gray-600)",
                  }}
                >
                  {nowRecommended.region}
                </span>
              </div>
              <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.85rem" }}>
                <span>
                  <strong>{nowRecommended.carbon_intensity_gco2_kwh}</strong> gCO₂/kWh
                </span>
                <span>
                  <strong>{nowRecommended.renewable_percentage}%</strong> renewable
                </span>
              </div>
            </>
          ) : (
            <div style={{ color: "var(--gray-400)", fontSize: "0.85rem" }}>No data</div>
          )}
        </div>

        <div style={card}>
          <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.1rem" }}>How It Works</h2>
          <ol
            style={{
              margin: 0,
              paddingLeft: "1.2rem",
              fontSize: "0.85rem",
              color: "var(--gray-600)",
              lineHeight: 1.8,
            }}
          >
            <li>Set your job duration and max delay tolerance</li>
            <li>Pick a strategy (lowest carbon, highest renewable, or balanced)</li>
            <li>Get the optimal time window and region across all cloud providers</li>
          </ol>
        </div>
      </div>

      {/* Find Optimal Window */}
      <div style={{ ...card, marginBottom: "2rem" }}>
        <h2
          style={{
            margin: "0 0 0.5rem",
            fontSize: "1.1rem",
            display: "flex",
            alignItems: "center",
          }}
        >
          Find Optimal Window
          <InfoTip
            label="how the window is estimated"
            text="Honest caveat: future hours use a simplified time-of-day model (a solar/demand curve applied to the current reading), NOT a real grid forecast — and the curve is keyed to UTC, so per-region local timing is approximate. The 'carbon saved' figure compares the best future slot against the dirtiest candidate region right now. Treat it as directional guidance, not a precise prediction."
          />
        </h2>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
            marginBottom: "1.5rem",
          }}
        >
          {/* Duration */}
          <div>
            <label style={labelStyle}>Job Duration (minutes)</label>
            <input
              type="range"
              aria-label="Job duration in minutes"
              min={5}
              max={480}
              step={5}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={sliderValue}>
              {duration} min ({(duration / 60).toFixed(1)}h)
            </div>
          </div>

          {/* Max Delay */}
          <div>
            <label style={labelStyle}>Max Delay (hours)</label>
            <input
              type="range"
              aria-label="Max delay in hours"
              min={1}
              max={168}
              step={1}
              value={maxDelay}
              onChange={(e) => setMaxDelay(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={sliderValue}>
              {maxDelay}h ({maxDelay <= 24 ? `${maxDelay}h` : `${(maxDelay / 24).toFixed(1)} days`})
            </div>
          </div>

          {/* Strategy */}
          <div>
            <label style={labelStyle}>Strategy</label>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.25rem",
              }}
            >
              {STRATEGIES.map((s) => (
                <label
                  key={s.value}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    padding: "0.25rem 0.5rem",
                    borderRadius: 6,
                    fontWeight: strategy === s.value ? 600 : 400,
                    background: strategy === s.value ? "var(--surface-alt)" : "transparent",
                  }}
                >
                  <input
                    type="radio"
                    name="strategy"
                    checked={strategy === s.value}
                    onChange={() => setStrategy(s.value)}
                  />
                  <span>
                    <strong>{s.label}</strong>
                    <span
                      style={{
                        color: "var(--gray-500)",
                        fontSize: "0.75rem",
                        marginLeft: 4,
                      }}
                    >
                      {s.desc}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Providers */}
          <div>
            <label style={labelStyle}>Cloud Providers</label>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {PROVIDERS.map((p) => (
                <button
                  type="button"
                  key={p}
                  onClick={() => toggleProvider(p)}
                  style={{
                    padding: "0.4rem 0.8rem",
                    borderRadius: 6,
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    textTransform: "uppercase",
                    border: selectedProviders.includes(p)
                      ? "2px solid var(--green-text)"
                      : "2px solid var(--gray-200)",
                    background: selectedProviders.includes(p)
                      ? "var(--green-100)"
                      : "var(--surface)",
                    color: selectedProviders.includes(p) ? "var(--green-700)" : "var(--gray-500)",
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => findWindow.mutate()}
          disabled={findWindow.isPending || selectedProviders.length === 0}
          style={{
            padding: "0.75rem 2rem",
            borderRadius: 8,
            border: "none",
            background: "var(--btn-green)",
            color: "white",
            fontWeight: 600,
            cursor: findWindow.isPending ? "wait" : "pointer",
            fontSize: "0.9rem",
          }}
        >
          {findWindow.isPending ? "Evaluating..." : "Find Greenest Window"}
        </button>
      </div>

      {/* Recommendation */}
      {recommendation && recommended && (
        <div
          style={{
            ...card,
            border: "1px solid var(--green-300)",
            marginBottom: "2rem",
          }}
        >
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>
            Recommended Window
            {recommendation.carbon_saved_vs_now_pct > 0 && (
              <span
                style={{
                  marginLeft: 8,
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "var(--green-text)",
                  background: "var(--green-100)",
                  padding: "2px 8px",
                  borderRadius: 4,
                }}
              >
                {recommendation.carbon_saved_vs_now_pct}% carbon saved
              </span>
            )}
          </h2>
          <p
            style={{
              margin: "-0.5rem 0 1rem",
              fontSize: "0.78rem",
              color: "var(--gray-400)",
            }}
          >
            Estimated from a simplified time-of-day model (not a real grid forecast); "% carbon
            saved" is vs the dirtiest candidate region right now. Directional guidance, not a
            precise prediction.
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: "0.75rem",
              marginBottom: "1rem",
            }}
          >
            <StatCard label="Provider" value={recommended.provider.toUpperCase()} />
            <StatCard label="Region" value={recommended.region} mono />
            <StatCard
              label="Carbon"
              value={`${recommended.carbon_intensity_gco2_kwh}`}
              unit="gCO₂/kWh"
            />
            <StatCard
              label="Renewable"
              value={`${recommended.renewable_percentage}`}
              unit="%"
              positive
              tip={RENEWABLE_TIP}
            />
            <StatCard label="Start" value={new Date(recommended.start).toLocaleString()} />
            <StatCard label="Slots Evaluated" value={`${recommendation.evaluated_slots}`} />
          </div>

          {/* Alternatives */}
          {alternatives.length > 0 && (
            <>
              <h3 style={{ margin: "1rem 0 0.5rem", fontSize: "0.95rem" }}>Alternatives</h3>
              <div style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                      <th style={th}>Provider</th>
                      <th style={th}>Region</th>
                      <th style={{ ...th, textAlign: "right" }}>gCO₂/kWh</th>
                      <th style={{ ...th, textAlign: "right" }}>
                        Renewable %
                        <InfoTip label="renewable %" text={RENEWABLE_TIP} />
                      </th>
                      <th style={th}>Start Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alternatives.slice(0, 8).map((alt, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--gray-100)" }}>
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
                        <td style={{ ...td, textAlign: "right" }}>
                          {alt.carbon_intensity_gco2_kwh}
                        </td>
                        <td
                          style={{
                            ...td,
                            textAlign: "right",
                            color: "var(--green-text)",
                            fontWeight: 600,
                          }}
                        >
                          {alt.renewable_percentage}%
                        </td>
                        <td
                          style={{
                            ...td,
                            fontSize: "0.8rem",
                            color: "var(--gray-500)",
                          }}
                        >
                          {new Date(alt.start).toLocaleString()}
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

      {/* Error */}
      {findWindow.isError && (
        <div
          style={{
            ...card,
            border: "1px solid var(--red-300, #fca5a5)",
            color: "var(--red-400, #f87171)",
          }}
        >
          Error: {(findWindow.error as Error).message}
        </div>
      )}

      {/* Recommends vs executes */}
      <div
        style={{
          ...card,
          marginBottom: "2rem",
          borderLeft: "3px solid var(--green-300)",
        }}
      >
        <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.1rem" }}>
          Recommends — doesn't run your job
        </h2>
        <p style={{ color: "var(--gray-600)", fontSize: "0.9rem", margin: 0 }}>
          CarbonLens tells you the greenest window and region. It doesn't trigger, hold, or relocate
          any workload — that execution step is yours. To actually gate or defer real CI/CD jobs on
          grid cleanliness, see{" "}
          <a
            href="https://github.com/peterklingelhofer/carbon-aware-dispatcher"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--green-text)", fontWeight: 600 }}
          >
            carbon-aware-dispatcher
          </a>{" "}
          — a GitHub Action (and CLI) that reads the same kind of live grid data, then skips, waits
          for, or dispatches a build only when the grid is clean. In short: this page advises{" "}
          <em>when</em> to run; the dispatcher changes <em>when and where compute actually runs</em>
          .
        </p>
      </div>

      {/* Integration Examples */}
      <div style={card}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Integration Examples</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "1rem",
          }}
        >
          <div>
            <h3 style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>GitHub Actions</h3>
            <pre style={codeBlock}>{`# .github/workflows/green-ci.yml
- name: Find green window
  run: |
    curl -X POST $API_URL/api/v1/scheduler/find-window \\
      -H "Content-Type: application/json" \\
      -d '{"job_duration_minutes": 30,
           "strategy": "lowest_carbon"}'`}</pre>
          </div>
          <div>
            <h3 style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>Python SDK</h3>
            <pre style={codeBlock}>{`import httpx

resp = httpx.post(
    f"{API_URL}/api/v1/scheduler/find-window",
    json={
        "job_duration_minutes": 60,
        "providers": ["aws", "gcp"],
        "strategy": "balanced",
    },
)
window = resp.json()
print(f"Run at {window['recommended']['start']}")
print(f"in {window['recommended']['region']}")`}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  unit,
  positive,
  mono,
  tip,
}: {
  label: string;
  value: string;
  unit?: string;
  positive?: boolean;
  mono?: boolean;
  tip?: ReactNode;
}) {
  return (
    <div
      style={{
        padding: "0.75rem",
        borderRadius: 8,
        border: "1px solid var(--gray-200)",
        background: "var(--surface-alt)",
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          color: "var(--gray-500)",
          display: "inline-flex",
          alignItems: "center",
        }}
      >
        {label}
        {tip && <InfoTip label={label.toLowerCase()} text={tip} />}
      </div>
      <div
        style={{
          fontSize: mono ? "0.85rem" : "1.3rem",
          fontWeight: 700,
          color: positive ? "var(--green-700)" : "inherit",
          fontFamily: mono ? "var(--mono)" : "inherit",
        }}
      >
        {value}
        {unit && (
          <span style={{ fontSize: "0.75rem", fontWeight: 400, marginLeft: 4 }}>{unit}</span>
        )}
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: "0.8rem",
  color: "var(--gray-500)",
  display: "block",
  marginBottom: 4,
};

const sliderValue: React.CSSProperties = {
  fontSize: "0.8rem",
  textAlign: "center",
  color: "var(--green-text)",
  fontWeight: 600,
};

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem",
  fontSize: "0.75rem",
  fontWeight: 600,
  color: "var(--gray-500)",
};

const td: React.CSSProperties = { padding: "0.5rem", fontSize: "0.85rem" };

const codeBlock: React.CSSProperties = {
  background: "var(--surface-alt)",
  borderRadius: 8,
  padding: "0.75rem",
  fontSize: "0.75rem",
  overflow: "auto",
  border: "1px solid var(--gray-200)",
  lineHeight: 1.6,
  margin: 0,
};
