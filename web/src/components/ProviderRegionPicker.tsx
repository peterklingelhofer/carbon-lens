import type { CloudRegion } from "../api/types";
import { PROVIDERS, providerButtonStyle } from "../lib/providers";

// The provider-pill row + region <select> shared by the clean-window heatmap and
// the region-comparison panel. Selecting a provider resets the region to that
// provider's default; the region list comes from the snapshot/API.
export function ProviderRegionPicker({
  provider,
  region,
  regions,
  onSelectProvider,
  onSelectRegion,
  regionLabel,
  showLocation = false,
}: {
  provider: string;
  region: string;
  regions: CloudRegion[] | undefined;
  onSelectProvider: (p: string) => void;
  onSelectRegion: (r: string) => void;
  regionLabel: string;
  showLocation?: boolean;
}) {
  return (
    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "0.75rem 0" }}>
      {PROVIDERS.map((p) => (
        <button
          type="button"
          key={p}
          onClick={() => onSelectProvider(p)}
          aria-pressed={provider === p}
          style={providerButtonStyle(provider === p)}
        >
          {p}
        </button>
      ))}
      <select
        value={region}
        onChange={(e) => onSelectRegion(e.target.value)}
        aria-label={regionLabel}
        style={{
          padding: "0.3rem 0.6rem",
          borderRadius: 6,
          border: "1px solid var(--gray-200)",
          background: "var(--surface)",
          color: "inherit",
          fontSize: "0.8rem",
        }}
      >
        {regions ? (
          regions.map((r) => (
            <option key={r.region} value={r.region}>
              {r.region}
              {showLocation && r.location ? ` — ${r.location}` : ""}
            </option>
          ))
        ) : (
          <option value={region}>{region}</option>
        )}
      </select>
    </div>
  );
}
