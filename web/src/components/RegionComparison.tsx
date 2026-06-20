import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { greenestRegion, snapshotEnabled, useSnapshot } from "../api/snapshot";
import { DEFAULT_REGION, PROVIDERS } from "../lib/providers";
import { card, muted } from "../styles";
import { InfoTip } from "./InfoTip";
import { IntensityValue } from "./IntensityValue";
import { ProviderRegionPicker } from "./ProviderRegionPicker";

function Stat({
  title,
  subject,
  intensity,
  renewable,
}: {
  title: string;
  subject: string;
  intensity?: number;
  renewable?: number;
}) {
  return (
    <div style={{ flex: "1 1 180px", minWidth: 0 }}>
      <div style={{ ...muted, textTransform: "uppercase", fontSize: "0.68rem" }}>{title}</div>
      <div style={{ fontWeight: 600, fontFamily: "var(--mono)", margin: "0.15rem 0" }}>
        {subject}
      </div>
      {intensity != null ? (
        <>
          <IntensityValue value={intensity} size="1.4rem" />
          {renewable != null && (
            <div style={{ ...muted, color: "var(--green-text)" }}>{renewable}% renewable</div>
          )}
        </>
      ) : (
        <span style={muted}>—</span>
      )}
    </div>
  );
}

// "You're running here -- is somewhere greener?" Compares a chosen region against
// the greenest available right now and shows the carbon a switch would save.
export function RegionComparison() {
  const [provider, setProvider] = useState("aws");
  const [region, setRegion] = useState(DEFAULT_REGION.aws);

  const { data: snapshot } = useSnapshot();

  const { data: apiRegions } = useQuery({
    queryKey: ["regions", provider],
    queryFn: () => api.regions(provider),
    staleTime: 60 * 60_000,
    enabled: !snapshotEnabled,
  });
  const { data: apiCurrent } = useQuery({
    queryKey: ["carbon", provider, region],
    queryFn: () => api.carbonIntensity(provider, region),
    enabled: !snapshotEnabled && !!region,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const { data: route } = useQuery({
    queryKey: ["route-greenest"],
    queryFn: () =>
      api.route({ constraints: { providers: PROVIDERS, carbon_weight: 1, cost_weight: 0 } }),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: !snapshotEnabled,
  });

  // Snapshot-first: region list, the chosen region's intensity, and the greenest region
  // (carbon-weighted routing = lowest current intensity) are all derived from the CDN
  // snapshot; the live API is only used when no snapshot is configured.
  const regions = snapshot ? snapshot.regions.filter((r) => r.provider === provider) : apiRegions;
  const current = snapshot ? snapshot.intensities[`${provider}/${region}`] : apiCurrent;
  const greenest = greenestRegion(snapshot, PROVIDERS) ?? route?.recommended;
  const curV = current?.carbon_intensity_gco2_kwh;
  const greenV = greenest?.carbon_intensity_gco2_kwh;
  const isGreenest = greenest && greenest.provider === provider && greenest.region === region;
  const savings =
    curV != null && greenV != null && curV > 0 ? Math.max(0, ((curV - greenV) / curV) * 100) : 0;

  return (
    <div style={{ ...card, marginBottom: "2rem" }}>
      <h2
        style={{ margin: "0 0 0.25rem", fontSize: "1.1rem", display: "flex", alignItems: "center" }}
      >
        Compare your region
        <InfoTip
          label="region comparison"
          text="Pick where you run today to see how it compares to the greenest region available right now, and how much carbon switching would save."
        />
      </h2>

      <ProviderRegionPicker
        provider={provider}
        region={region}
        regions={regions}
        onSelectProvider={(p) => {
          setProvider(p);
          setRegion(DEFAULT_REGION[p]);
        }}
        onSelectRegion={setRegion}
        regionLabel="Your region"
      />

      <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
        <Stat
          title="Your region"
          subject={`${provider}/${region}`}
          intensity={curV}
          renewable={current?.renewable_percentage}
        />
        <Stat
          title="Greenest available"
          subject={greenest ? `${greenest.provider}/${greenest.region}` : "…"}
          intensity={greenV}
          renewable={greenest?.renewable_percentage}
        />
      </div>

      {curV != null && greenV != null && (
        <div
          style={{
            marginTop: "1rem",
            padding: "0.6rem 0.9rem",
            borderRadius: 8,
            background: "var(--surface-alt)",
            fontSize: "0.9rem",
          }}
        >
          {isGreenest || savings < 1 ? (
            <span>✅ You're already on the greenest available region.</span>
          ) : (
            <span>
              Switching to{" "}
              <strong>
                {greenest?.provider}/{greenest?.region}
              </strong>{" "}
              would cut carbon intensity by{" "}
              <strong style={{ color: "var(--green-text)" }}>~{savings.toFixed(0)}%</strong>.
            </span>
          )}
        </div>
      )}
    </div>
  );
}
