import { Link } from "react-router-dom";
import { InfoTip } from "../components/InfoTip";
import { card as baseCard, sectionStyle } from "../styles";

const section: React.CSSProperties = { ...sectionStyle(), padding: "3rem 2rem" };
const card: React.CSSProperties = { ...baseCard, padding: "2rem" };

/** Section headings. Centered headings are reserved for the one interlude
 *  section, so the page doesn't read as a stack of identical blocks. */
const heading = (align: "left" | "center" = "left"): React.CSSProperties => ({
  fontSize: align === "center" ? "2rem" : "1.6rem",
  textAlign: align,
  marginTop: "3rem",
  marginBottom: "0.75rem",
});

const featureTitle: React.CSSProperties = {
  margin: 0,
  fontSize: "1rem",
  fontWeight: 600,
  borderLeft: "3px solid var(--btn-green)",
  paddingLeft: "0.6rem",
};

const legend: React.CSSProperties = {
  fontSize: "0.8rem",
  color: "var(--gray-400)",
  margin: "0.75rem 0 0",
  lineHeight: 1.6,
};

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
          background: "var(--green-800)",
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
          If you're hosting a website, you may as well host it on 100% renewable energy. Carbon Lens
          provides observability into which cloud regions emit the least carbon by aggregating grid
          data from dozens of sources, making what was an opaque decision a clear one.
        </p>
        <p
          className="hero-subtitle"
          style={{
            fontSize: "1.25rem",
            maxWidth: 720,
            margin: "0 auto 0.75rem",
            opacity: 0.92,
          }}
        >
          Every cloud region runs on a local power grid. Carbon Lens reads how much CO₂ that grid
          emits per kilowatt-hour right now (its <strong>carbon intensity</strong>) from live
          grid-operator data. Lower means greener.
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
          75+ regions across AWS, GCP, and Azure. Route your workloads to the cleanest one, then
          turn the same data into the emissions reports regulators are starting to require.
        </p>
        <div
          className="hero-cta"
          style={{ display: "flex", gap: "1rem", justifyContent: "center" }}
        >
          <Link
            to="/"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              // Fixed white (not --surface) - the hero background is always dark
              // green, so dark-green text on white is high-contrast in both modes.
              background: "#ffffff",
              color: "var(--green-800)",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Explore the live globe
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
        <p
          style={{
            fontSize: "0.9rem",
            margin: "1.5rem auto 0",
            opacity: 0.8,
          }}
        >
          Free to use, no account required. A public service for anyone working to measure and cut
          cloud emissions.{" "}
          <Link to="/about" style={{ color: "white", textDecoration: "underline" }}>
            Why it's free
          </Link>
        </p>
      </div>

      <section style={section}>
        <h2 style={{ ...heading(), marginTop: 0 }}>"100% renewable" is a yearly average</h2>
        <p style={{ color: "var(--gray-500)", marginBottom: "1.5rem", maxWidth: 680 }}>
          Providers match their annual electricity use with renewable certificates. That doesn't
          tell you whether your 2 a.m. job ran on wind or on gas. Carbon Lens reports the grid's
          measured carbon intensity, hour by hour.
        </p>

        {/* Plain-language explainer: the "credits" argument + the acronyms decoded */}
        <div style={card}>
          <h3 style={{ marginTop: 0, fontSize: "1.15rem" }}>
            How the "100% renewable" claim actually works
          </h3>
          <p style={{ color: "var(--gray-600)", fontSize: "0.95rem" }}>
            Over a year, a provider buys enough <strong>renewable-energy certificates</strong>{" "}
            (RECs), or signs enough power-purchase agreements, to match its total electricity use.
            The certificates and the electricity are counted separately, so a data center can draw
            from a gas-heavy grid at midnight and still "count" as 100% renewable on its annual
            report. That money does fund new renewables, and the claim is an accounting match. It
            doesn't show that clean electrons ran your job.
          </p>

          <h3 style={{ fontSize: "1.15rem", marginBottom: "0.5rem" }}>
            Why measuring is starting to matter
          </h3>
          <p
            style={{
              color: "var(--gray-600)",
              fontSize: "0.95rem",
              marginTop: 0,
            }}
          >
            Regulators are moving from annual offsets to measured emissions:
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
              <strong>CSRD</strong> (the EU's Corporate Sustainability Reporting Directive): large
              companies must report audited emissions data.
            </li>
            <li>
              <strong>SEC climate rule</strong>: US rules pushing public companies to disclose
              climate-related emissions.
            </li>
            <li>
              <strong>California SB 253</strong>: large companies operating in California must
              report their greenhouse-gas emissions.
            </li>
          </ul>
          <p style={{ color: "var(--gray-600)", fontSize: "0.95rem", margin: 0 }}>
            Carbon Lens turns live grid data into a first draft of those reports.
          </p>
        </div>

        <h2 style={heading()}>What you can build with it</h2>
        <div style={card}>
          <dl style={{ display: "grid", gap: "1.25rem", margin: 0 }}>
            {[
              {
                title: "Carbon intensity API",
                desc: "Latest grams of CO₂ per kWh for 75+ cloud regions in one request, with the data source tagged on every response.",
                tip: "An API is how one program asks another for data. Here, your code asks ours for a region's live carbon number. gCO₂/kWh = grams of CO₂ emitted per kilowatt-hour of electricity.",
              },
              {
                title: "Emissions reporting",
                desc: "Draft the emissions reports regulators are starting to require, built from the same live data, with a documented method and a data-quality summary.",
                tip: "Greenhouse-gas reporting follows the GHG Protocol standard. 'Scope 2' = emissions from the electricity you use; 'Scope 3' = emissions from services you buy (cloud included). Rules like the EU's CSRD, the US SEC climate rule, and California's SB 253 increasingly require it.",
              },
              {
                title: "Carbon-aware routing",
                desc: "Find the greenest cloud region across AWS, GCP, and Azure, weighing carbon against cost.",
                tip: "'Routing' means choosing where to run a job. You set priorities (e.g. favour low carbon, cap cost) and it ranks every region. Acting on the result is up to you.",
              },
              {
                title: "8 live grid integrations",
                desc: "UK, EIA, OpenElectricity/AEMO, IESO/AESO, Taipower, GridStatus, ENTSO-E, and Electricity Maps pull data straight from grid operators. Other regions use clearly-labelled estimates.",
                tip: "A grid operator runs a region's electricity grid and publishes what it's generating right now. 'Live integration' means we read that official feed directly, rather than estimating.",
              },
              {
                title: "Live updates feed",
                desc: "A continuous stream of carbon-intensity updates to build on: dashboards, alerts, or shifting flexible jobs to cleaner hours.",
                tip: "Delivered over a WebSocket, a connection that stays open so the server can push new readings to your app the instant they change, instead of you repeatedly asking.",
              },
              {
                title: "Carbon targets (beta)",
                desc: "Set a carbon target for your workloads and get checked against live data, with summary reports.",
                tip: "Modelled on an SLA (service-level agreement), a measurable promise about a service. Here that promise is a carbon ceiling, e.g. 'stay under 100 gCO₂/kWh'. Beta: checks run in memory and reset on restart; not a third-party-assured standard.",
              },
            ].map((item) => (
              <div key={item.title}>
                <dt style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                  <span style={featureTitle}>{item.title}</span>
                  <InfoTip label={item.title} text={item.tip} />
                </dt>
                <dd style={{ margin: "0.5rem 0 0", fontSize: "0.95rem" }}>{item.desc}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* What makes a grid greener - the one centered interlude */}
        <h2 style={heading("center")}>What makes a grid greener</h2>
        <p
          style={{
            textAlign: "center",
            color: "var(--gray-500)",
            maxWidth: 700,
            margin: "0 auto 1.5rem",
          }}
        >
          Electricity comes from a mix of sources: wind, solar, hydro, nuclear, gas, coal. When more
          of a region's power is coming from clean sources, each kilowatt-hour emits less CO₂, so
          it's greener. That mix shifts hour to hour with the weather and demand, and a sunny, windy
          afternoon is far cleaner than a still night running on gas. Carbon Lens reads that live
          mix from each grid operator and turns it into one number:{" "}
          <strong>carbon intensity</strong>, in grams of CO₂ per kWh.
        </p>

        {/* How It Works */}
        <h2 style={heading()}>How it works</h2>
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
                title: "Look up",
                desc: "Ask for any cloud provider and region and get its live carbon intensity, renewable share, and the source behind the number.",
              },
              {
                step: "2",
                title: "Compare",
                desc: "Set your priorities (e.g. greenest within a cost limit) and get the best region to run in. It ranks options; moving the workload is still your call.",
              },
              {
                step: "3",
                title: "Report",
                desc: "Provide your cloud usage and get a draft emissions report from live grid data, with the method and data quality shown.",
              },
              {
                step: "4",
                title: "Monitor",
                desc: "Set a carbon target and have workloads checked against live data, with summary reports. (Beta.)",
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
                <h3 style={{ margin: "0.5rem 0 0.25rem", fontSize: "1rem" }}>{s.title}</h3>
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
        <h2 style={heading()}>Data sources</h2>
        <p
          style={{
            margin: "0 0 1rem",
            color: "var(--gray-500)",
            fontSize: "0.9rem",
          }}
        >
          How every number is produced, and where it's an estimate:{" "}
          <Link
            to="/methodology"
            style={{
              color: "var(--green-text)",
              textDecoration: "underline",
              fontWeight: 600,
            }}
          >
            read the methodology
          </Link>
        </p>
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
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Type</th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Access</th>
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
                <tr key={name} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                  <td style={{ padding: "0.5rem", fontWeight: 500 }}>{name}</td>
                  <td style={{ padding: "0.5rem" }}>{coverage}</td>
                  <td style={{ padding: "0.5rem" }}>{res}</td>
                  <td style={{ padding: "0.5rem" }}>
                    {auth?.includes("no key") ? (
                      <span style={{ color: "var(--green-text)", fontWeight: 600 }}>{auth}</span>
                    ) : (
                      <span>{auth}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={legend}>
            <strong>Type.</strong> Live API: read directly from the grid operator's official
            real-time feed. Heuristic: an estimate from typical regional values and time of day.
            Weather estimate: inferred from local solar and wind conditions rather than a direct
            carbon measurement.
          </p>
          <p style={legend}>
            <strong>Access.</strong> "No key" works out of the box; a free key or token needs a free
            sign-up; a paid key needs a paid plan with that provider.
          </p>
          <p style={legend}>
            <strong>Balancing authority / ISO.</strong> The body that runs a regional electricity
            grid and publishes what it's generating, such as PJM (US Mid-Atlantic), CAISO
            (California), or National Grid ESO (Great Britain). Carbon is measured at that grid
            rather than inside the datacenter.
          </p>
        </div>

        {/* CTA */}
        <div style={{ textAlign: "center", margin: "3rem 0 1rem" }}>
          <Link
            to="/"
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
            See it live on the globe
          </Link>
          <p
            style={{
              marginTop: "0.75rem",
              color: "var(--gray-500)",
              fontSize: "0.85rem",
            }}
          >
            Live grid-operator data, updated continuously. Or{" "}
            <Link
              to="/api-explorer"
              style={{
                color: "var(--green-text)",
                textDecoration: "underline",
              }}
            >
              explore the API
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
