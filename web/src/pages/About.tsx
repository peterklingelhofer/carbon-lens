import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { snapshotEnabled, useSnapshot } from "../api/snapshot";
import { timeAgo } from "../lib/format";
import { card as baseCard, section as sectionFn } from "../styles";

const section = sectionFn(820);
const card: React.CSSProperties = { ...baseCard, padding: "2rem" };

// The API runs on Render's Oregon region, which draws from the Pacific
// Northwest grid (Bonneville Power Administration). AWS us-west-2 is the same
// Oregon / US-NW-BPAT zone, so its live reading stands in for our own grid.
const OREGON = { provider: "aws", region: "us-west-2" };

function OregonGridLive() {
  const { data: snapshot } = useSnapshot();
  const fromSnapshot = snapshot?.intensities[`${OREGON.provider}/${OREGON.region}`];
  const { data: fromApi } = useQuery({
    queryKey: ["oregon-grid"],
    queryFn: () => api.carbonIntensity(OREGON.provider, OREGON.region),
    enabled: !snapshotEnabled,
    refetchInterval: 5 * 60 * 1000,
  });
  const i = fromSnapshot ?? fromApi;

  return (
    <div
      style={{
        marginTop: "1.25rem",
        padding: "1.25rem 1.5rem",
        borderRadius: 8,
        background: "var(--surface-alt)",
        border: "1px solid var(--green-200)",
      }}
    >
      <div
        style={{
          fontSize: "0.75rem",
          color: "var(--gray-500)",
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: "0.75rem",
        }}
      >
        <span
          aria-hidden
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: i ? "var(--green-500)" : "var(--gray-300)",
            display: "inline-block",
          }}
        />
        Oregon grid right now · US-NW-BPAT
      </div>

      {i ? (
        <>
          <div style={{ display: "flex", gap: "2.5rem", flexWrap: "wrap" }}>
            <div>
              <div
                style={{
                  fontSize: "2rem",
                  fontWeight: 700,
                  color: "var(--green-text)",
                }}
              >
                {i.renewable_percentage}%
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>renewable</div>
            </div>
            <div>
              <div style={{ fontSize: "2rem", fontWeight: 700 }}>
                {i.carbon_intensity_gco2_kwh}
                <span style={{ fontSize: "0.9rem", fontWeight: 400, marginLeft: 4 }}>gCO₂/kWh</span>
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--gray-500)" }}>carbon intensity</div>
            </div>
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--gray-400)",
              marginTop: "0.75rem",
            }}
          >
            Measured from {i.source}
            {i.quality === "estimated" && " (estimated — upstream feed intermittent)"} · updated{" "}
            {timeAgo(i.timestamp)}
          </div>
        </>
      ) : (
        <div style={{ fontSize: "0.9rem", color: "var(--gray-400)" }}>
          Fetching the Oregon grid's live reading…
        </div>
      )}
    </div>
  );
}

export function About() {
  return (
    <div style={section}>
      <h1 style={{ marginBottom: "0.5rem", textAlign: "center" }}>About CarbonLens</h1>
      <p
        style={{
          color: "var(--gray-500)",
          marginBottom: "2.5rem",
          textAlign: "center",
          maxWidth: 640,
          marginLeft: "auto",
          marginRight: "auto",
        }}
      >
        CarbonLens reads live grid-operator data and turns it into one comparable number per cloud
        region, so the real carbon cost of where you run is easy to see and act on. Free to use, no
        account required.
      </p>

      <div style={card}>
        <h2 style={{ marginTop: 0, fontSize: "1.2rem" }}>Why it's free</h2>
        <p style={{ color: "var(--gray-600)", fontSize: "0.95rem" }}>
          Most of what CarbonLens needs already exists: grid operators publish what they're
          generating, and the readings are public. CarbonLens just reads those official feeds, turns
          them into one comparable number per region, and shows it. Keeping that open felt more
          useful than locking it behind a sign-up — the whole point is to make the grid's real
          carbon cost easy to see.
        </p>
        <ul
          style={{
            color: "var(--gray-600)",
            fontSize: "0.95rem",
            lineHeight: 1.8,
            paddingLeft: "1.2rem",
            margin: "0.5rem 0 0",
          }}
        >
          <li>No account, no card, no trial clock — open the site and use it.</li>
          <li>
            The API answers without a key on the public demo. There's a generous fair-use limit so
            the service stays responsive for everyone.
          </li>
          <li>
            Built on free, public data sources. Where a region has no live feed, the estimate is
            clearly labelled rather than hidden.
          </li>
        </ul>
      </div>

      <div style={{ ...card, marginTop: "1.5rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.2rem" }}>Our own footprint</h2>
        <p style={{ color: "var(--gray-600)", fontSize: "0.95rem" }}>
          CarbonLens tries to practise what it measures. It's a deliberately lightweight service: a
          small API that reads public grid feeds and caches the results, plus a static site served
          from a CDN. There's no heavy compute behind it — no model training, no crypto, no
          sprawling data pipeline — so it draws very little power to run, and it sleeps after a
          short idle period and wakes on demand. The few-second wait on the first request is that
          wake-up.
        </p>
        <p
          style={{
            color: "var(--gray-600)",
            fontSize: "0.95rem",
            marginBottom: 0,
          }}
        >
          The API runs on a free Render instance in their Oregon region, which draws from the
          Pacific Northwest grid (Bonneville Power Administration, zone US-NW-BPAT). That grid is
          hydro-heavy and usually among the cleaner ones in North America. Rather than ask you to
          take that on faith, here's what it's emitting right now — the same live, measured reading
          the rest of the site uses, not an annual "matched to renewable" claim:
        </p>

        <OregonGridLive />

        <p
          style={{
            color: "var(--gray-400)",
            fontSize: "0.8rem",
            marginTop: "0.75rem",
            marginBottom: 0,
          }}
        >
          This is the grid's latest carbon intensity (location-based) — measured, not matched. It's
          a stand-in from the same Oregon / US-NW-BPAT zone our server sits in, so it moves hour to
          hour with the actual grid.
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
