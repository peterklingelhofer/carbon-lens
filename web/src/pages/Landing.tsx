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
          How green is your cloud
          <br />
          region, right now?
        </h1>
        <p
          className="hero-subtitle"
          style={{
            fontSize: "1.25rem",
            maxWidth: 720,
            margin: "0 auto 0.75rem",
            opacity: 0.92,
          }}
        >
          Every cloud region runs on a local power grid. CarbonLens measures how much
          CO₂ that grid emits per kilowatt-hour right now — its <strong>carbon
          intensity</strong> — from live grid-operator data. Lower means greener.
        </p>
        <p
          className="hero-subtitle"
          style={{
            fontSize: "1rem",
            maxWidth: 620,
            margin: "0 auto 2rem",
            opacity: 0.75,
          }}
        >
          75+ regions across AWS, GCP, and Azure. Route your workloads to the cleanest
          one — and turn the same data into the emissions reports regulators are
          starting to require.
        </p>
        <div
          className="hero-cta"
          style={{ display: "flex", gap: "1rem", justifyContent: "center" }}
        >
          <Link
            to="/globe"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              // Fixed white (not --surface) — the hero gradient is always dark
              // green, so dark-green text on white is high-contrast in both modes.
              background: "#ffffff",
              color: "var(--green-800)",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            🌍 Explore the live globe
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
            See live grid data
          </Link>
        </div>
      </div>

      <section style={section}>
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginBottom: "0.5rem",
          }}
        >
          "100% renewable" is a yearly average
        </h2>
        <p
          style={{
            textAlign: "center",
            color: "var(--gray-500)",
            marginBottom: "2rem",
            maxWidth: 680,
            marginLeft: "auto",
            marginRight: "auto",
          }}
        >
          Providers match their annual electricity use with renewable certificates.
          That doesn't tell you whether your 2 a.m. job actually ran on wind or on gas.
          CarbonLens reports the grid's real carbon intensity, hour by hour.
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
            <div style={{ color: "var(--gray-500)" }}>
              Cloud providers: Run 24/7 &rarr; Buy RECs at year-end &rarr;
              Claim "100% renewable" on annual report
            </div>
            <div style={{ color: "var(--green-text)", fontWeight: 600 }}>
              CarbonLens: &nbsp;Query real-time grid data &rarr; Know actual
              gCO2/kWh right now &rarr; Make informed decisions
            </div>
          </div>
        </div>

        {/* Plain-language explainer: the "credits" argument + the acronyms decoded */}
        <div style={{ ...card, marginTop: "1.5rem" }}>
          <h3 style={{ marginTop: 0, fontSize: "1.15rem" }}>
            How the "100% renewable" claim actually works
          </h3>
          <p style={{ color: "var(--gray-600)", fontSize: "0.95rem" }}>
            Over a year, a provider buys enough <strong>renewable-energy certificates</strong>{" "}
            (RECs), or signs enough power-purchase agreements, to match its total electricity
            use. The certificates and the electricity are counted separately — so a data
            center can draw from a gas-heavy grid at midnight and still "count" as 100%
            renewable on its annual report. It's real money funding real renewables, but it's
            an accounting match, not proof that clean electrons ran your job.
          </p>

          <h3 style={{ fontSize: "1.15rem", marginBottom: "0.5rem" }}>
            Why measuring is starting to matter
          </h3>
          <p style={{ color: "var(--gray-600)", fontSize: "0.95rem", marginTop: 0 }}>
            Regulators increasingly want the real numbers, not just the annual offset:
          </p>
          <ul
            style={{
              color: "var(--gray-600)",
              fontSize: "0.95rem",
              lineHeight: 1.7,
              paddingLeft: "1.2rem",
              margin: "0 0 1rem",
            }}
          >
            <li>
              <strong>CSRD</strong> — the EU's Corporate Sustainability Reporting Directive:
              large companies must report audited, real-world emissions.
            </li>
            <li>
              <strong>SEC climate rule</strong> — US rules pushing public companies to disclose
              climate-related emissions.
            </li>
            <li>
              <strong>California SB 253</strong> — large companies operating in California must
              report their greenhouse-gas emissions.
            </li>
          </ul>
          <p style={{ color: "var(--gray-600)", fontSize: "0.95rem", margin: 0 }}>
            CarbonLens turns live grid data into a defensible first draft of those reports —
            emissions measured, not matched.
          </p>
        </div>

        <div style={grid3}>
          {[
            {
              title: "Carbon Intensity API",
              desc: "gCO2/kWh for 75+ cloud regions in one REST call. A cascading chain of 11 providers with automatic fallback — and every response is tagged with the source that produced it.",
            },
            {
              title: "Compliance Reporting",
              desc: "Draft CSRD / SEC Climate / California SB 253 emissions reports. Scope 2 (location-based) + Scope 3 Cat 1, GHG-Protocol-structured, with a documented methodology and data-quality summary.",
            },
            {
              title: "Carbon-Aware Routing",
              desc: "Find the greenest cloud region across AWS, GCP, and Azure. Multi-objective scoring balances carbon intensity and cost.",
            },
            {
              title: "6 Live Grid Integrations",
              desc: "EIA (US), ENTSO-E (Europe), AEMO (Australia), UK Carbon Intensity, GridStatus, and Electricity Maps fetch real grid-operator data. Heuristic and mock sources cover the rest — each clearly labeled.",
            },
            {
              title: "Live WebSocket Feed",
              desc: "Stream carbon intensity updates over a WebSocket. Build dashboards, trigger alerts, or shift workloads when the grid gets dirty.",
            },
            {
              title: "Green SLA Monitoring (Beta)",
              desc: "Define carbon targets, run on-demand and background compliance checks against live grid data, and generate attestation-style summary reports. (In-memory; not yet a third-party-assured standard.)",
            },
          ].map((item) => (
            <div key={item.title} style={card}>
              <span style={badge}>{item.title}</span>
              <p style={{ marginTop: "0.75rem", fontSize: "0.95rem" }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>

        {/* What makes a grid greener */}
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginTop: "3rem",
            marginBottom: "0.75rem",
          }}
        >
          What makes a grid greener?
        </h2>
        <p
          style={{
            textAlign: "center",
            color: "var(--gray-500)",
            maxWidth: 700,
            margin: "0 auto 1.5rem",
          }}
        >
          Electricity comes from a mix of sources — wind, solar, hydro, nuclear, gas,
          coal. When more of a region's power is coming from clean sources, each
          kilowatt-hour emits less CO₂, so it's greener. That mix shifts hour to hour
          with the weather and demand: a sunny, windy afternoon is far cleaner than a
          still night running on gas. CarbonLens reads that live mix from each grid
          operator and turns it into one number — <strong>carbon intensity</strong>,
          in grams of CO₂ per kWh.
        </p>

        {/* How It Works */}
        <h2
          style={{
            textAlign: "center",
            fontSize: "2rem",
            marginTop: "3rem",
            marginBottom: "1rem",
          }}
        >
          How It Works
        </h2>
        <div style={card}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1.5rem",
              textAlign: "center",
            }}
          >
            {[
              {
                step: "1",
                title: "Query",
                desc: "Call our API with a cloud provider and region. Get real-time carbon intensity, renewable percentage, and data source.",
              },
              {
                step: "2",
                title: "Route",
                desc: "Or let us find the greenest region. Post your constraints, we score every option and return the best match.",
              },
              {
                step: "3",
                title: "Report",
                desc: "Ingest your cloud usage data. We calculate Scope 2+3 emissions using real grid data and generate compliance reports.",
              },
              {
                step: "4",
                title: "Monitor",
                desc: "Beta: set carbon SLAs, run on-demand and background compliance checks, and generate attestation-style summary reports.",
              },
            ].map((s) => (
              <div key={s.step}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: "50%",
                    background: "var(--btn-green)",
                    color: "white",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: "1.1rem",
                    marginBottom: "0.5rem",
                  }}
                >
                  {s.step}
                </div>
                <h3 style={{ margin: "0.5rem 0 0.25rem", fontSize: "1rem" }}>
                  {s.title}
                </h3>
                <p
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--gray-500)",
                    margin: 0,
                  }}
                >
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
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
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Provider
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Coverage
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Type
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>
                  Auth
                </th>
              </tr>
            </thead>
            <tbody>
              {[
                ["UK Carbon Intensity", "Great Britain (18 zones)", "Live API", "Free, no key"],
                ["EIA (US DOE)", "US (60+ balancing authorities)", "Live API", "Free key"],
                ["AEMO", "Australia (5 states)", "Live API", "Free, no key"],
                ["Grid India", "India (5 regions)", "Heuristic", "Free, no key"],
                ["ONS Brazil", "Brazil (5 regions)", "Heuristic", "Free, no key"],
                ["Eskom", "South Africa", "Heuristic", "Free, no key"],
                ["GridStatus.io", "US ISOs (7)", "Live API", "Paid key"],
                ["ENTSO-E", "Europe (36+ countries)", "Live API", "Free token"],
                ["Open-Meteo", "Worldwide (40+ zones)", "Weather estimate", "Free, no key"],
                ["Electricity Maps", "Global (200+ zones)", "Live API", "Paid key"],
              ].map(([name, coverage, res, auth]) => (
                <tr
                  key={name}
                  style={{ borderBottom: "1px solid var(--gray-100)" }}
                >
                  <td style={{ padding: "0.5rem", fontWeight: 500 }}>{name}</td>
                  <td style={{ padding: "0.5rem" }}>{coverage}</td>
                  <td style={{ padding: "0.5rem" }}>{res}</td>
                  <td style={{ padding: "0.5rem" }}>
                    {auth?.includes("no key") ? (
                      <span style={{ color: "var(--green-text)", fontWeight: 600 }}>
                        {auth}
                      </span>
                    ) : (
                      <span>{auth}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* CTA */}
        <div style={{ textAlign: "center", margin: "3rem 0 1rem" }}>
          <Link
            to="/globe"
            style={{
              display: "inline-block",
              padding: "0.85rem 2.5rem",
              borderRadius: 8,
              background: "var(--btn-green)",
              color: "white",
              fontWeight: 600,
              fontSize: "1.1rem",
              textDecoration: "none",
            }}
          >
            🌍 See it live on the globe
          </Link>
          <p
            style={{
              marginTop: "0.75rem",
              color: "var(--gray-500)",
              fontSize: "0.85rem",
            }}
          >
            Real grid-operator data, updated continuously — or{" "}
            <Link
              to="/api-explorer"
              style={{ color: "var(--green-text)", textDecoration: "underline" }}
            >
              explore the API
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
