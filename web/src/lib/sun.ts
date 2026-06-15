// Where the sun is, from the clock alone -- pure astronomy, no API.
//
// Used to draw the day/night terminator and the subsolar point (where the sun is
// directly overhead) on the globe. Approximations good to ~1° (we ignore the
// equation of time, ~±4° of longitude) -- plenty for a visual that explains why
// solar-heavy zones clean up around local midday.

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

function normalizeLng(lng: number): number {
  return ((lng + 540) % 360) - 180;
}

// The point on Earth where the sun is directly overhead right now.
export function subsolarPoint(date: Date): { lat: number; lng: number } {
  const yearStart = Date.UTC(date.getUTCFullYear(), 0, 0);
  const today = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  const dayOfYear = (today - yearStart) / 86_400_000;

  // Solar declination (deg): the subsolar latitude, swinging ±23.44° over the year.
  const lat = -23.44 * Math.cos(((2 * Math.PI) / 365) * (dayOfYear + 10));

  // Subsolar longitude: 0° at UTC noon, moving 15°/h westward.
  const hours = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
  const lng = normalizeLng(-15 * (hours - 12));

  return { lat, lng };
}

// Destination point a great-circle distance `dist` (radians) along bearing `brng`
// (radians) from (latR, lonR) in radians. Returns [lat, lng] in degrees.
function destination(latR: number, lonR: number, brng: number, dist: number): [number, number] {
  const lat = Math.asin(
    Math.sin(latR) * Math.cos(dist) + Math.cos(latR) * Math.sin(dist) * Math.cos(brng),
  );
  const lon =
    lonR +
    Math.atan2(
      Math.sin(brng) * Math.sin(dist) * Math.cos(latR),
      Math.cos(dist) - Math.sin(latR) * Math.sin(lat),
    );
  return [lat * R2D, normalizeLng(lon * R2D)];
}

// A great circle of points `radiusDeg` from `center` (used for both the
// terminator at 90° and the small marker ring around the subsolar point).
export function circleAround(
  center: { lat: number; lng: number },
  radiusDeg: number,
  steps = 96,
): [number, number][] {
  const latR = center.lat * D2R;
  const lonR = center.lng * D2R;
  const dist = radiusDeg * D2R;
  const points: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    points.push(destination(latR, lonR, (i / steps) * 2 * Math.PI, dist));
  }
  return points;
}

// The day/night terminator: the great circle 90° from the subsolar point.
export function terminatorPath(date: Date, steps = 120): [number, number][] {
  return circleAround(subsolarPoint(date), 90, steps);
}
