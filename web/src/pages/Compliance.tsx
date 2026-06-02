import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ComplianceReport } from "../api/types";
import { section as sectionFn, card, providerChip } from "../styles";

const section = sectionFn(1100);

export function Compliance() {
  const queryClient = useQueryClient();
  const [orgId] = useState("demo");
  const [orgName] = useState("Demo Organization");
  const [activeReport, setActiveReport] = useState<ComplianceReport | null>(
    null
  );
  const [step, setStep] = useState<
    "idle" | "ingesting" | "calculating" | "generating"
  >("idle");

  const { data: reports } = useQuery({
    queryKey: ["compliance-reports", orgId],
    queryFn: () => api.compliance.listReports(orgId),
  });

  const ingestMutation = useMutation({
    mutationFn: () => {
      setStep("ingesting");
      return api.compliance.ingestUsage({
        org_id: orgId,
        provider: "mock",
        period_start: new Date(
          Date.now() - 30 * 24 * 60 * 60 * 1000
        ).toISOString(),
        period_end: new Date().toISOString(),
      });
    },
  });

  const calculateMutation = useMutation({
    mutationFn: () => {
      setStep("calculating");
      return api.compliance.calculate(orgId);
    },
  });

  const reportMutation = useMutation({
    mutationFn: () => {
      setStep("generating");
      return api.compliance.generateReport({
        org_id: orgId,
        org_name: orgName,
        report_name: `CSRD Report — ${new Date().toISOString().slice(0, 10)}`,
      });
    },
    onSuccess: (report) => {
      setActiveReport(report);
      setStep("idle");
      queryClient.invalidateQueries({ queryKey: ["compliance-reports"] });
    },
  });

  async function runFullPipeline() {
    try {
      await ingestMutation.mutateAsync();
      await calculateMutation.mutateAsync();
      await reportMutation.mutateAsync();
    } catch {
      setStep("idle");
    }
  }

  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem" }}>Compliance Reporting</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        CSRD / ESRS E1 aligned cloud emissions measurement and reporting.
      </p>

      {/* Pipeline action */}
      <div
        style={{
          ...card,
          marginBottom: "2rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "1.1rem" }}>
          Generate Compliance Report
        </h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: 0 }}>
          This demo ingests mock cloud usage data, calculates emissions using
          real-time grid carbon intensity from 11 government sources, and
          generates a CSRD-aligned report.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button
            onClick={runFullPipeline}
            disabled={step !== "idle"}
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              border: "none",
              background: "var(--btn-green)",
              color: "white",
              fontWeight: 600,
              cursor: step === "idle" ? "pointer" : "wait",
              opacity: step === "idle" ? 1 : 0.7,
            }}
          >
            {step === "idle"
              ? "Generate Report (Demo Data)"
              : step === "ingesting"
                ? "Ingesting usage data..."
                : step === "calculating"
                  ? "Calculating emissions..."
                  : "Generating report..."}
          </button>
        </div>

        {/* Pipeline step results */}
        {ingestMutation.data && (
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--gray-600)",
              background: "var(--surface-alt)",
              padding: "0.5rem 0.75rem",
              borderRadius: 6,
            }}
          >
            Ingested {ingestMutation.data.records_ingested} usage records (
            {ingestMutation.data.total_energy_kwh.toFixed(2)} kWh) across{" "}
            {ingestMutation.data.providers_covered.join(", ")}
          </div>
        )}
        {calculateMutation.data && (
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--gray-600)",
              background: "var(--surface-alt)",
              padding: "0.5rem 0.75rem",
              borderRadius: 6,
            }}
          >
            Calculated {calculateMutation.data.calculations_count} emissions (
            {calculateMutation.data.total_emissions_kgco2e.toFixed(4)} kgCO2e)
            — Sources: {calculateMutation.data.data_sources_used.join(", ")}
          </div>
        )}
      </div>

      {/* Active Report */}
      {activeReport && <ReportView report={activeReport} />}

      {/* Report history */}
      {reports && reports.length > 0 && (
        <div style={card}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>
            Report History
          </h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                <th
                  style={{
                    textAlign: "left",
                    padding: "0.5rem",
                    fontSize: "0.8rem",
                  }}
                >
                  Report
                </th>
                <th
                  style={{
                    textAlign: "left",
                    padding: "0.5rem",
                    fontSize: "0.8rem",
                  }}
                >
                  Period
                </th>
                <th
                  style={{
                    textAlign: "right",
                    padding: "0.5rem",
                    fontSize: "0.8rem",
                  }}
                >
                  Total kgCO2e
                </th>
                <th
                  style={{
                    textAlign: "right",
                    padding: "0.5rem",
                    fontSize: "0.8rem",
                  }}
                >
                  Saved %
                </th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr
                  key={r.id}
                  style={{
                    borderBottom: "1px solid var(--gray-100)",
                    cursor: "pointer",
                  }}
                  onClick={async () => {
                    const full = await api.compliance.getReport(r.id, orgId);
                    setActiveReport(full);
                  }}
                >
                  <td
                    style={{
                      padding: "0.5rem",
                      fontSize: "0.85rem",
                      color: "var(--green-text)",
                      fontWeight: 500,
                    }}
                  >
                    {r.report_name}
                  </td>
                  <td style={{ padding: "0.5rem", fontSize: "0.8rem" }}>
                    {r.period_start.slice(0, 10)} — {r.period_end.slice(0, 10)}
                  </td>
                  <td
                    style={{
                      padding: "0.5rem",
                      textAlign: "right",
                      fontWeight: 600,
                    }}
                  >
                    {r.total_kgco2e.toFixed(4)}
                  </td>
                  <td
                    style={{
                      padding: "0.5rem",
                      textAlign: "right",
                      color: "var(--green-text)",
                      fontWeight: 600,
                    }}
                  >
                    {r.carbon_saved_percentage.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ReportView({ report }: { report: ComplianceReport }) {
  const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  return (
    <div style={{ ...card, marginBottom: "2rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: "1.2rem" }}>
            {report.report_name}
          </h2>
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--gray-500)",
              marginTop: "0.25rem",
            }}
          >
            {report.reporting_standard} | {report.methodology.split("(")[0]}
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--gray-400)",
              marginTop: "0.25rem",
            }}
          >
            Generated: {new Date(report.generated_at).toLocaleString()}
          </div>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <a
            href={`${BASE_URL}/api/v1/compliance/reports/${report.id}/export?org_id=${report.org_id}&format=json`}
            style={{
              padding: "0.4rem 0.8rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: "var(--surface)",
              fontSize: "0.8rem",
              textDecoration: "none",
              color: "inherit",
            }}
          >
            Export JSON
          </a>
          <a
            href={`${BASE_URL}/api/v1/compliance/reports/${report.id}/export?org_id=${report.org_id}&format=csv`}
            style={{
              padding: "0.4rem 0.8rem",
              borderRadius: 6,
              border: "1px solid var(--gray-200)",
              background: "var(--surface)",
              fontSize: "0.8rem",
              textDecoration: "none",
              color: "inherit",
            }}
          >
            Export CSV
          </a>
        </div>
      </div>

      {/* Summary stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <StatCard
          label="Total Emissions"
          value={`${report.total_kgco2e.toFixed(4)}`}
          unit="kgCO2e"
        />
        <StatCard
          label="Energy Consumed"
          value={`${report.total_energy_kwh.toFixed(2)}`}
          unit="kWh"
        />
        <StatCard
          label="Avg Renewable"
          value={`${report.avg_renewable_percentage.toFixed(1)}`}
          unit="%"
          positive
        />
        <StatCard
          label="Carbon Saved"
          value={`${report.carbon_saved_percentage.toFixed(1)}`}
          unit="% vs coal"
          positive
        />
      </div>

      {/* Scope breakdown */}
      <h3
        style={{ fontSize: "0.95rem", marginBottom: "0.75rem", marginTop: 0 }}
      >
        GHG Protocol Scope Breakdown
      </h3>
      <div style={{ overflow: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "0.85rem",
            marginBottom: "1.5rem",
          }}
        >
          <thead>
            <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Scope</th>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Method</th>
              <th style={{ textAlign: "right", padding: "0.5rem" }}>kgCO2e</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: "1px solid var(--gray-100)" }}>
              <td style={{ padding: "0.5rem", fontWeight: 500 }}>Scope 2</td>
              <td style={{ padding: "0.5rem" }}>Location-based</td>
              <td
                style={{
                  padding: "0.5rem",
                  textAlign: "right",
                  fontWeight: 600,
                }}
              >
                {report.scope2_location_kgco2e.toFixed(4)}
              </td>
            </tr>
            <tr style={{ borderBottom: "1px solid var(--gray-100)" }}>
              <td style={{ padding: "0.5rem", fontWeight: 500 }}>Scope 2</td>
              <td style={{ padding: "0.5rem" }}>Market-based</td>
              <td
                style={{
                  padding: "0.5rem",
                  textAlign: "right",
                  fontWeight: 600,
                }}
              >
                {report.scope2_market_kgco2e.toFixed(4)}
              </td>
            </tr>
            <tr style={{ borderBottom: "1px solid var(--gray-100)" }}>
              <td style={{ padding: "0.5rem", fontWeight: 500 }}>Scope 3</td>
              <td style={{ padding: "0.5rem" }}>Cat 1 (purchased services)</td>
              <td
                style={{
                  padding: "0.5rem",
                  textAlign: "right",
                  fontWeight: 600,
                }}
              >
                {report.scope3_cat1_kgco2e.toFixed(4)}
              </td>
            </tr>
            <tr style={{ fontWeight: 700 }}>
              <td style={{ padding: "0.5rem" }}>Total</td>
              <td style={{ padding: "0.5rem" }}></td>
              <td style={{ padding: "0.5rem", textAlign: "right" }}>
                {report.total_kgco2e.toFixed(4)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* By provider */}
      {Object.keys(report.scope2_location_by_provider).length > 0 && (
        <>
          <h3
            style={{
              fontSize: "0.95rem",
              marginBottom: "0.75rem",
              marginTop: 0,
            }}
          >
            Emissions by Cloud Provider
          </h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "0.75rem",
              marginBottom: "1.5rem",
            }}
          >
            {Object.entries(report.scope2_location_by_provider).map(
              ([provider, kgco2e]) => (
                <div
                  key={provider}
                  style={{
                    padding: "0.75rem",
                    borderRadius: 8,
                    border: "1px solid var(--gray-200)",
                    background: "var(--surface-alt)",
                    textAlign: "center",
                  }}
                >
                  <div>
                    <span
                      style={{
                        fontSize: "0.75rem",
                        textTransform: "uppercase",
                        ...providerChip(provider),
                      }}
                    >
                      {provider}
                    </span>
                  </div>
                  <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                    {kgco2e.toFixed(4)}
                  </div>
                  <div
                    style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}
                  >
                    kgCO2e
                  </div>
                </div>
              )
            )}
          </div>
        </>
      )}

      {/* EU Taxonomy */}
      <div
        style={{
          padding: "1rem",
          borderRadius: 8,
          background: report.eu_taxonomy_aligned
            ? "rgba(34, 197, 94, 0.08)"
            : "rgba(234, 179, 8, 0.08)",
          border: `1px solid ${report.eu_taxonomy_aligned ? "var(--green-200)" : "var(--yellow-200, #fef08a)"}`,
        }}
      >
        <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: 4 }}>
          EU Taxonomy Status:{" "}
          {report.eu_taxonomy_aligned ? "Aligned" : "Eligible (not yet aligned)"}
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--gray-600)" }}>
          {report.taxonomy_notes}
        </div>
      </div>

      {/* Data quality */}
      {Object.keys(report.data_quality_summary).length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--gray-500)",
              display: "flex",
              gap: "1rem",
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontWeight: 600 }}>Data quality:</span>
            {Object.entries(report.data_quality_summary).map(
              ([quality, count]) => (
                <span key={quality}>
                  {quality}: {count}
                </span>
              )
            )}
            <span style={{ marginLeft: "auto" }}>
              Sources: {report.data_sources.join(", ")}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  unit,
  positive,
}: {
  label: string;
  value: string;
  unit: string;
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
      <div
        style={{ fontSize: "0.7rem", color: "var(--gray-500)", marginBottom: 2 }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "1.5rem",
          fontWeight: 700,
          color: positive ? "var(--green-700)" : "inherit",
        }}
      >
        {value}
        <span style={{ fontSize: "0.75rem", fontWeight: 400, marginLeft: 4 }}>
          {unit}
        </span>
      </div>
    </div>
  );
}
