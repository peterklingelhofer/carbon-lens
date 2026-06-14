// Stable colour + label per normalized fuel key (matches the backend's
// emission_factors vocabulary). Fuels not listed fall back to a neutral grey.
export const FUEL_META: Record<string, { label: string; color: string }> = {
  solar: { label: "Solar", color: "#fbbf24" },
  wind: { label: "Wind", color: "#38bdf8" },
  hydro: { label: "Hydro", color: "#22d3ee" },
  nuclear: { label: "Nuclear", color: "#a78bfa" },
  geothermal: { label: "Geothermal", color: "#fb923c" },
  biomass: { label: "Biomass", color: "#84cc16" },
  natural_gas: { label: "Gas", color: "#f87171" },
  coal: { label: "Coal", color: "#9ca3af" },
  oil: { label: "Oil", color: "#9f1239" },
  petroleum: { label: "Oil", color: "#9f1239" },
  battery: { label: "Battery", color: "#34d399" },
  other: { label: "Other", color: "#64748b" },
};

export const fuelMeta = (key: string) => FUEL_META[key] ?? { label: key, color: "#64748b" };

// Live generation breakdown as a stacked share bar plus a top-fuel legend. Only
// shown for zones whose source reports a real fuel mix.
export function PowerMix({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown)
    .filter(([, mw]) => mw > 0)
    .sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, mw]) => sum + mw, 0);
  if (!entries.length || total <= 0) return null;
  const pct = (mw: number) => Math.round((mw / total) * 100);
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginBottom: 4 }}>Generation mix</div>
      <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden" }}>
        {entries.map(([fuel, mw]) => (
          <div
            key={fuel}
            title={`${fuelMeta(fuel).label}: ${pct(mw)}%`}
            style={{ width: `${(mw / total) * 100}%`, background: fuelMeta(fuel).color }}
          />
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 10px", marginTop: 6 }}>
        {entries.slice(0, 5).map(([fuel, mw]) => (
          <span
            key={fuel}
            style={{
              fontSize: "0.7rem",
              color: "#cbd5e1",
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                background: fuelMeta(fuel).color,
                display: "inline-block",
              }}
            />
            {fuelMeta(fuel).label} {pct(mw)}%
          </span>
        ))}
      </div>
    </div>
  );
}
