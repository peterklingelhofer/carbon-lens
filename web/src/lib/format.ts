// Small pure formatting helpers shared across pages (kept here so they're
// defined once and unit-testable).

/** Human "x min/hr ago" from an ISO timestamp. */
export function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
}

/** Total grid load (whole balancing authority, all consumers), formatted as MW/GW. */
export function formatLoad(mw?: number | null): string | null {
  if (mw == null) return null;
  return mw >= 1000 ? `${(mw / 1000).toFixed(1)} GW` : `${Math.round(mw)} MW`;
}

/** Extract a readable message from a mutation error of unknown type. */
export function mutationErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

/** Round to a "nice" 1/2/5 × 10ⁿ value - used for the globe's km scale bar. */
export function niceKm(x: number): number {
  if (x <= 0) return 0;
  const exp = Math.floor(Math.log10(x));
  const frac = x / 10 ** exp;
  const nice = frac < 1.5 ? 1 : frac < 3.5 ? 2 : frac < 7.5 ? 5 : 10;
  return nice * 10 ** exp;
}
