import { describe, expect, it } from "vitest";
import { subsolarPoint, terminatorPath } from "./sun";

const D2R = Math.PI / 180;

// Great-circle angular distance (deg) between the subsolar point and a [lat,lng].
function angularDistanceDeg(a: { lat: number; lng: number }, b: [number, number]): number {
  const c =
    Math.sin(a.lat * D2R) * Math.sin(b[0] * D2R) +
    Math.cos(a.lat * D2R) * Math.cos(b[0] * D2R) * Math.cos((a.lng - b[1]) * D2R);
  return Math.acos(Math.max(-1, Math.min(1, c))) / D2R;
}

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

describe("terminatorPath", () => {
  it("is a closed great circle exactly 90° from the subsolar point", () => {
    const d = new Date("2026-06-21T09:00:00Z");
    const s = subsolarPoint(d);
    const path = terminatorPath(d);
    expect(path.length).toBe(121);
    for (const p of path) {
      expect(angularDistanceDeg(s, p)).toBeCloseTo(90, 0);
    }
  });
});
