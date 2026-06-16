// Where the sun is, from the clock alone -- pure astronomy, no API.
//
// Gives the subsolar point (where the sun is directly overhead) so the globe can
// shade daylight by cos(solar zenith). Approximations good to ~1° (we ignore the
// equation of time, ~±4° of longitude) -- plenty for a soft visual.

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
