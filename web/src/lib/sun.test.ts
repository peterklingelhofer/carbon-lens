import { describe, expect, it } from "vitest";
import { subsolarPoint } from "./sun";

describe("subsolarPoint", () => {
  it("sits near (0,0) at the March equinox, UTC noon", () => {
    const s = subsolarPoint(new Date("2026-03-20T12:00:00Z"));
    expect(Math.abs(s.lat)).toBeLessThan(3); // declination ~0 at equinox
    expect(Math.abs(s.lng)).toBeLessThan(2); // noon UTC -> over Greenwich
  });

  it("moves ~15°/hour west of Greenwich through the afternoon", () => {
    expect(subsolarPoint(new Date("2026-03-20T18:00:00Z")).lng).toBeCloseTo(-90, 0);
  });

  it("puts the sun over the northern tropics at the June solstice", () => {
    expect(subsolarPoint(new Date("2026-06-21T12:00:00Z")).lat).toBeGreaterThan(20);
  });
});
