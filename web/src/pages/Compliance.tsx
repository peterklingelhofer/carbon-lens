import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { ComplianceReport } from "../api/types";
import { InfoTip } from "../components/InfoTip";
import { DATA_QUALITY_TIP_RICH } from "../copy";
import { card, providerChip, section as sectionFn } from "../styles";

const section = sectionFn(1100);

// A ready-to-edit example matching the exact columns the upload expects, so users can
// shape their own spreadsheet to match instead of guessing. Rows mirror the demo data.
const SAMPLE_USAGE_CSV = `provider,region,service,resource_type,usage_quantity,usage_unit,period_start,period_end
aws,us-east-1,ec2,m6i.xlarge,7200,vcpu_hours,2026-05-01,2026-06-01
aws,eu-west-1,s3,standard,500000,gb_hours,2026-05-01,2026-06-01
gcp,us-central1,compute-engine,n2-standard-4,4800,vcpu_hours,2026-05-01,2026-06-01
gcp,us-central1,cloud-functions,default,2000000,requests,2026-05-01,2026-06-01
azure,eastus,virtual-machines,Standard_D4s_v5,3600,vcpu_hours,2026-05-01,2026-06-01
`;

function downloadSampleCsv() {
  const blob = new Blob([SAMPLE_USAGE_CSV], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "carbonlens-sample-usage.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function Compliance() {
  const queryClient = useQueryClient();
  const [orgId] = useState("demo");
  const [orgName] = useState("Demo Organization");
  const [activeReport, setActiveReport] = useState<ComplianceReport | null>(null);
  const [step, setStep] = useState<"idle" | "ingesting" | "calculating" | "generating">("idle");
  const [csvFile, setCsvFile] = useState<File | null>(null);

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
        period_start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
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
        report_name: `CSRD Report - ${new Date().toISOString().slice(0, 10)}`,
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

  // Real-data path: upload a usage CSV, then run the SAME calculate → report
  // pipeline (live grid intensity) the demo uses.
  const csvPipeline = useMutation({
    mutationFn: async () => {
      if (!csvFile) throw new Error("Choose a CSV file first.");
      await api.compliance.uploadCsv(orgId, csvFile);
      await api.compliance.calculate(orgId);
      return api.compliance.generateReport({
        org_id: orgId,
        org_name: orgName,
        report_name: `Usage CSV Report - ${new Date().toISOString().slice(0, 10)}`,
      });
    },
    onSuccess: (report) => {
      setActiveReport(report);
      queryClient.invalidateQueries({ queryKey: ["compliance-reports"] });
    },
  });

  return (
    <div style={section}>
      <h1
        style={{
          marginBottom: "0.5rem",
          display: "flex",
          alignItems: "center",
        }}
      >
        Emissions reporting
        <InfoTip
          label="emissions reporting"
          text="Turns your cloud usage into a draft greenhouse-gas emissions report, built from real grid data. Aligned with the GHG Protocol (the standard accounting framework) and the EU's CSRD / ESRS E1 disclosure rules. It's a useful first draft, not an assured/audited report."
        />
      </h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        Turn your cloud usage into a draft emissions report, calculated from real grid data - with
        the method and data quality shown.
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
        <h2 style={{ margin: 0, fontSize: "1.1rem" }}>Option 1 - Try it with demo data</h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: 0 }}>
          Ingests a sample mid-size SaaS workload, calculates emissions using the latest grid carbon
          intensity from the live data sources, and generates a CSRD-aligned report - so you can see
          the output without uploading anything.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button
            type="button"
            onClick={runFullPipeline}
            disabled={step !== "idle" || csvPipeline.isPending}
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
            {calculateMutation.data.total_emissions_kgco2e.toFixed(4)} kgCO₂e) - Sources:{" "}
            {calculateMutation.data.data_sources_used.join(", ")}
          </div>
        )}
      </div>

      {/* Real-data path: upload your own usage CSV */}
      <div
        style={{
          ...card,
          marginBottom: "2rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: "1.1rem",
            display: "flex",
            alignItems: "center",
          }}
        >
          Option 2 - Use your own usage CSV
          <InfoTip
            label="usage CSV"
            text="Upload a CSV of your real cloud usage and get the same report, calculated against live grid intensity per region. It's processed in memory for this report, not stored long-term."
          />
        </h2>
        <p style={{ color: "var(--gray-500)", fontSize: "0.85rem", margin: 0 }}>
          Columns:{" "}
          <code
            style={{
              fontSize: "0.8rem",
              background: "var(--surface-alt)",
              padding: "1px 5px",
              borderRadius: 4,
            }}
          >
            provider, region, service, usage_quantity, usage_unit, period_start, period_end
          </code>{" "}
          (<code>resource_type</code> optional). Units: <code>vcpu_hours</code>,{" "}
          <code>gb_hours</code>, <code>requests</code>, <code>gb_transferred</code>, or{" "}
          <code>kwh</code>. Dates are ISO 8601 (e.g. 2026-05-01).{" "}
          <button
            type="button"
            onClick={downloadSampleCsv}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              color: "var(--btn-green)",
              font: "inherit",
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            Download a sample CSV →
          </button>
        </p>
        <div
          style={{
            display: "flex",
            gap: "0.75rem",
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="Usage CSV file"
            onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
            style={{ fontSize: "0.85rem" }}
          />
          <button
            type="button"
            onClick={() => csvPipeline.mutate()}
            disabled={!csvFile || csvPipeline.isPending || step !== "idle"}
            style={{
              padding: "0.6rem 1.5rem",
              borderRadius: 8,
              border: "none",
              background: "var(--btn-green)",
              color: "white",
              fontWeight: 600,
              cursor: !csvFile || csvPipeline.isPending ? "not-allowed" : "pointer",
              opacity: !csvFile || csvPipeline.isPending || step !== "idle" ? 0.6 : 1,
            }}
          >
            {csvPipeline.isPending ? "Calculating…" : "Generate from my CSV"}
          </button>
        </div>
        {csvPipeline.isError && (
          <div role="alert" style={{ color: "var(--red-400, #f87171)", fontSize: "0.8rem" }}>
            {(csvPipeline.error as Error).message}
          </div>
        )}
      </div>

      {/* Active Report */}
      {activeReport && <ReportView report={activeReport} />}

      {/* Report history */}
      {reports && reports.length > 0 && (
        <div style={card}>
          <h2 style={{ margin: "0 0 1rem", fontSize: "1.1rem" }}>Report History</h2>
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
                  Total kgCO₂e
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
                <tr key={r.id} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                  <td style={{ padding: "0.5rem", fontSize: "0.85rem" }}>
                    {/* A real button so the row is keyboard-operable; the row-level
                        onClick it replaces was mouse-only. */}
                    <button
                      type="button"
                      onClick={async () => {
                        const full = await api.compliance.getReport(r.id, orgId);
                        setActiveReport(full);
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        padding: 0,
                        font: "inherit",
                        color: "var(--green-text)",
                        fontWeight: 500,
                        cursor: "pointer",
                        textAlign: "left",
                        textDecoration: "underline",
                      }}
                    >
                      {r.report_name}
                    </button>
                  </td>
                  <td style={{ padding: "0.5rem", fontSize: "0.8rem" }}>
                    {r.period_start.slice(0, 10)} - {r.period_end.slice(0, 10)}
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
  // Same-origin (proxied) base for the export download links.
  const BASE_URL =
    import.meta.env.VITE_API_URL || (typeof window !== "undefined" ? window.location.origin : "");
  // Demo reports are built from a synthetic usage fixture (not a real CSV upload).
  const isDemo = !report.report_name.toLowerCase().includes("csv");

  return (
    <div style={{ ...card, marginBottom: "2rem" }}>
      {isDemo && (
        <div
          style={{
            display: "inline-block",
            fontSize: "0.7rem",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            color: "var(--amber)",
            border: "1px solid var(--amber)",
            borderRadius: 4,
            padding: "2px 8px",
            marginBottom: "1rem",
          }}
        >
          Demo data - synthetic usage, not a real workload
        </div>
      )}
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
          <h2 style={{ margin: 0, fontSize: "1.2rem" }}>{report.report_name}</h2>
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
          unit="kgCO₂e"
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
        style={{
          fontSize: "0.95rem",
          marginBottom: "0.75rem",
          marginTop: 0,
          display: "flex",
          alignItems: "center",
        }}
      >
        GHG Protocol scope breakdown
        <InfoTip
          label="GHG Protocol scopes"
          text="The GHG Protocol sorts emissions into scopes. Scope 2 = emissions from the electricity you use; Scope 3 Cat 1 = emissions embedded in services you purchase (cloud included). Location-based uses the local grid's average intensity; market-based reflects contracts you've bought (RECs/PPAs). kgCO₂e = kilograms of CO₂-equivalent (all greenhouse gases expressed as CO₂)."
        />
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
              <th style={{ textAlign: "right", padding: "0.5rem" }}>kgCO₂e</th>
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
      <p
        style={{
          fontSize: "0.75rem",
          color: "var(--gray-400)",
          margin: "-0.75rem 0 1.25rem",
        }}
      >
        Note: with no supplier-specific contracts (RECs/PPAs) supplied, market-based mirrors
        location-based here - a real market-based figure would apply your contractual instruments.
      </p>

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
            {Object.entries(report.scope2_location_by_provider).map(([provider, kgco2e]) => (
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
                <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>{kgco2e.toFixed(4)}</div>
                <div style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>kgCO₂e</div>
              </div>
            ))}
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
        <div
          style={{
            fontWeight: 600,
            fontSize: "0.9rem",
            marginBottom: 4,
            display: "inline-flex",
            alignItems: "center",
          }}
        >
          EU Taxonomy Status:{" "}
          {report.eu_taxonomy_aligned ? "Aligned" : "Eligible (not yet aligned)"}
          <InfoTip
            label="EU Taxonomy status"
            text="Simplified screening only: this flags 'aligned' purely from a high renewable share. Real EU Taxonomy alignment also requires technical screening criteria, Do-No-Significant-Harm, and minimum safeguards - none of which are assessed here. Treat as indicative, not a determination."
          />
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--gray-600)" }}>{report.taxonomy_notes}</div>
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
            <span
              style={{
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
              }}
            >
              Data quality:
              <InfoTip label="data quality" text={DATA_QUALITY_TIP_RICH} />
            </span>
            {Object.entries(report.data_quality_summary).map(([quality, count]) => (
              <span key={quality}>
                {quality}: {count}
              </span>
            ))}
            <span style={{ marginLeft: "auto" }}>Sources: {report.data_sources.join(", ")}</span>
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
        style={{
          fontSize: "0.7rem",
          color: "var(--gray-500)",
          marginBottom: 2,
        }}
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
        <span style={{ fontSize: "0.75rem", fontWeight: 400, marginLeft: 4 }}>{unit}</span>
      </div>
    </div>
  );
}
