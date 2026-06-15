// "Is the grid cleaner or dirtier than usual right now?" — relative context from
// the accumulated history, which is more motivating than a bare absolute number.
//
// Pure and side-effect-free so it's unit-testable; the globe feeds it the history
// it already fetched, so there's no extra request.

export type UsualComparison = {
  status: "cleaner" | "typical" | "dirtier";
  deltaPct: number; // signed: negative = cleaner than usual
  basis: "hour" | "recent"; // compared against same-hour-of-day, or all recent points
  sampleSize: number;
};

type Point = { timestamp: string; carbon_intensity_gco2_kwh: number };

const MIN_HOUR_SAMPLES = 3;
const MIN_RECENT_SAMPLES = 6;
const DEADBAND_PCT = 10; // within ±10% reads as "typical"

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// Compare `current` intensity to the historical baseline. Prefers the same
// hour-of-day (UTC) when there's enough of it (diurnal patterns dominate grid
// carbon); otherwise falls back to all recent points. Returns null when there
// isn't enough history yet to say anything honest.
export function relativeToUsual(
  current: number,
  points: Point[],
  now: Date,
): UsualComparison | null {
  const hour = now.getUTCHours();
  const sameHour = points
    .filter((p) => new Date(p.timestamp).getUTCHours() === hour)
    .map((p) => p.carbon_intensity_gco2_kwh);

  let sample: number[];
  let basis: "hour" | "recent";
  if (sameHour.length >= MIN_HOUR_SAMPLES) {
    sample = sameHour;
    basis = "hour";
  } else if (points.length >= MIN_RECENT_SAMPLES) {
    sample = points.map((p) => p.carbon_intensity_gco2_kwh);
    basis = "recent";
  } else {
    return null; // baseline still building
  }

  const baseline = median(sample);
  if (baseline <= 0) return null;

  const deltaPct = Math.round(((current - baseline) / baseline) * 100);
  const status =
    deltaPct <= -DEADBAND_PCT ? "cleaner" : deltaPct >= DEADBAND_PCT ? "dirtier" : "typical";
  return { status, deltaPct, basis, sampleSize: sample.length };
}
