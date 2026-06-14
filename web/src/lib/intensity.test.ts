import { describe, expect, it } from "vitest";
import { intensityColor, intensityRGB, renewableRGB } from "./intensity";

describe("intensityRGB", () => {
  it("maps intensity to a green->red scale by threshold (boundaries inclusive)", () => {
    expect(intensityRGB(0)).toEqual([34, 197, 94]); // green, very clean
    expect(intensityRGB(50)).toEqual([34, 197, 94]); // upper edge of green
    expect(intensityRGB(150)).toEqual([132, 204, 22]); // lime
    expect(intensityRGB(300)).toEqual([234, 179, 8]); // amber
    expect(intensityRGB(500)).toEqual([249, 115, 22]); // orange
    expect(intensityRGB(900)).toEqual([239, 68, 68]); // red, dirty
  });
});

describe("intensityColor", () => {
  it("formats the rgb scale as a CSS string", () => {
    expect(intensityColor(0)).toBe("rgb(34,197,94)");
    expect(intensityColor(900)).toBe("rgb(239,68,68)");
  });
});

describe("renewableRGB", () => {
  it("runs the opposite way: high renewable % is green, low is red", () => {
    expect(renewableRGB(90)).toEqual([34, 197, 94]);
    expect(renewableRGB(50)).toEqual([234, 179, 8]);
    expect(renewableRGB(10)).toEqual([239, 68, 68]);
  });
});
