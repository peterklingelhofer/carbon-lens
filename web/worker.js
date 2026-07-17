// Cloudflare Worker entry: serves the built SPA from ./dist AND proxies API
// paths to the Render backend, so the browser only ever makes SAME-ORIGIN
// requests. This removes CORS entirely and, crucially, stops privacy extensions
// / Firefox Enhanced Tracking Protection from blocking the (otherwise
// cross-origin, third-party) API calls — those tools block by request domain,
// and now every request is first-party to the page's own origin.

const API_ORIGIN = "https://carbonlens-gssa.onrender.com";

// Same value as web/.env.production's VITE_SNAPSHOT_URL. env.SNAPSHOT_URL (set in
// wrangler.jsonc vars) is the source of truth; this is only a fallback so the
// worker still degrades to snapshot-serving if the binding is ever missing.
const DEFAULT_SNAPSHOT_URL =
  "https://raw.githubusercontent.com/peterklingelhofer/carbon-lens/data/snapshot.json";

// Paths owned by the backend API rather than the static site.
function isApiPath(pathname) {
  return (
    pathname === "/health" ||
    pathname.startsWith("/health/") ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/ws/") ||
    pathname === "/ready" ||
    pathname === "/docs" ||
    pathname === "/redoc" ||
    pathname === "/openapi.json" ||
    pathname === "/metrics"
  );
}

// --- Snapshot read-through -------------------------------------------------
//
// A handful of GET endpoints are fully derivable from the same snapshot.json
// the frontend already reads (see src/api/snapshot.ts), so they're served
// straight from GitHub's CDN instead of waking the sleeping Render origin
// (~46s cold start). Every other API path -- including endpoints below whose
// snapshot representation doesn't losslessly reproduce the live response shape
// (see the route table note) -- proxies exactly as before.
//
// Deliberately NOT intercepted, despite being snapshot-derived in principle:
//   GET /api/v1/regions
//     CloudRegion also has eia_respondent/gridstatus_iso (models/region.py);
//     the snapshot's region entries don't carry them (build_snapshot.py only
//     writes provider/region/grid_zone/location/latitude/longitude). ~25
//     regions have a real eia_respondent value, so a projected response would
//     silently report null for a field that isn't actually null -- a wrong
//     answer, not just an incomplete one. Proxied.
//   GET /api/v1/carbon/forecast/{provider}/{region}
//     CarbonForecast.points is list[CarbonIntensity] (grid_zone, renewable_
//     percentage, source, grid_load_mw, marginal_intensity_gco2_kwh,
//     power_breakdown_mw per point). The snapshot's forecast points are
//     compacted to {t, c} only (snapshot.ts CarbonSnapshotForecast) -- the
//     other per-point fields don't exist anywhere to reconstruct from.
//     Proxied.

let snapshotPromise = null;
let snapshotExpiresAt = 0;
const SNAPSHOT_TTL_MS = 300_000;

// Fetch snapshot.json once and reuse across every intercepted endpoint in this
// request (and across requests in the same isolate, for SNAPSHOT_TTL_MS). The
// `cf.cacheTtl` hint additionally lets Cloudflare's edge cache this subrequest
// across isolates/colos. A failed fetch/parse is never cached -- it's cleared
// immediately so the next request retries rather than being stuck failing.
function getSnapshot(env) {
  const now = Date.now();
  if (snapshotPromise && now < snapshotExpiresAt) return snapshotPromise;
  const url = env?.SNAPSHOT_URL || DEFAULT_SNAPSHOT_URL;
  snapshotExpiresAt = now + SNAPSHOT_TTL_MS;
  snapshotPromise = fetch(url, { cf: { cacheTtl: 300, cacheEverything: true } }).then((res) => {
    if (!res.ok) throw new Error(`snapshot fetch failed: ${res.status}`);
    return res.json();
  });
  snapshotPromise.catch(() => {
    snapshotPromise = null;
    snapshotExpiresAt = 0;
  });
  return snapshotPromise;
}

