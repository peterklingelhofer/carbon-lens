import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useSnapshot } from "../api/snapshot";
import { InfoTip } from "../components/InfoTip";
import { RegionSpread } from "../components/RegionSpread";
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

const body: React.CSSProperties = { color: "var(--gray-600)", fontSize: "0.95rem" };

// The quantitative claims on this page are read from the same snapshot they
// describe, so they can't drift out of date the way hardcoded copy does.
function useSiteFacts() {
  const { data: snapshot } = useSnapshot();
  return useMemo(() => {
    if (!snapshot) return null;
    const readings = Object.values(snapshot.intensities);
    const live = readings.filter((i) => i.quality === "live").length;
    const shifts = Object.values(snapshot.best_time ?? {})
      .map((b) => b.shift_savings_pct ?? 0)
      .sort((a, b) => a - b);
    const median = shifts.length ? shifts[Math.floor(shifts.length / 2)] : null;
    return {
      regions: snapshot.regions.length,
      providers: new Set(snapshot.regions.map((r) => r.provider)).size,
      live,
      estimated: readings.length - live,
      medianShift: median === null ? null : Math.round(median),
      bestShift: shifts.length ? Math.round(shifts[shifts.length - 1]) : null,
    };
  }, [snapshot]);
}

export function Landing() {
  const facts = useSiteFacts();

  return (
    <div>
      {/* Hero */}
      <style>{`
        .hero-title { font-size: 3rem; }
        .hero-subtitle { font-size: 1.15rem; }
        .hero-section { padding: 4rem 2rem 3.5rem; }
        @media (max-width: 600px) {
          .hero-title { font-size: 1.75rem !important; }
          .hero-subtitle { font-size: 1rem !important; }
          .hero-section { padding: 2.5rem 1rem 2.5rem !important; }
          .hero-cta { flex-direction: column !important; align-items: stretch !important; }
          .hero-cta a { text-align: center; }
        }
      `}</style>
      <div
        className="hero-section"
        style={{
          background: "var(--green-800)",
          color: "white",
          padding: "4rem 2rem 3.5rem",
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
            fontSize: "1.15rem",
            maxWidth: 700,
            margin: "0 auto 2rem",
            opacity: 0.92,
          }}
        >
          Every data centre runs on its local power grid, and grids differ by more than tenfold.
          Carbon Lens reads each grid's live output and shows what your region is emitting this
          hour, so you can pick a cleaner one, run flexible jobs at cleaner times, and put real
          numbers in your emissions report.
        </p>

        <div style={{ margin: "0 auto 2rem", maxWidth: 720 }}>
          <RegionSpread />
        </div>

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
            to="/regions"
            style={{
              padding: "0.75rem 2rem",
              borderRadius: 8,
              border: "2px solid rgba(255,255,255,0.4)",
              color: "white",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            See every region
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
        <h2 style={{ ...heading(), marginTop: 0 }}>Renewable hosting is an accounting claim</h2>
        <p style={{ color: "var(--gray-500)", marginBottom: "1.5rem", maxWidth: 680 }}>
          "Runs on 100% renewable energy" almost always describes a year of paperwork, not the
          electricity reaching the machine. The grid is physical, and it's what actually emits.
        </p>

        <div style={card}>
          <h3 style={{ marginTop: 0, fontSize: "1.15rem" }}>How the claim works</h3>
          <p style={body}>
            Over a year, a provider buys enough <strong>renewable-energy certificates</strong>{" "}
            (RECs), or signs enough power-purchase agreements, to match its total electricity use.
            The certificates and the electricity are counted separately, so a data centre can draw
            from a gas-heavy grid at midnight and still count as 100% renewable on its annual
            report. That money does fund new renewables, and the claim is a fair accounting match.
            It doesn't show that clean electrons ran your job.
          </p>

          <h3 style={{ fontSize: "1.15rem", marginBottom: "0.5rem" }}>
            Why switching to a green host isn't the whole answer
          </h3>
          <p style={{ ...body, marginTop: 0, marginBottom: 0 }}>
            A host with strong renewable commitments still draws from whatever grid its building
            sits on. A server in Frankfurt runs on the German grid whether it's rented from a big
            cloud or a green-branded provider, and that grid is several times dirtier per
            kilowatt-hour than one in Norway or Québec. Picking a genuinely clean grid is the larger
            lever, and it's available on every provider. Carbon Lens covers hosts like Hetzner, OVH
            and Scaleway alongside AWS, Azure and Google Cloud for exactly that comparison.
          </p>
        </div>

        <h2 style={heading()}>Three things you can do with it</h2>
        <div style={card}>
          <h3 style={{ marginTop: 0, fontSize: "1.15rem" }}>1. Pick a cleaner region</h3>
          <p style={body}>
            This is the big one, and it's a one-time decision. The spread between the dirtiest and
            cleanest regions is often more than tenfold, so the same server can emit a fraction of
            what it does today purely by running somewhere else. For new workloads with no
            data-residency constraint, it costs nothing to choose well.{" "}
            <Link to="/regions" style={{ color: "var(--green-text)", fontWeight: 600 }}>
              Compare every region
            </Link>
            .
          </p>

          <h3 style={{ fontSize: "1.15rem", marginBottom: "0.5rem" }}>
            2. Run flexible jobs at cleaner times
          </h3>
          <p style={{ ...body, marginTop: 0 }}>
            A grid's mix shifts hour to hour with weather and demand. Work that doesn't need a fixed
            start time (nightly batch jobs, model training, CI pipelines) can wait for a cleaner
            window.
            {facts?.medianShift != null && facts.bestShift != null ? (
              <>
                {" "}
                Across the regions here, moving a daily job to the cleanest hour saves about{" "}
                <strong>{facts.medianShift}%</strong> in the median region, and up to{" "}
                <strong>{facts.bestShift}%</strong> in the most variable ones. On an already-clean
                grid like Québec's it saves almost nothing, because there's little to avoid.
              </>
            ) : (
              <>
                {" "}
                How much this saves depends heavily on the grid, and on a clean grid it's little.
              </>
            )}{" "}
            <Link to="/best-time" style={{ color: "var(--green-text)", fontWeight: 600 }}>
              Find the greenest window
            </Link>
            .
          </p>

          <h3 style={{ fontSize: "1.15rem", marginBottom: "0.5rem" }}>
            3. Put real numbers in your reporting
          </h3>
          <p style={{ ...body, marginTop: 0, marginBottom: 0 }}>
            Greenhouse-gas reporting asks for a location-based figure: what the grid you drew from
            actually emitted. That's the number this site measures, so it can turn your cloud usage
            into a first draft with the method and data quality shown.{" "}
            <Link to="/report" style={{ color: "var(--green-text)", fontWeight: 600 }}>
              Draft a report
            </Link>
            .
          </p>
        </div>

        <p style={{ ...body, color: "var(--gray-500)", fontSize: "0.9rem" }}>
          Worth being plain about scale: a small website or blog emits very little either way, and
          moving it won't change much. The tonnes are in compute-heavy work, so that's where this is
          worth your time.
        </p>

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

        <h2 style={heading()}>Why measuring is starting to matter</h2>
        <div style={card}>
          <p style={{ ...body, marginTop: 0 }}>
            Emissions accounting is moving from annual averages toward measured, time-matched
            electricity. The <strong>GHG Protocol</strong>, the standard the whole field reports
            against, is revising its Scope 2 rules and has consulted on requiring{" "}
            <strong>hourly matching</strong>: proving clean generation in the same hour the power
            was used, rather than over a year. If that lands, the hour-by-hour grid figure stops
            being a nice extra and becomes the number that counts.
          </p>
          <p style={body}>Where the rules stand today:</p>
          <ul style={{ ...body, lineHeight: 1.7, paddingLeft: "1.2rem", margin: "0 0 1rem" }}>
            <li>
              <strong>California SB 253</strong> is in force. Companies above $1B in revenue doing
              business in California file their first Scope 1 and 2 emissions by 10 November 2026,
              with Scope 3 following in 2027.
            </li>
            <li>
              <strong>The EU's CSRD</strong> still requires audited sustainability reporting, though
              February 2026's Omnibus package cut its scope considerably: it now applies to
              companies above 1,000 employees and €450M turnover, for financial years from 2027.
            </li>
            <li>
              <strong>The US SEC climate rule</strong> is going the other way. It was adopted in
              2024, stayed, and the Commission proposed rescinding it in 2026, so it isn't a live
              requirement.
            </li>
          </ul>
          <p style={{ ...body, margin: 0 }}>
            Regulation moves in both directions, which is why the durable case here is the standard
            rather than any one rule: measured, location-based intensity is what credible reporting
            is built on, and it's what a company asking about its own footprint actually needs.
          </p>
        </div>

        <h2 style={heading()}>For developers</h2>
        <div style={card}>
          <dl style={{ display: "grid", gap: "1.25rem", margin: 0 }}>
            {[
              {
                title: "Carbon intensity API",
                desc: `Latest grams of CO₂ per kWh for ${facts ? `${facts.regions} cloud regions` : "every cloud region"} in one request, with the data source tagged on every response.`,
                tip: "An API is how one program asks another for data. Here, your code asks ours for a region's live carbon number. gCO₂/kWh = grams of CO₂ emitted per kilowatt-hour of electricity.",
              },
              {
                title: "Carbon-aware routing",
                desc: "Rank every region by your own priorities, weighing carbon against cost, and get the best one to run in.",
                tip: "'Routing' means choosing where to run a job. You set priorities (e.g. favour low carbon, cap cost) and it ranks every region. Acting on the result is up to you.",
              },
              {
                title: "Emissions reporting",
                desc: "Draft GHG-Protocol Scope 2 and 3 reports from the same live data, with a documented method and a data-quality summary.",
                tip: "Greenhouse-gas reporting follows the GHG Protocol standard. 'Scope 2' = emissions from the electricity you use; 'Scope 3' = emissions from services you buy (cloud included).",
              },
              {
                title: "Live grid integrations",
                desc: "UK, EIA, ENTSO-E, OpenElectricity/AEMO, IESO and AESO pull data straight from grid operators. Other regions use clearly-labelled estimates.",
                tip: "A grid operator runs a region's electricity grid and publishes what it's generating right now. 'Live integration' means we read that official feed directly, rather than estimating.",
              },
              {
                title: "Live updates feed",
                desc: "A continuous stream of carbon-intensity updates to build on: dashboards, alerts, or shifting flexible jobs to cleaner hours.",
                tip: "Delivered over a WebSocket, a connection that stays open so the server can push new readings to your app the instant they change, instead of you repeatedly asking.",
              },
              {
                title: "Carbon targets (beta)",
                desc: "Set a carbon ceiling for your workloads and get checked against live data, with summary reports.",
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

        {/* Data Sources */}
        <h2 style={heading()}>Data sources</h2>
        <p
          style={{
            margin: "0 0 1rem",
            color: "var(--gray-500)",
            fontSize: "0.9rem",
          }}
        >
          {facts
            ? `Of the ${facts.regions} regions published right now, ${facts.live} are read from a live grid-operator feed and ${facts.estimated} are labelled estimates. `
            : "Every reading is tagged with the source that produced it. "}
          How each number is produced, and where it's an estimate:{" "}
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
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Source</th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Coverage</th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>Type</th>
                <th style={{ textAlign: "left", padding: "0.5rem" }}>On this site</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["ENTSO-E", "Europe", "Live feed", "Yes"],
                ["EIA (US DOE)", "United States", "Live feed", "Yes"],
                ["UK Carbon Intensity", "Great Britain", "Live feed", "Yes"],
                ["OpenElectricity / AEMO", "Australia", "Live feed", "Yes"],
                ["IESO", "Ontario, Canada", "Live feed", "Yes"],
                ["AESO", "Alberta, Canada", "Live feed", "Yes"],
                ["Open-Meteo", "Worldwide", "Weather estimate", "Yes"],
                ["Regional heuristics", "India, Brazil, South Africa, Québec", "Estimate", "Yes"],
                ["Taipower", "Taiwan", "Live feed", "Self-host"],
                ["GridStatus.io", "US ISOs", "Live feed", "Self-host (paid key)"],
                ["Electricity Maps", "Global", "Live feed", "Self-host (paid key)"],
              ].map(([name, coverage, res, here]) => (
                <tr key={name} style={{ borderBottom: "1px solid var(--gray-100)" }}>
                  <td style={{ padding: "0.5rem", fontWeight: 500 }}>{name}</td>
                  <td style={{ padding: "0.5rem" }}>{coverage}</td>
                  <td style={{ padding: "0.5rem" }}>{res}</td>
                  <td style={{ padding: "0.5rem" }}>
                    {here === "Yes" ? (
                      <span style={{ color: "var(--green-text)", fontWeight: 600 }}>{here}</span>
                    ) : (
                      <span style={{ color: "var(--gray-500)" }}>{here}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={legend}>
            <strong>Type.</strong> Live feed: read directly from the grid operator's official
            real-time data. Weather estimate: inferred from local solar and wind conditions rather
            than a direct carbon measurement. Estimate: typical regional values by time of day.
          </p>
          <p style={legend}>
            <strong>On this site.</strong> "Self-host" means the integration is built and tested but
            needs a key this public deployment doesn't use, so those regions fall back to an
            estimate here. Running your own copy with a key switches them on.
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
              to="/api"
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
