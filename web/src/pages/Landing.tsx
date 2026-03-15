import { Link } from "react-router-dom";
import { section as sectionFn, card as baseCard, grid3, badge } from "../styles";

const section: React.CSSProperties = { ...sectionFn(), padding: "3rem 2rem" };
const card: React.CSSProperties = { ...baseCard, padding: "2rem" };

export function Landing() {
  return (
    <div>
      {/* Hero */}
      <style>{`
        .hero-title { font-size: 3rem; }
        .hero-subtitle { font-size: 1.25rem; }
        .hero-section { padding: 5rem 2rem 4rem; }
        @media (max-width: 600px) {
          .hero-title { font-size: 1.75rem !important; }
          .hero-subtitle { font-size: 1rem !important; }
          .hero-section { padding: 3rem 1rem 2.5rem !important; }
          .hero-cta { flex-direction: column !important; align-items: stretch !important; }
          .hero-cta a { text-align: center; }
        }
      `}</style>
      <div
        className="hero-section"
        style={{
          background: "linear-gradient(135deg, var(--green-700), var(--green-900))",
          color: "white",
          padding: "5rem 2rem 4rem",
          textAlign: "center",
        }}
      >
        <h1
          className="hero-title"
          style={{ fontSize: "3rem", margin: "0 0 1rem", fontWeight: 700 }}
        >
          Measure, report, and reduce
          <br />
          your cloud carbon footprint.
        </h1>
        <p
          className="hero-subtitle"
          style={{
            fontSize: "1.25rem",
            maxWidth: 700,
            margin: "0 auto 0.75rem",
            opacity: 0.9,
          }}
        >
          CSRD-compliant Scope 2 &amp; 3 emissions reporting for cloud infrastructure.
          Powered by 11 government-verified grid data sources — not corporate estimates.
        </p>
        <p
          className="hero-subtitle"
          style={{
            fontSize: "1rem",
            maxWidth: 600,
            margin: "0 auto 2rem",
            opacity: 0.7,
          }}
        >
          EU regulations now require companies to measure and disclose cloud
          emissions. Carbon Mesh makes it auditable, automated, and actionable.
        </p>
        <div className="hero-cta" style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <Link
            to="/compliance"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              background: "var(--surface)",
              color: "var(--green-800)",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Try Compliance Reporting
          </Link>
          <Link
            to="/dashboard"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              border: "2px solid rgba(255,255,255,0.4)",
              color: "white",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            View Live Grid Data
          </Link>
        </div>
      </div>

      {/* The "100% Renewable" Lie */}
      <section style={section}>
        <h2 style={{ textAlign: "center", fontSize: "2rem", marginBottom: "0.5rem" }}>
          The "100% Renewable" Lie
        </h2>
        <p style={{ textAlign: "center", color: "var(--gray-500)", marginBottom: "2rem" }}>
          Every major cloud provider claims "100% renewable." Here's what they actually do.
        </p>

        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Annual Matching Is Not Clean Computing</h3>
          <p>
            If a data center consumes 100 MWh of electricity in a year, the provider
            purchases 100 MWh of renewable energy certificates (RECs). On a spreadsheet,
            their carbon footprint nets to zero.
          </p>
          <p style={{ marginTop: "1rem" }}>
            But data centers run 24/7. When the sun sets and the wind stops, your servers
            draw power from the local grid. If that grid burns coal at 2 AM, your code runs
            on fossil fuels. The provider "offsets" that midnight pollution with surplus solar
            credits from a different state at noon.
          </p>
          <p
            style={{
              marginTop: "1rem",
              fontWeight: 600,
              color: "var(--green-700)",
            }}
          >
            This is not clean computing. This is carbon accounting.
          </p>
        </div>

        <div style={{ ...card, overflow: "auto" }}>
          <h3 style={{ marginTop: 0 }}>What the Big Three Actually Do</h3>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.9rem",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                <th style={{ textAlign: "left", padding: "0.75rem" }}>Provider</th>
                <th style={{ textAlign: "left", padding: "0.75rem" }}>Claim</th>
                <th style={{ textAlign: "left", padding: "0.75rem" }}>Reality</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: "1px solid var(--gray-100)" }}>
                <td style={{ padding: "0.75rem", fontWeight: 600 }}>AWS</td>
                <td style={{ padding: "0.75rem" }}>"100% renewable matched" (2023)</td>
                <td style={{ padding: "0.75rem" }}>
                  Annual matching via RECs. "Data Center Alley" in Virginia runs 60-85%
                  on fossil fuels at any given hour.
                </td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--gray-100)" }}>
                <td style={{ padding: "0.75rem", fontWeight: 600 }}>Google Cloud</td>
                <td style={{ padding: "0.75rem" }}>"24/7 CFE by 2030"</td>
                <td style={{ padding: "0.75rem" }}>
                  Most transparent. ~64% CFE globally. Finland/Iowa exceed 90%.
                  Singapore/Virginia below 30%.
                </td>
              </tr>
              <tr>
                <td style={{ padding: "0.75rem", fontWeight: 600 }}>Azure</td>
                <td style={{ padding: "0.75rem" }}>"100/100/0 by 2030"</td>
                <td style={{ padding: "0.75rem" }}>
                  100% electricity, 100% of time, 0 carbon. Ambitious but not yet met.
                  Investing in small modular nuclear.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* How Carbon Mesh is Different */}
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginBottom: "0.5rem",
            marginTop: "3rem",
          }}
        >
          How Carbon Mesh Works
        </h2>
        <p style={{ textAlign: "center", color: "var(--gray-500)", marginBottom: "2rem" }}>
          Measure your actual cloud emissions. Get audit-ready reports. Optimize automatically.
        </p>

        <div style={card}>
          <div
            style={{
              fontFamily: "var(--mono)",
              fontSize: "0.9rem",
              background: "var(--surface-alt)",
              padding: "1.5rem",
              borderRadius: 8,
              lineHeight: 1.8,
            }}
          >
            <div style={{ color: "var(--gray-400)" }}>
              Traditional: Guess emissions &rarr; Buy offsets &rarr; Put in annual report
            </div>
            <div style={{ color: "var(--green-700)", fontWeight: 600 }}>
              Carbon Mesh: Ingest cloud usage &rarr; Calculate with real grid data &rarr; CSRD-ready report
            </div>
          </div>
        </div>

        <div style={grid3}>
          {[
            {
              title: "CSRD / ESRS E1 Compliant",
              desc: "Reports aligned with EU Corporate Sustainability Reporting Directive. Scope 2 (location + market-based) and Scope 3 Category 1.",
            },
            {
              title: "GHG Protocol Methodology",
              desc: "Every calculation follows the GHG Protocol Corporate Standard with full audit trail — data source, timestamp, methodology version.",
            },
            {
              title: "Government-Verified Data",
              desc: "11 official grid operator sources (EIA, ENTSO-E, AEMO, POSOCO). Not estimates — actual measured emissions factors.",
            },
            {
              title: "Multi-Cloud Coverage",
              desc: "Ingest usage from AWS Cost Explorer, GCP Billing, and Azure Cost Management. 75+ regions across all three providers.",
            },
            {
              title: "Hourly Granularity",
              desc: "Track actual grid conditions per hour, not annual averages. Identify when and where your workloads generate the most emissions.",
            },
            {
              title: "Actionable Optimization",
              desc: "Beyond reporting: route workloads to the cleanest region in real-time. Reduce emissions, not just measure them.",
            },
          ].map((item) => (
            <div key={item.title} style={card}>
              <span style={badge}>{item.title}</span>
              <p style={{ marginTop: "0.75rem", fontSize: "0.95rem" }}>{item.desc}</p>
            </div>
          ))}
        </div>

        {/* Data Sources */}
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginTop: "3rem",
            marginBottom: "1rem",
          }}
        >
          Data Sources
        </h2>
        <div style={{ ...card, overflow: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.85rem",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid var(--gray-200)" }}>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Provider</th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Coverage</th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Resolution</th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Auth</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["UK Carbon Intensity", "UK (18 zones)", "30 min", "Free, no key"],
                ["EIA (US DOE)", "US (60+ balancing authorities)", "Hourly", "Free key"],
                ["AEMO", "Australia (5 states)", "5 min", "Free, no key"],
                ["Grid India", "India (5 regions)", "5 min", "Free, no key"],
                ["ONS Brazil", "Brazil (5 regions)", "Real-time", "Free, no key"],
                ["Eskom", "South Africa", "Heuristic", "Free, no key"],
                ["GridStatus.io", "US ISOs (7)", "5 min", "Free key"],
                ["ENTSO-E", "Europe (36+ countries)", "Hourly", "Free token"],
                ["Open-Meteo", "Worldwide (40+ zones)", "Hourly", "Free, no key"],
                ["Electricity Maps", "Global (200+ zones)", "Real-time", "Paid key"],
              ].map(([name, coverage, res, auth]) => (
                <tr
                  key={name}
                  style={{ borderBottom: "1px solid var(--gray-100)" }}
                >
                  <td style={{ padding: "0.5rem", fontWeight: 500 }}>{name}</td>
                  <td style={{ padding: "0.5rem" }}>{coverage}</td>
                  <td style={{ padding: "0.5rem" }}>{res}</td>
                  <td style={{ padding: "0.5rem" }}>{auth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* CTA */}
        <div style={{ textAlign: "center", margin: "3rem 0 1rem" }}>
          <Link
            to="/compliance"
            style={{
              display: "inline-block",
              padding: "0.85rem 2.5rem",
              borderRadius: 8,
              background: "var(--green-600)",
              color: "white",
              fontWeight: 600,
              fontSize: "1.1rem",
              textDecoration: "none",
            }}
          >
            Generate Your First Compliance Report
          </Link>
          <p style={{ marginTop: "0.75rem", color: "var(--gray-400)", fontSize: "0.85rem" }}>
            Free demo with mock data — no account required
          </p>
        </div>
      </section>
    </div>
  );
}
