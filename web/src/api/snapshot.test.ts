import { describe, expect, it } from "vitest";
import type { CarbonSnapshot } from "./snapshot";
import {
  greenestRegion,
  gridZonesFromSnapshot,
  qualityFromSource,
  zoneIntensityFromSnapshot,
} from "./snapshot";

// Minimal snapshot fixture exercising the derive-from-snapshot helpers.
const SNAP = {
  regions: [
    { provider: "aws", region: "us-east-1", grid_zone: "US-MIDA-PJM", location: "Virginia" },
    { provider: "gcp", region: "us-east4", grid_zone: "US-MIDA-PJM", location: "Virginia" },
    { provider: "gcp", region: "europe-north1", grid_zone: "FI", location: "Finland" },
  ],
  intensities: {
    "aws/us-east-1": {
      grid_zone: "US-MIDA-PJM",
      carbon_intensity_gco2_kwh: 500,
      renewable_percentage: 10,
    },
    "gcp/us-east4": {
      grid_zone: "US-MIDA-PJM",
      carbon_intensity_gco2_kwh: 500,
      renewable_percentage: 10,
    },
    "gcp/europe-north1": {
      grid_zone: "FI",
      carbon_intensity_gco2_kwh: 40,
      renewable_percentage: 92,
      marginal_intensity_gco2_kwh: 80,
    },
  },
} as unknown as CarbonSnapshot;

describe("gridZonesFromSnapshot", () => {
  it("groups regions by grid zone with their provider/region keys", () => {
    const zones = gridZonesFromSnapshot(SNAP);
    expect(zones.map((z) => z.grid_zone)).toEqual(["FI", "US-MIDA-PJM"]); // sorted
    const pjm = zones.find((z) => z.grid_zone === "US-MIDA-PJM");
    expect(pjm?.regions).toEqual(["aws/us-east-1", "gcp/us-east4"]);
    expect(pjm?.location).toBe("Virginia");
  });

  it("returns [] without a snapshot", () => {
    expect(gridZonesFromSnapshot(undefined)).toEqual([]);
  });
});

describe("zoneIntensityFromSnapshot", () => {
  it("returns the intensity for any region on the zone", () => {
    const fi = zoneIntensityFromSnapshot(SNAP, "FI");
    expect(fi?.carbon_intensity_gco2_kwh).toBe(40);
    expect(fi?.marginal_intensity_gco2_kwh).toBe(80);
    expect(zoneIntensityFromSnapshot(SNAP, "NOPE")).toBeUndefined();
  });
});

describe("greenestRegion", () => {
  it("picks the lowest-intensity region among the given providers", () => {
    const best = greenestRegion(SNAP, ["aws", "gcp", "azure"]);
    expect(best).toEqual({
      provider: "gcp",
      region: "europe-north1",
      carbon_intensity_gco2_kwh: 40,
      renewable_percentage: 92,
    });
  });

  it("respects the provider filter", () => {
    const best = greenestRegion(SNAP, ["aws"]);
    expect(best?.region).toBe("us-east-1"); // only aws considered
  });
});

describe("qualityFromSource", () => {
  it("classifies heuristic and weather estimates as 'estimated'", () => {
    expect(qualityFromSource("grid_india_heuristic")).toBe("estimated");
    expect(qualityFromSource("eskom_heuristic")).toBe("estimated");
    expect(qualityFromSource("open_meteo")).toBe("estimated");
  });

  it("classifies mock / error fallbacks as 'mock'", () => {
    expect(qualityFromSource("mock")).toBe("mock");
    expect(qualityFromSource("electricity_maps_error")).toBe("mock");
  });

  it("classifies real grid-operator feeds as 'live'", () => {
    expect(qualityFromSource("uk_carbon_intensity")).toBe("live");
    expect(qualityFromSource("eia")).toBe("live");
    expect(qualityFromSource("entsoe")).toBe("live");
  });
});
