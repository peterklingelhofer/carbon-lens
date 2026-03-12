import { Link } from "react-router-dom";
import { section as sectionFn, card as baseCard, grid3, badge } from "../styles";

const section: React.CSSProperties = { ...sectionFn(), padding: "3rem 2rem" };
const card: React.CSSProperties = { ...baseCard, padding: "2rem" };

export function Landing() {
  return (
    <div>
      {/* Hero */}
      <div
        style={{
          background: "linear-gradient(135deg, var(--green-700), var(--green-900))",
          color: "white",
          padding: "5rem 2rem 4rem",
          textAlign: "center",
        }}
      >
        <h1 style={{ fontSize: "3rem", margin: "0 0 1rem", fontWeight: 700 }}>
          The cloud runs on coal at night.
          <br />
          We fix that.
        </h1>
        <p
          style={{
            fontSize: "1.25rem",
            maxWidth: 700,
            margin: "0 auto 2rem",
            opacity: 0.9,
          }}
        >
          Carbon Mesh routes your compute to whichever region is physically running
          on the cleanest energy right now — verified by government grid data, not
          corporate press releases.
        </p>
        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <Link
            to="/route"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              background: "var(--surface)",
              color: "var(--green-800)",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Try the Router
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
            View Dashboard
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
          What Carbon Mesh Does Differently
        </h2>
        <p style={{ textAlign: "center", color: "var(--gray-500)", marginBottom: "2rem" }}>
          Instead of buying offsets after the fact, we move the compute to where the
          energy is already clean.
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
              Traditional cloud: Pick region &rarr; Run job &rarr; Buy carbon offsets later
            </div>
            <div style={{ color: "var(--green-700)", fontWeight: 600 }}>
              Carbon Mesh: &nbsp;&nbsp;&nbsp;&nbsp;Check grid data &rarr; Find cleanest
              region NOW &rarr; Run job there
            </div>
          </div>
        </div>

        <div style={grid3}>
          {[
            {
              title: "Government-Verified Data",
              desc: "We use official grid operator data (EIA, ENTSO-E, AEMO), not self-reported corporate numbers.",
            },
            {
              title: "Hourly, Not Annual",
              desc: "We track actual grid conditions per hour, not annual averages or offset spreadsheets.",
            },
            {
              title: "Multi-Cloud",
              desc: "Not locked to one provider. We arbitrage across AWS, GCP, and Azure — 75+ regions.",
            },
            {
              title: "11 Data Sources",
              desc: "Cascading through UK, EIA, AEMO, Grid India, ONS Brazil, Eskom, ENTSO-E, and more.",
            },
            {
              title: "Open Source",
              desc: "Transparent methodology. Anyone can verify our claims. The control plane is fully open.",
            },
            {
              title: "Price Competitive",
              desc: "Green doesn't cost more. Clean energy during off-peak is often the cheapest energy.",
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
            to="/route"
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
            Try the Green Router Now
          </Link>
        </div>
      </section>
    </div>
  );
}