// Project a snapshot intensity entry down to exactly CarbonIntensity's fields
// (models/carbon.py). The snapshot entry additionally carries `quality`,
// `carried_forward`, and sometimes `consumption_intensity_gco2_kwh` -- none of
// which the live model has, so they'd leak into a response the live API never
// produces if passed through unprojected.
function projectIntensity(entry) {
  if (!entry) return undefined;
  return {
    grid_zone: entry.grid_zone,
    carbon_intensity_gco2_kwh: entry.carbon_intensity_gco2_kwh,
    renewable_percentage: entry.renewable_percentage,
    timestamp: entry.timestamp,
    source: entry.source,
    grid_load_mw: entry.grid_load_mw ?? null,
    marginal_intensity_gco2_kwh: entry.marginal_intensity_gco2_kwh ?? null,
    power_breakdown_mw: entry.power_breakdown_mw ?? null,
  };
}

// Project down to exactly CarbonSignal's fields. The snapshot builder writes
// these from the live model's own model_dump() (build_snapshot.py
// compute_region_data), so this is normally a 1:1 passthrough -- projected
// explicitly anyway so a future snapshot field addition can't leak through.
function projectSignal(entry) {
  if (!entry) return undefined;
  return {
    provider: entry.provider,
    region: entry.region,
    grid_zone: entry.grid_zone,
    intensity_gco2_kwh: entry.intensity_gco2_kwh,
    state: entry.state,
    advice: entry.advice,
    cleaner_window_in_hours: entry.cleaner_window_in_hours ?? null,
    cleaner_window_intensity_gco2_kwh: entry.cleaner_window_intensity_gco2_kwh ?? null,
    marginal_intensity_gco2_kwh: entry.marginal_intensity_gco2_kwh ?? null,
    marginal_note: entry.marginal_note ?? null,
    marginal_basis: entry.marginal_basis ?? "heuristic",
    clean_surplus: entry.clean_surplus ?? false,
    surplus_window_in_hours: entry.surplus_window_in_hours ?? null,
  };
}

// Project down to exactly BestTime's fields (built via the same
// engine.besttime.build_best_time the live endpoint calls, so the values
// themselves already match -- see build_snapshot.py compute_best_times).
function projectBestTime(entry) {
  if (!entry) return undefined;
  return {
    provider: entry.provider,
    region: entry.region,
    grid_zone: entry.grid_zone,
    basis: entry.basis,
    days_analyzed: entry.days_analyzed,
    cleanest_hour_utc: entry.cleanest_hour_utc ?? null,
    dirtiest_hour_utc: entry.dirtiest_hour_utc ?? null,
    shift_savings_pct: entry.shift_savings_pct ?? null,
    annual_kg_saved: entry.annual_kg_saved ?? null,
    suggested_cron: entry.suggested_cron ?? null,
    ranked_hours: entry.ranked_hours ?? [],
  };
}

// WeatherConditions needs grid_zone/provider/region/observed_at that the
// snapshot's compact weather entry doesn't carry per-entry (only
// wind_speed_kmh/solar_irradiance_w_m2/source -- see compute_weather in
// build_snapshot.py). provider/region come from the lookup key itself;
// grid_zone is resolved from the snapshot's own region list (same source of
// truth as the live mapper); observed_at uses the snapshot's generated_at --
// the live value is always "now" at request time regardless, so no cached
// response could ever match it byte-for-byte anyway.
function projectWeather(entry, provider, region, snapshot) {
  if (!entry) return undefined;
  const meta = (snapshot.regions || []).find((r) => r.provider === provider && r.region === region);
  if (!meta) return undefined;
  return {
    grid_zone: meta.grid_zone,
    provider,
    region,
    wind_speed_kmh: entry.wind_speed_kmh,
    solar_irradiance_w_m2: entry.solar_irradiance_w_m2,
    observed_at: snapshot.generated_at,
    source: entry.source ?? "open_meteo",
  };
}

