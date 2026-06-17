import { describe, expect, it } from "vitest";
import { isCleanSurplus } from "./surplus";

describe("isCleanSurplus", () => {
  it("flags renewables-dominant, low-carbon, clean-margin grids", () => {
    expect(isCleanSurplus(95, 30, 20)).toBe(true);
    expect(isCleanSurplus(90, 40, null)).toBe(true);
  });

  it("does not flag when fossil sets the margin", () => {
    expect(isCleanSurplus(90, 40, 400)).toBe(false);
  });

  it("does not flag modest renewable share or not-low-enough carbon", () => {
    expect(isCleanSurplus(60, 200, 50)).toBe(false);
    expect(isCleanSurplus(90, 150, 20)).toBe(false);
  });
});
