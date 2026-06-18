// Read the carbon-aware headers a service sets via CarbonAwareShedder
// (carbon_mesh.middleware) and degrade the browser experience when the grid is dirty
// -- e.g. skip prefetch, lower image/video quality, defer analytics beacons. Pure and
// framework-agnostic so any app can drop it in.

export type CarbonMode = "full" | "reduced";

export interface CarbonHeaders {
  mode: CarbonMode;
  intensityGco2Kwh: number | null;
}

// Parse `X-Carbon-Mode` / `X-Carbon-Intensity` from a fetch Response's headers.
// Defaults to "full" when the header is absent (no carbon-aware server -> no change).
export function readCarbonHeaders(headers: Headers): CarbonHeaders {
  const mode: CarbonMode = headers.get("X-Carbon-Mode") === "reduced" ? "reduced" : "full";
  const raw = headers.get("X-Carbon-Intensity");
  const n = raw != null && raw !== "" ? Number(raw) : null;
  return { mode, intensityGco2Kwh: n != null && Number.isFinite(n) ? n : null };
}

// Pick one of two options by the carbon mode: full quality vs a leaner one when dirty.
export function chooseByMode<T>(mode: CarbonMode, whenFull: T, whenReduced: T): T {
  return mode === "full" ? whenFull : whenReduced;
}

// fetch() wrapper returning the response plus the parsed carbon mode/intensity, so a
// client can branch on the grid without re-reading headers everywhere.
export async function carbonAwareFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<{ response: Response } & CarbonHeaders> {
  const response = await fetch(input, init);
  return { response, ...readCarbonHeaders(response.headers) };
}