function snapshotJsonResponse(body) {
  return new Response(JSON.stringify(body), {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=300",
      "X-Carbon-Lens-Source": "snapshot",
    },
  });
}

// Route table: path shape -> { kind, provider, region } | { kind, zone }. Two
// carbon/{provider}/{region}-shaped 3-segment paths exist (the zone-first
// sibling and the region one), same ambiguity routes.py resolves by literal
// "zone" segment match, so it's checked first here too. Anything not matched
// (including /regions and /carbon/forecast/... -- see the note above) returns
// null and falls straight through to the origin proxy.
function matchSnapshotRoute(pathname) {
  const segments = pathname.split("/").filter(Boolean).slice(2); // drop "api","v1"
  if (segments[0] !== "carbon") return null;

  if (segments.length === 3 && segments[1] === "zone") {
    return { kind: "zone-intensity", zone: decodeURIComponent(segments[2]) };
  }
  if (segments.length === 3) {
    return {
      kind: "intensity",
      provider: decodeURIComponent(segments[1]),
      region: decodeURIComponent(segments[2]),
    };
  }
  if (segments.length === 4) {
    const [, sub, provider, region] = segments;
    if (sub !== "signal" && sub !== "best-time" && sub !== "weather") return null;
    return {
      kind: sub,
      provider: decodeURIComponent(provider),
      region: decodeURIComponent(region),
    };
  }
  return null;
}

// Any query param that would change the live response gates the whole
// endpoint back to the origin -- the snapshot only has the default-params
// answer precomputed. best-time's `days`/`energy_kwh` are the only such
// params among the intercepted endpoints (routes.py); the rest take none.
function hasResponseAffectingQuery(route, url) {
  if (route.kind !== "best-time") return false;
  const days = url.searchParams.get("days");
  return (days !== null && days !== "14") || url.searchParams.has("energy_kwh");
}

async function serveFromSnapshot(route, url, env) {
  if (hasResponseAffectingQuery(route, url)) return null;

  const snapshot = await getSnapshot(env);

  switch (route.kind) {
    case "zone-intensity": {
      const entry = Object.values(snapshot.intensities || {}).find(
        (i) => i.grid_zone === route.zone,
      );
      const projected = projectIntensity(entry);
      return projected ? snapshotJsonResponse(projected) : null;
    }
    case "intensity": {
      const entry = snapshot.intensities?.[`${route.provider}/${route.region}`];
      const projected = projectIntensity(entry);
      return projected ? snapshotJsonResponse(projected) : null;
    }
    case "signal": {
      const entry = snapshot.signals?.[`${route.provider}/${route.region}`];
      const projected = projectSignal(entry);
      return projected ? snapshotJsonResponse(projected) : null;
    }
    case "best-time": {
      const entry = snapshot.best_time?.[`${route.provider}/${route.region}`];
      const projected = projectBestTime(entry);
      return projected ? snapshotJsonResponse(projected) : null;
    }
    case "weather": {
      const entry = snapshot.weather?.[`${route.provider}/${route.region}`];
      const projected = projectWeather(entry, route.provider, route.region, snapshot);
      return projected ? snapshotJsonResponse(projected) : null;
    }
    default:
      return null;
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (isApiPath(url.pathname)) {
      if (request.method === "GET") {
        const route = matchSnapshotRoute(url.pathname);
        if (route) {
          // Any failure here (snapshot unreachable, malformed JSON, unexpected
          // shape) falls through to the origin proxy below rather than surfacing
          // a broken CDN response.
          const served = await serveFromSnapshot(route, url, env).catch(() => null);
          if (served) return served;
        }
      }

      // Forward method, headers, and body unchanged to the backend. fetch() uses
      // the target URL's host for the connection, so this lands on Render.
      const target = API_ORIGIN + url.pathname + url.search;
      return fetch(new Request(target, request));
    }

    // Everything else: the static SPA. env.ASSETS applies the configured
    // single-page-application fallback (client routes -> index.html).
    return env.ASSETS.fetch(request);
  },
};
