import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import type { SimulateResponse, ComputeOption } from "../api/types";
import { section as sectionFn, card } from "../styles";

const section = sectionFn(1100);

const NETWORKS = [
  "boundless",
  "succinct",
  "gevulot",
  "aleo",
  "scroll",
  "zksync",
  "starknet",
  "taiko",
];

export function ZKBroker() {
  const [network, setNetwork] = useState("boundless");
  const [bountyUsd, setBountyUsd] = useState(5.0);
  const [circuitSize, setCircuitSize] = useState(20);
  const [maxCarbon, setMaxCarbon] = useState(50);
  const [result, setResult] = useState<SimulateResponse | null>(null);

  const { data: stats } = useQuery({
    queryKey: ["zk-stats"],
    queryFn: () => api.zk.stats(),
    refetchInterval: 10000,
  });

  const { data: jobs } = useQuery({
    queryKey: ["zk-jobs", network],
    queryFn: () => api.zk.availableJobs(network),
  });

  const simulateMutation = useMutation({
    mutationFn: () =>
      api.zk.simulate({
        network,
        bounty_usd: bountyUsd,
        circuit_size: circuitSize,
        max_carbon_intensity: maxCarbon,
      }),
    onSuccess: setResult,
  });

  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem" }}>Green ZK Broker</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Route ZK proof generation to the greenest, most profitable GPU compute.
      </p>

      {/* Stats */}
      {stats && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: "0.75rem",
            marginBottom: "2rem",
          }}
        >
          <StatCard label="Jobs Completed" value={stats.completed_jobs} />
          <StatCard
            label="Total Profit"
            value={`$${stats.total_profit_usd.toFixed(2)}`}
            positive
          />
          <StatCard
            label="Avg Margin"
            value={`${stats.avg_profit_margin_pct.toFixed(1)}%`}
            positive
          />
          <StatCard
            label="Avg Renewable"
            value={`${stats.avg_renewable_percentage.toFixed(0)}%`}
            positive
          />
          <StatCard
            label="Zero-Carbon Jobs"
            value={`${stats.zero_carbon_job_pct.toFixed(0)}%`}
            positive
          />
          <StatCard
            label="CO2 Saved"
            value={`${stats.total_carbon_saved_grams.toFixed(0)}g`}
            positive
          />
        </div>
      )}

      {/* Simulate */}
      <div style={{ ...card, marginBottom: "2rem" }}>
        <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>
          Simulate Proof Routing
        </h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
            marginBottom: "1rem",
          }}
        >
          <div>
            <label
              style={{ fontSize: "0.8rem", color: "var(--gray-500)", display: "block", marginBottom: 4 }}
            >
              Prover Network
            </label>
            <select
              value={network}
              onChange={(e) => setNetwork(e.target.value)}
              style={{
                width: "100%",
                padding: "0.5rem",
                borderRadius: 6,
                border: "1px solid var(--gray-200)",
                fontSize: "0.9rem",
              }}
            >
              {NETWORKS.map((n) => (
                <option key={n} value={n}>
                  {n.charAt(0).toUpperCase() + n.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              style={{ fontSize: "0.8rem", color: "var(--gray-500)", display: "block", marginBottom: 4 }}
            >
              Bounty (USD)
            </label>
            <input
              type="number"
              value={bountyUsd}
              onChange={(e) => setBountyUsd(Number(e.target.value))}
              min={0}
              step={0.5}
              style={{
                width: "100%",
                padding: "0.5rem",
                borderRadius: 6,
                border: "1px solid var(--gray-200)",
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div>
            <label
              style={{ fontSize: "0.8rem", color: "var(--gray-500)", display: "block", marginBottom: 4 }}
            >
              Circuit Size (log2)
            </label>
            <input
              type="range"
              min={18}
              max={26}
              value={circuitSize}
              onChange={(e) => setCircuitSize(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={{ fontSize: "0.8rem", textAlign: "center" }}>
              2^{circuitSize} = {(2 ** circuitSize).toLocaleString()} constraints
            </div>
          </div>
          <div>
            <label
              style={{ fontSize: "0.8rem", color: "var(--gray-500)", display: "block", marginBottom: 4 }}
            >
              Max Carbon (gCO2/kWh)
            </label>
            <input
              type="range"
              min={0}
              max={500}
              step={10}
              value={maxCarbon}
              onChange={(e) => setMaxCarbon(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div
              style={{
                fontSize: "0.8rem",
                textAlign: "center",
                color: maxCarbon === 0 ? "var(--green-600)" : "inherit",
                fontWeight: maxCarbon === 0 ? 600 : 400,
              }}
            >
              {maxCarbon === 0 ? "ZERO CARBON ONLY" : `${maxCarbon} gCO2/kWh`}
            </div>
          </div>
        </div>
        <button
          onClick={() => simulateMutation.mutate()}
          disabled={simulateMutation.isPending}
          style={{
            padding: "0.75rem 2rem",
            borderRadius: 8,
            border: "none",
            background: "var(--green-600)",
            color: "white",
            fontWeight: 600,
            cursor: simulateMutation.isPending ? "wait" : "pointer",
          }}
        >
          {simulateMutation.isPending ? "Routing..." : "Find Greenest GPU"}
        </button>
      </div>

      {/* Simulation Result */}
      {result && <SimulationResult result={result} />}

      {/* Available Jobs */}
      {jobs && jobs.length > 0 && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>
            Available Proof Jobs
          </h2>
          <div style={{ overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                  <th style={th}>Network</th>
                  <th style={th}>Proof System</th>
                  <th style={th}>Circuit</th>
                  <th style={{ ...th, textAlign: "right" }}>Bounty</th>
                  <th style={{ ...th, textAlign: "right" }}>Est. GPU Min</th>
                  <th style={{ ...th, textAlign: "right" }}>VRAM</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    style={{ borderBottom: "1px solid var(--gray-100)" }}
                  >
                    <td style={td}>
                      <span style={{ fontWeight: 600, textTransform: "capitalize" }}>
                        {job.network}
                      </span>
                    </td>
                    <td style={td}>
                      <span
                        style={{
                          fontFamily: "var(--mono)",
                          fontSize: "0.8rem",
                        }}
                      >
                        {job.proof_system}
                      </span>
                    </td>
                    <td style={td}>2^{job.circuit_size}</td>
                    <td style={{ ...td, textAlign: "right", fontWeight: 600 }}>
                      ${job.bounty_usd.toFixed(2)}
                      <span
                        style={{
                          fontSize: "0.7rem",
                          color: "var(--gray-400)",
                          marginLeft: 4,
                        }}
                      >
                        {job.bounty_token}
                      </span>
                    </td>
                    <td style={{ ...td, textAlign: "right" }}>
                      {job.estimated_gpu_minutes.toFixed(1)}
                    </td>
                    <td style={{ ...td, textAlign: "right" }}>
                      {job.min_vram_gb} GB
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function SimulationResult({ result }: { result: SimulateResponse }) {
  const decision = result.decision;

  return (
    <div style={{ ...card, marginBottom: "2rem" }}>
      <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>
        Routing Decision
        {result.rejected && (
          <span
            style={{
              marginLeft: 8,
              fontSize: "0.75rem",
              color: "white",
              background: "var(--red-400, #f87171)",
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            REJECTED
          </span>
        )}
      </h2>

      {result.rejected ? (
        <div
          style={{
            padding: "1rem",
            borderRadius: 8,
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid var(--red-200, #fecaca)",
            color: "var(--red-700, #b91c1c)",
            fontSize: "0.9rem",
          }}
        >
          {result.rejection_reason}
        </div>
      ) : decision ? (
        <>
          {/* Winner */}
          <div
            style={{
              padding: "1rem",
              borderRadius: 8,
              background: "rgba(34, 197, 94, 0.08)",
              border: "1px solid var(--green-200)",
              marginBottom: "1rem",
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "0.75rem",
              }}
            >
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  Provider
                </div>
                <div style={{ fontWeight: 700, textTransform: "uppercase" }}>
                  {decision.chosen_provider.provider.replace("_", " ")}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
                  {decision.chosen_provider.region}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  GPU
                </div>
                <div style={{ fontWeight: 600 }}>
                  {decision.chosen_provider.gpu_type.replace("_", " ").toUpperCase()}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
                  {decision.chosen_provider.vram_gb} GB VRAM
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  Carbon
                </div>
                <div
                  style={{
                    fontWeight: 700,
                    color:
                      decision.chosen_provider.carbon_intensity_gco2_kwh === 0
                        ? "var(--green-600)"
                        : decision.chosen_provider.carbon_intensity_gco2_kwh <=
                            50
                          ? "var(--green-500)"
                          : "var(--orange-400)",
                  }}
                >
                  {decision.chosen_provider.carbon_intensity_gco2_kwh} gCO2/kWh
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
                  {decision.chosen_provider.renewable_percentage}% renewable
                  {decision.chosen_provider.is_behind_the_meter && " (BTM)"}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  Profit
                </div>
                <div style={{ fontWeight: 700, color: "var(--green-600)" }}>
                  ${decision.estimated_profit_usd.toFixed(4)}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
                  {decision.profit_margin_pct}% margin
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
                  CO2 Saved
                </div>
                <div style={{ fontWeight: 700, color: "var(--green-600)" }}>
                  {decision.carbon_saved_vs_grid_avg_grams.toFixed(1)}g
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
                  vs grid average
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {/* All options comparison */}
      <h3
        style={{ fontSize: "0.9rem", marginBottom: "0.5rem", marginTop: "1rem" }}
      >
        All Compute Options ({result.all_options.length} found,{" "}
        {result.green_options.length} passed carbon filter)
      </h3>
      <div style={{ overflow: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
              <th style={th}>Provider</th>
              <th style={th}>Region</th>
              <th style={th}>GPU</th>
              <th style={{ ...th, textAlign: "right" }}>$/hr</th>
              <th style={{ ...th, textAlign: "right" }}>Job Cost</th>
              <th style={{ ...th, textAlign: "right" }}>gCO2/kWh</th>
              <th style={{ ...th, textAlign: "right" }}>Renew %</th>
              <th style={th}>BTM</th>
              <th style={th}>Status</th>
            </tr>
          </thead>
          <tbody>
            {result.all_options
              .sort(
                (a, b) =>
                  a.carbon_intensity_gco2_kwh - b.carbon_intensity_gco2_kwh
              )
              .map((opt, i) => {
                const isGreen = result.green_options.some(
                  (g) =>
                    g.provider === opt.provider && g.region === opt.region
                );
                const isChosen =
                  decision?.chosen_provider.provider === opt.provider &&
                  decision?.chosen_provider.region === opt.region;
                return (
                  <tr
                    key={i}
                    style={{
                      borderBottom: "1px solid var(--gray-100)",
                      background: isChosen
                        ? "rgba(34, 197, 94, 0.06)"
                        : undefined,
                      opacity: isGreen ? 1 : 0.5,
                    }}
                  >
                    <td style={{ ...td, fontWeight: 600, textTransform: "uppercase", fontSize: "0.75rem" }}>
                      {opt.provider.replace("_", " ")}
                    </td>
                    <td style={{ ...td, fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
                      {opt.region}
                    </td>
                    <td style={{ ...td, fontSize: "0.8rem" }}>
                      {opt.gpu_type.replace("_", " ").toUpperCase()}
                    </td>
                    <td style={{ ...td, textAlign: "right" }}>
                      ${opt.cost_per_gpu_hour_usd.toFixed(2)}
                    </td>
                    <td style={{ ...td, textAlign: "right" }}>
                      ${opt.estimated_job_cost_usd.toFixed(4)}
                    </td>
                    <td
                      style={{
                        ...td,
                        textAlign: "right",
                        fontWeight: 600,
                        color:
                          opt.carbon_intensity_gco2_kwh === 0
                            ? "var(--green-600)"
                            : opt.carbon_intensity_gco2_kwh <= 50
                              ? "var(--green-500)"
                              : opt.carbon_intensity_gco2_kwh <= 200
                                ? "var(--yellow-500, #eab308)"
                                : "var(--red-400)",
                      }}
                    >
                      {opt.carbon_intensity_gco2_kwh}
                    </td>
                    <td
                      style={{
                        ...td,
                        textAlign: "right",
                        color:
                          opt.renewable_percentage >= 90
                            ? "var(--green-600)"
                            : "inherit",
                      }}
                    >
                      {opt.renewable_percentage}%
                    </td>
                    <td style={td}>
                      {opt.is_behind_the_meter ? (
                        <span style={{ color: "var(--green-600)", fontWeight: 600 }}>
                          Yes
                        </span>
                      ) : (
                        <span style={{ color: "var(--gray-400)" }}>No</span>
                      )}
                    </td>
                    <td style={td}>
                      {isChosen ? (
                        <span
                          style={{
                            color: "var(--green-600)",
                            fontWeight: 700,
                            fontSize: "0.75rem",
                          }}
                        >
                          CHOSEN
                        </span>
                      ) : isGreen ? (
                        <span
                          style={{
                            color: "var(--green-500)",
                            fontSize: "0.75rem",
                          }}
                        >
                          eligible
                        </span>
                      ) : (
                        <span
                          style={{
                            color: "var(--red-400)",
                            fontSize: "0.75rem",
                          }}
                        >
                          filtered
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  positive,
}: {
  label: string;
  value: string | number;
  positive?: boolean;
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
      <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>
        {label}
      </div>
      <div
        style={{
          fontSize: "1.3rem",
          fontWeight: 700,
          color: positive ? "var(--green-700)" : "inherit",
        }}
      >
        {value}
      </div>
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem",
  fontSize: "0.75rem",
  fontWeight: 600,
  color: "var(--gray-500)",
};

const td: React.CSSProperties = { padding: "0.5rem", fontSize: "0.85rem" };
