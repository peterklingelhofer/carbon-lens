import { Link } from "react-router-dom";
import { section as sectionFn, card as baseCard } from "../styles";

const section = sectionFn(820);
const card: React.CSSProperties = { ...baseCard, padding: "2rem" };
const h2: React.CSSProperties = { marginTop: 0, fontSize: "1.2rem" };
const p: React.CSSProperties = { color: "var(--gray-600)", fontSize: "0.95rem", lineHeight: 1.7 };
const li: React.CSSProperties = { color: "var(--gray-600)", fontSize: "0.95rem", lineHeight: 1.8 };

export function Methodology() {
  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem", textAlign: "center" }}>Methodology</h1>
      <p style={{ ...p, textAlign: "center", maxWidth: 640, margin: "0 auto 2.5rem" }}>
        How every number on this site is produced — and, just as importantly, where it's an estimate
        rather than a measurement. The short version: we read public grid-operator data, tag every
        reading with its source, and never hide an estimate behind a real one.
      </p>

      <div style={card}>
        <h2 style={h2}>What we measure</h2>
        <p style={p}>
          <strong>Carbon intensity</strong> is the grams of CO₂-equivalent emitted per kilowatt-hour of
          electricity on a given grid right now (gCO₂/kWh) — a <em>rate</em>, not a total. It's a
          <strong> location-based</strong> figure: the average intensity of the physical grid a region
          draws from, regardless of any renewable certificates bought against it. Lower is genuinely cleaner.
        </p>
      </div>

      <div style={{ ...card, marginTop: "1.5rem" }}>
        <h2 style={h2}>Where the numbers come from</h2>
        <p style={p}>
          For each grid zone we try data sources in priority order and use the first that covers it,
          tagging every response with a <code>source</code> field so provenance is always visible:
        </p>
        <ul style={{ paddingLeft: "1.2rem", margin: "0 0 0.5rem" }}>
          <li style={li}>
            <strong>Live (measured):</strong> read straight from a grid operator's real-time feed — EIA (US),
            ENTSO-E (Europe), UK Carbon Intensity, AEMO (Australia), GridStatus (US ISOs), Electricity Maps.
          </li>
          <li style={li}>
            <strong>Estimated (modelled):</strong> where no live feed is configured, a weather-based estimate
            (Open-Meteo) or a regional time-of-day heuristic. Clearly labelled <em>est.</em> everywhere it appears.
          </li>
          <li style={li}>
            <strong>Sample (fallback):</strong> static representative values, last resort so the API always returns
            something. Dropped from the published snapshot — the dashboard shows no sample data.
          </li>
        </ul>
        <p style={{ ...p, margin: 0 }}>
          The published <strong>snapshot</strong> is rebuilt on a schedule from these feeds; the "Data updated"
          timestamp on the globe and Status page shows its current age (GitHub's free scheduler refreshes it
          best-effort, so it can lag a few hours).
        </p>
      </div>

      <div style={{ ...card, marginTop: "1.5rem" }}>
        <h2 style={h2}>Renewable % is not the same as "clean"</h2>
        <p style={p}>
          "Renewable %" counts wind, solar, and hydro — but <strong>not nuclear</strong>. So a low-carbon
          nuclear/hydro grid (France, Sweden, Ontario) can show a modest renewable % while emitting very little
          CO₂, and a grid can be high-renewable yet still dirty when the rest is coal. <strong>Carbon intensity is
          the rigorous "how clean" measure</strong> — it's why the globe colours by it and the dashboard sorts by
          it by default. Treat renewable % as context, not the headline.
        </p>
      </div>

      <div style={{ ...card, marginTop: "1.5rem" }}>
        <h2 style={h2}>Estimates &amp; known limitations</h2>
        <ul style={{ paddingLeft: "1.2rem", margin: 0 }}>
          <li style={li}>
            The weather-based estimate infers renewables from <em>current</em> solar irradiance and wind only, so it
            understates steady hydro/nuclear baseload — it can read a near-zero renewable % for a grid that's actually
            very clean. Configure a live feed (e.g. an ENTSO-E token) for accurate fuel-mix data.
          </li>
          <li style={li}>
            Integer-looking values don't imply integer accuracy, especially for estimated zones.
          </li>
          <li style={li}>
            The carbon-aware scheduler's future windows use a simplified time-of-day model, not a real forecast.
          </li>
        </ul>
      </div>

      <div style={{ ...card, marginTop: "1.5rem" }}>
        <h2 style={h2}>Emissions reporting</h2>
        <p style={p}>
          The <Link to="/compliance" style={{ color: "var(--green-text)" }}>compliance</Link> draft maps your usage
          (service + region) to energy with published coefficients (Cloud Carbon Footprint / Etsy "Cloud Jewels",
          provider PUE figures), then multiplies by the grid's location-based intensity, structured per the GHG
          Protocol (Scope 2 + Scope 3 Cat 1). It's a <strong>first draft to build on, not an assured or audited
          report</strong>: market-based Scope 2 needs your own contracts (RECs/PPAs), and EU Taxonomy alignment is a
          simplified screen, not a determination.
        </p>
      </div>

      <div style={{ ...card, marginTop: "1.5rem" }}>
        <h2 style={h2}>What this is not</h2>
        <p style={{ ...p, margin: 0 }}>
          A free public tool for orientation and first drafts — not assured/audited reporting, and not financial,
          legal, or compliance advice. Where it estimates, it says so.
        </p>
      </div>

      <div style={{ textAlign: "center", marginTop: "2rem" }}>
        <Link
          to="/globe"
          style={{
            display: "inline-block",
            padding: "0.85rem 2.5rem",
            borderRadius: 8,
            background: "var(--btn-green)",
            color: "white",
            fontWeight: 600,
            fontSize: "1.05rem",
            textDecoration: "none",
          }}
        >
          🌍 Explore the live globe
        </Link>
      </div>
    </div>
  );
}
