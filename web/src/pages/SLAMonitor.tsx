import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { section as sectionFn, card } from "../styles";
import { InfoTip } from "../components/InfoTip";

const section = sectionFn(1100);

export function SLAMonitor() {
  const queryClient = useQueryClient();
  const [orgId] = useState("demo");
  const [showCreate, setShowCreate] = useState(false);

  // Form state
  const [name, setName] = useState("Production Green SLA");
  const [maxCarbon, setMaxCarbon] = useState(100);
  const [minRenewable, setMinRenewable] = useState(50);

  const { data: slas } = useQuery({
    queryKey: ["slas", orgId],
    queryFn: () => api.sla.list(orgId),
  });

  const { data: monitorStatus } = useQuery({
    queryKey: ["sla-monitor"],
    queryFn: () => api.sla.monitorStatus(),
    refetchInterval: 10000,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.sla.create({
        org_id: orgId,
        name,
        max_carbon_intensity_gco2_kwh: maxCarbon,
        min_renewable_percentage: minRenewable,
        providers: ["aws", "gcp", "azure"],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["slas"] });
      setShowCreate(false);
    },
  });

  const checkMutation = useMutation({
    mutationFn: (slaId: string) => api.sla.check(slaId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["slas"] }),
  });

  const reportMutation = useMutation({
    mutationFn: (slaId: string) =>
      api.sla.generateReport(slaId, { org_name: "Demo Organization", period_days: 30 }),
  });

  const monitorMutation = useMutation({
    mutationFn: (action: "start" | "stop") =>
      action === "start" ? api.sla.startMonitor(orgId) : api.sla.stopMonitor(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sla-monitor"] }),
  });

  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem", display: "flex", alignItems: "center" }}>
        Green SLA monitoring
        <InfoTip
          label="SLA"
          text="An SLA (service-level agreement) is a measurable promise about a service. Here it's a carbon ceiling for your workloads — e.g. 'stay under 100 gCO₂/kWh' — checked against live grid data."
        />
      </h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Set carbon targets for your workloads, check them against live grid data, and
        get summary reports.
      </p>

      {/* Monitor Status + Controls */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "2rem" }}>
        <div style={card}>
          <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.1rem" }}>Background Monitor</h2>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.5rem" }}>
            <span style={{
              width: 8, height: 8, borderRadius: "50%",
              background: monitorStatus?.running ? "var(--green-500)" : "var(--gray-300)",
              display: "inline-block",
            }} />
            <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>
              {monitorStatus?.running ? "Running" : "Stopped"}
            </span>
          </div>
          {monitorStatus?.running && (
            <div style={{ fontSize: "0.8rem", color: "var(--gray-500)", marginBottom: "0.5rem" }}>
              {monitorStatus.checks_completed} checks | {monitorStatus.breaches_detected} breaches | {monitorStatus.slas_monitored} SLAs
            </div>
          )}
          <button
            onClick={() => monitorMutation.mutate(monitorStatus?.running ? "stop" : "start")}
            disabled={monitorMutation.isPending}
            style={{
              padding: "0.5rem 1.5rem", borderRadius: 6, border: "none",
              background: monitorStatus?.running ? "var(--gray-200)" : "var(--btn-green)",
              color: monitorStatus?.running ? "var(--gray-700)" : "white",
              fontWeight: 600, cursor: "pointer", fontSize: "0.85rem",
            }}
          >
            {monitorStatus?.running ? "Stop Monitor" : "Start Monitor"}
          </button>
        </div>

        <div style={card}>
          <h2 style={{ margin: "0 0 0.75rem", fontSize: "1.1rem" }}>Quick Stats</h2>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--green-text)" }}>
            {slas?.length || 0}
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>
            SLAs defined
          </div>
          {slas && slas.length > 0 && (
            <div style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
              <span style={{ color: "var(--green-text)", fontWeight: 600 }}>
                {slas.filter((s: { status: string }) => s.status === "compliant").length} compliant
              </span>
              {" | "}
              <span style={{ color: "var(--orange-400, #fb923c)", fontWeight: 600 }}>
                {slas.filter((s: { status: string }) => s.status === "warning").length} warning
              </span>
              {" | "}
              <span style={{ color: "var(--red-400, #f87171)", fontWeight: 600 }}>
                {slas.filter((s: { status: string }) => s.status === "breached").length} breached
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Create SLA */}
      <div style={{ marginBottom: "1.5rem" }}>
        <button
          onClick={() => setShowCreate(!showCreate)}
          style={{
            padding: "0.5rem 1.5rem", borderRadius: 6, border: "none",
            background: "var(--btn-green)", color: "white",
            fontWeight: 600, cursor: "pointer", fontSize: "0.85rem",
          }}
        >
          {showCreate ? "Cancel" : "Create New SLA"}
        </button>
      </div>

      {showCreate && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>New Green SLA</h2>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem", marginBottom: "1rem",
          }}>
            <div>
              <label style={labelStyle}>SLA Name</label>
              <input
                type="text" value={name} onChange={(e) => setName(e.target.value)}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Max Carbon (gCO2/kWh)</label>
              <input
                type="range" min={0} max={500} step={10}
                value={maxCarbon} onChange={(e) => setMaxCarbon(Number(e.target.value))}
                style={{ width: "100%" }}
              />
              <div style={{ fontSize: "0.8rem", textAlign: "center",
                color: maxCarbon <= 50 ? "var(--green-text)" : maxCarbon <= 200 ? "var(--green-500)" : "var(--orange-400)",
                fontWeight: 600,
              }}>
                {maxCarbon === 0 ? "ZERO CARBON ONLY" : `${maxCarbon} gCO2/kWh`}
              </div>
            </div>
            <div>
              <label style={labelStyle}>Min Renewable (%)</label>
              <input
                type="range" min={0} max={100} step={5}
                value={minRenewable} onChange={(e) => setMinRenewable(Number(e.target.value))}
                style={{ width: "100%" }}
              />
              <div style={{ fontSize: "0.8rem", textAlign: "center", fontWeight: 600,
                color: minRenewable >= 80 ? "var(--green-text)" : "inherit",
              }}>
                {minRenewable}% minimum renewable
              </div>
            </div>
          </div>
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            style={{
              padding: "0.75rem 2rem", borderRadius: 8, border: "none",
              background: "var(--btn-green)", color: "white",
              fontWeight: 600, cursor: createMutation.isPending ? "wait" : "pointer",
            }}
          >
            {createMutation.isPending ? "Creating..." : "Create SLA"}
          </button>
        </div>
      )}

      {/* SLA List */}
      {slas && slas.length > 0 && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Your SLAs</h2>
          <div style={{ overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                  <th style={th}>Name</th>
                  <th style={th}>Status</th>
                  <th style={{ ...th, textAlign: "right" }}>Max Carbon</th>
                  <th style={{ ...th, textAlign: "right" }}>Min Renewable</th>
                  <th style={th}>Frequency</th>
                  <th style={th}>Last Checked</th>
                  <th style={th}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {slas.map((sla) => (
                  <tr key={sla.id as string} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                    <td style={{ ...td, fontWeight: 600 }}>{sla.name as string}</td>
                    <td style={td}>
                      <StatusBadge status={sla.status as string} />
                    </td>
                    <td style={{ ...td, textAlign: "right" }}>
                      {sla.max_carbon_intensity_gco2_kwh as number} gCO2
                    </td>
                    <td style={{ ...td, textAlign: "right" }}>
                      {sla.min_renewable_percentage as number}%
                    </td>
                    <td style={td}>{sla.check_frequency as string}</td>
                    <td style={{ ...td, fontSize: "0.8rem", color: "var(--gray-500)" }}>
                      {sla.last_checked
                        ? new Date(sla.last_checked as string).toLocaleString()
                        : "Never"}
                    </td>
                    <td style={td}>
                      <div style={{ display: "flex", gap: "0.25rem" }}>
                        <button
                          onClick={() => checkMutation.mutate(sla.id as string)}
                          disabled={checkMutation.isPending}
                          style={smallButton}
                        >
                          Check
                        </button>
                        <button
                          onClick={() => reportMutation.mutate(sla.id as string)}
                          disabled={reportMutation.isPending}
                          style={smallButton}
                        >
                          Report
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Latest Check Result */}
      {checkMutation.data && (
        <div style={{ ...card, marginBottom: "2rem",
          border: checkMutation.data.status === "compliant" ? "1px solid var(--green-300)" :
                  checkMutation.data.status === "warning" ? "1px solid var(--yellow-300, #fde047)" :
                  "1px solid var(--red-300, #fca5a5)",
        }}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>
            Latest Check Result
            <StatusBadge status={checkMutation.data.status} style={{ marginLeft: 8 }} />
          </h2>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: "0.75rem",
          }}>
            <StatCard label="Avg Carbon" value={`${checkMutation.data.avg_carbon_intensity_gco2_kwh}`} unit="gCO2/kWh" />
            <StatCard label="Max Carbon" value={`${checkMutation.data.max_carbon_intensity_gco2_kwh}`} unit="gCO2/kWh" />
            <StatCard label="Avg Renewable" value={`${checkMutation.data.avg_renewable_percentage}`} unit="%" positive />
            <StatCard label="Regions Checked" value={`${checkMutation.data.regions_checked}`} />
            <StatCard label="Compliant" value={`${checkMutation.data.regions_compliant}`} positive />
            <StatCard label="Breached" value={`${checkMutation.data.regions_breached}`} />
          </div>
          {checkMutation.data.breached_regions.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <h3 style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>Breached Regions</h3>
              <div style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                      <th style={th}>Provider</th>
                      <th style={th}>Region</th>
                      <th style={{ ...th, textAlign: "right" }}>gCO2/kWh</th>
                      <th style={{ ...th, textAlign: "right" }}>Renewable %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {checkMutation.data.breached_regions.map((r, i: number) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                        <td style={{ ...td, fontWeight: 600, textTransform: "uppercase", fontSize: "0.8rem" }}>
                          {r.provider as string}
                        </td>
                        <td style={{ ...td, fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
                          {r.region as string}
                        </td>
                        <td style={{ ...td, textAlign: "right", fontWeight: 600, color: "var(--red-400, #f87171)" }}>
                          {r.carbon_intensity_gco2_kwh as number}
                        </td>
                        <td style={{ ...td, textAlign: "right" }}>
                          {r.renewable_percentage as number}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Report Result */}
      {reportMutation.data && (
        <div style={{ ...card, marginBottom: "2rem" }}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>
            Attestation Report: {reportMutation.data.sla_name}
          </h2>
          <div style={{ fontSize: "0.8rem", color: "var(--gray-500)", marginBottom: "1rem" }}>
            {new Date(reportMutation.data.period_start).toLocaleDateString()} — {new Date(reportMutation.data.period_end).toLocaleDateString()}
            {" | "}Generated {new Date(reportMutation.data.generated_at).toLocaleString()}
          </div>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: "0.75rem", marginBottom: "1rem",
          }}>
            <StatCard label="Compliance" value={`${reportMutation.data.compliance_percentage}`} unit="%" positive={reportMutation.data.compliance_percentage >= 80} />
            <StatCard label="Total Checks" value={`${reportMutation.data.total_checks}`} />
            <StatCard label="Compliant" value={`${reportMutation.data.compliant_checks}`} positive />
            <StatCard label="Breached" value={`${reportMutation.data.breached_checks}`} />
            <StatCard label="Avg Carbon" value={`${reportMutation.data.avg_carbon_intensity_gco2_kwh}`} unit="gCO2/kWh" />
            <StatCard label="Avg Renewable" value={`${reportMutation.data.avg_renewable_percentage}`} unit="%" positive />
          </div>
          <div style={{ padding: "0.75rem", borderRadius: 8, background: "var(--surface-alt)", fontSize: "0.8rem", color: "var(--gray-600)" }}>
            {reportMutation.data.reporting_standard} | {reportMutation.data.methodology}
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status, style }: { status: string; style?: React.CSSProperties }) {
  const colors: Record<string, { bg: string; color: string }> = {
    compliant: { bg: "var(--green-100)", color: "var(--green-text)" },
    warning: { bg: "rgba(234, 179, 8, 0.1)", color: "var(--orange-400, #fb923c)" },
    breached: { bg: "rgba(239, 68, 68, 0.1)", color: "var(--red-400, #f87171)" },
    unknown: { bg: "var(--gray-100)", color: "var(--gray-500)" },
  };
  const c = colors[status] || colors.unknown;
  return (
    <span style={{
      fontSize: "0.7rem", fontWeight: 600, padding: "2px 8px",
      borderRadius: 4, background: c.bg, color: c.color,
      textTransform: "uppercase", ...style,
    }}>
      {status}
    </span>
  );
}

function StatCard({ label, value, unit, positive }: {
  label: string; value: string; unit?: string; positive?: boolean;
}) {
  return (
    <div style={{
      padding: "0.75rem", borderRadius: 8,
      border: "1px solid var(--gray-200)", background: "var(--surface-alt)",
    }}>
      <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>{label}</div>
      <div style={{
        fontSize: "1.3rem", fontWeight: 700,
        color: positive ? "var(--green-700)" : "inherit",
      }}>
        {value}
        {unit && <span style={{ fontSize: "0.75rem", fontWeight: 400, marginLeft: 4 }}>{unit}</span>}
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: "0.8rem", color: "var(--gray-500)", display: "block", marginBottom: 4,
};

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "0.5rem", borderRadius: 6,
  border: "1px solid var(--gray-200)", fontSize: "0.9rem", boxSizing: "border-box",
};

const th: React.CSSProperties = {
  textAlign: "left", padding: "0.5rem", fontSize: "0.75rem",
  fontWeight: 600, color: "var(--gray-500)",
};

const td: React.CSSProperties = { padding: "0.5rem", fontSize: "0.85rem" };

const smallButton: React.CSSProperties = {
  padding: "0.25rem 0.5rem", borderRadius: 4, border: "1px solid var(--gray-200)",
  background: "var(--surface)", cursor: "pointer", fontSize: "0.75rem",
};
