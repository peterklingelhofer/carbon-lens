import { describe, expect, it } from "vitest";
import { chooseByMode, readCarbonHeaders } from "./carbonMode";

describe("readCarbonHeaders", () => {
  it("parses mode and intensity", () => {
    const h = new Headers({ "X-Carbon-Mode": "reduced", "X-Carbon-Intensity": "420" });
    expect(readCarbonHeaders(h)).toEqual({ mode: "reduced", intensityGco2Kwh: 420 });
  });

  it("defaults to full when the header is absent", () => {
    expect(readCarbonHeaders(new Headers())).toEqual({ mode: "full", intensityGco2Kwh: null });
  });

  it("treats a non-numeric intensity as null", () => {
    const h = new Headers({ "X-Carbon-Mode": "full", "X-Carbon-Intensity": "n/a" });
    expect(readCarbonHeaders(h).intensityGco2Kwh).toBeNull();
  });
});

describe("chooseByMode", () => {
  it("picks full vs reduced", () => {
    expect(chooseByMode("full", "1080p", "480p")).toBe("1080p");
    expect(chooseByMode("reduced", "1080p", "480p")).toBe("480p");
  });
});
