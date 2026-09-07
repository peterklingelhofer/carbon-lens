import { useSnapshot } from "../api/snapshot";
import { intensityColor } from "../lib/intensity";

// A few well-known regions spanning the range, dirtiest first, so the spread is
// the first thing a visitor sees. All five read from live grid-operator feeds
// (EIA and ENTSO-E), so the strip never has to caveat itself with "est.".
const REGIONS = [
  { provider: "aws", region: "us-east-1" },
  { provider: "aws", region: "eu-central-1" },
  { provider: "aws", region: "us-west-2" },
  { provider: "azure", region: "francecentral" },
  { provider: "azure", region: "norwayeast" },
];

/** The same five regions' live carbon intensity, as a compact strip. Sits on the
 *  dark hero and the globe's explainer card, so the colours are the raw scale
 *  rather than the theme-aware one. Renders nothing until the data is there. */
export function RegionSpread() {
  const { data: snapshot } = useSnapshot();
  if (!snapshot) return null;

  const rows = REGIONS.map(({ provider, region }) => {
    const key = `${provider}/${region}`;
    const reading = snapshot.intensities[key];
    const meta = snapshot.regions.find((r) => r.provider === provider && r.region === region);
    if (!reading || !meta || reading.quality !== "live") return null;
    return {
      key,
      location: meta.location,
      intensity: Math.round(reading.carbon_intensity_gco2_kwh),
    };
  }).filter((r): r is NonNullable<typeof r> => r !== null);

  // Below three the point (grids differ enormously) no longer lands, so say nothing.
  if (rows.length < 3) return null;

  return (
    <div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "0.5rem 1.5rem",
        }}
      >
        {rows.map((r) => (
          <div key={r.key} style={{ textAlign: "center" }}>
            <div
              style={{ fontSize: "1.5rem", fontWeight: 700, color: intensityColor(r.intensity) }}
            >
              {r.intensity}
            </div>
            <div style={{ fontSize: "0.8rem", opacity: 0.85 }}>{r.location}</div>
          </div>
        ))}
      </div>
      <p style={{ fontSize: "0.75rem", opacity: 0.7, margin: "0.6rem 0 0", textAlign: "center" }}>
        Grams of CO₂ per kilowatt-hour, from each grid's latest reading. Lower is cleaner.
      </p>
    </div>
  );
}
