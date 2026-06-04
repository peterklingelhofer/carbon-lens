import { describe, expect, it } from "vitest";
import { qualityFromSource } from "./snapshot";

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
