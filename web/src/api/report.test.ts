import { describe, expect, it } from "vitest";
import type { GreenRegion } from "./report";
import { sitingFromGreenest } from "./report";

const GREENEST: GreenRegion[] = [
  { provider: "gcp", region: "europe-north1", location: "Finland", typical_gco2_kwh: 40 },
  { provider: "aws", region: "us-east-1", location: "Virginia", typical_gco2_kwh: 400 },
  { provider: "azure", region: "westeurope", location: "Netherlands", typical_gco2_kwh: 200 },
];

describe("sitingFromGreenest", () => {
  it("ranks by typical intensity and computes annual kg at the given load", () => {
    const rec = sitingFromGreenest(GREENEST, ["aws", "gcp", "azure"], 1000, 30);
    expect(rec.options.map((o) => o.region)).toEqual(["europe-north1", "westeurope", "us-east-1"]);
    expect(rec.recommended.region).toBe("europe-north1");
    // 1000 W = 1 kW; annual_kg = typical x 1 x 8760 / 1000 -> FI: 40 * 8760 / 1000 = 350.4
    expect(rec.options[0].annual_kg).toBe(350.4);
    // saved vs worst = (400 - 40) x 1 x 8760 / 1000 = 3153.6
    expect(rec.annual_kg_saved_vs_worst).toBe(3153.6);
    expect(rec.power_watts).toBe(1000);
    expect(rec.days_analyzed).toBe(30);
  });

  it("filters to the selected providers and omits annual kg without a load", () => {
    const rec = sitingFromGreenest(GREENEST, ["gcp"], 0, 14);
    expect(rec.options.map((o) => o.provider)).toEqual(["gcp"]);
    expect(rec.options[0].annual_kg).toBeNull();
    expect(rec.annual_kg_saved_vs_worst).toBeNull();
    expect(rec.power_watts).toBeNull();
  });
});
