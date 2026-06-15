import { describe, expect, it } from "vitest";
import { relativeToUsual } from "./anomaly";

// Build N points all at the same UTC hour with the given intensities.
function pointsAtHour(
  hour: number,
  intensities: number[],
): { timestamp: string; carbon_intensity_gco2_kwh: number }[] {
  return intensities.map((c, i) => ({
    timestamp: `2026-06-${String(10 + i).padStart(2, "0")}T${String(hour).padStart(2, "0")}:00:00Z`,
    carbon_intensity_gco2_kwh: c,
  }));
}

describe("relativeToUsual", () => {
  const now = new Date("2026-06-20T14:00:00Z"); // UTC hour 14

  it("returns null until there's enough history", () => {
    expect(relativeToUsual(100, pointsAtHour(14, [100, 110]), now)).toBeNull();
  });

  it("flags cleaner-than-usual against the same hour-of-day baseline", () => {
    // baseline (same hour) median = 400; current 200 -> 50% cleaner.
    const cmp = relativeToUsual(200, pointsAtHour(14, [380, 400, 420]), now);
    expect(cmp).not.toBeNull();
    expect(cmp?.basis).toBe("hour");
    expect(cmp?.status).toBe("cleaner");
    expect(cmp?.deltaPct).toBe(-50);
  });

  it("flags dirtier-than-usual", () => {
    const cmp = relativeToUsual(300, pointsAtHour(14, [180, 200, 220]), now);
    expect(cmp?.status).toBe("dirtier");
    expect(cmp?.deltaPct).toBe(50);
  });

  it("reads as typical within the deadband", () => {
    const cmp = relativeToUsual(205, pointsAtHour(14, [190, 200, 210]), now);
    expect(cmp?.status).toBe("typical");
  });

  it("falls back to recent points when this hour is thin", () => {
    // Only 1 point at hour 14, but 6 total at other hours -> 'recent' basis.
    const cmp = relativeToUsual(100, pointsAtHour(9, [300, 300, 300, 300, 300, 300]), now);
    expect(cmp?.basis).toBe("recent");
    expect(cmp?.status).toBe("cleaner");
  });
});
