import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useForecastSnapshot, useSignal } from "../api/snapshot";
import { relativeToUsual } from "../lib/anomaly";
import { MiniSparkline, trendLabel } from "./MiniSparkline";

const SIGNAL_COLOR = { green: "#4ade80", yellow: "#fbbf24", red: "#f87171" } as const;

// The run-now/wait decision for a region, read straight from the precomputed snapshot
// signal on the CDN -- no API call, so it's instant even when the server is asleep.
// Renders nothing when there's no signal (snapshot disabled, or region not covered).
export function RegionSignal({ provider, region }: { provider: string; region: string }) {
  const signal = useSignal(provider, region);
  if (!signal) return null;
  const color = SIGNAL_COLOR[signal.state];
  const runNow = signal.advice === "run_now";
  const window = signal.surplus_window_in_hours ?? signal.cleaner_window_in_hours;

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginBottom: 4 }}>
        Run a flexible job now?
      </div>
      <div style={{ fontSize: "0.85rem", fontWeight: 600, color }}>
        {signal.clean_surplus ? "⚡ " : ""}
        {runNow ? "Yes — run now" : `Wait${window != null ? ` ~${window}h` : ""} for cleaner`}
        {!runNow && signal.cleaner_window_intensity_gco2_kwh != null && (
          <span style={{ color: "#86efac", fontWeight: 400 }}>
            {" "}
            · then ~{Math.round(signal.cleaner_window_intensity_gco2_kwh)} gCO₂/kWh
          </span>
        )}
      </div>
      {signal.marginal_note && (
        <div style={{ fontSize: "0.62rem", color: "#9ca3af", marginTop: 3 }}>
          {signal.marginal_note}
        </div>
      )}
      <div style={{ fontSize: "0.58rem", color: "#6b7280", marginTop: 2 }}>
        precomputed signal · marginal {signal.marginal_basis}
      </div>
    </div>
  );
}

// "Cleaner / dirtier than usual" badge from the history baseline, when available.
function UsualBadge({
  current,
  points,
}: {
  current: number;
  points: { timestamp: string; carbon_intensity_gco2_kwh: number }[];
}) {
  const cmp = relativeToUsual(current, points, new Date());
  if (!cmp) return null;
  const forHour = cmp.basis === "hour" ? " for this hour" : "";
  if (cmp.status === "typical") {
    return (
      <div style={{ fontSize: "0.65rem", color: "#9ca3af", marginTop: 2 }}>
        About typical{forHour}.
      </div>
    );
  }
  const cleaner = cmp.status === "cleaner";
  return (
    <div style={{ fontSize: "0.68rem", marginTop: 2, color: cleaner ? "#4ade80" : "#fbbf24" }}>
      {cleaner ? "🟢" : "🟡"} ~{Math.abs(cmp.deltaPct)}% {cleaner ? "cleaner" : "dirtier"} than
      usual
      {forHour}.
    </div>
  );
}

// Past-7-days carbon intensity for the selected region, from /carbon/history.
// The archive accumulates over time, so a region shows nothing until it has been
// observed -- handled with an honest "still accumulating" note rather than a gap.
export function RegionHistory({
  provider,
  region,
  current,
}: {
  provider: string;
  region: string;
  current?: number;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["history", provider, region],
    queryFn: () => api.carbonHistory(provider, region, 168),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  const label = (
    <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginBottom: 4 }}>Past 7 days</div>
  );
  if (isLoading) return null;
  if (!data || data.points.length < 2) {
    return (
      <div style={{ marginTop: 10 }}>
        {label}
        <div style={{ fontSize: "0.65rem", color: "#6b7280" }}>History is still accumulating.</div>
      </div>
    );
  }

  const vals = data.points.map((p) => p.carbon_intensity_gco2_kwh);
  const labels = data.points.map((p) =>
    new Date(p.timestamp).toLocaleString(undefined, { weekday: "short", hour: "numeric" }),
  );
  return (
    <div style={{ marginTop: 10 }}>
      {label}
      <MiniSparkline
        values={vals}
        labels={labels}
        mark="last"
        ariaLabel={`Carbon intensity over the past 7 days, trending ${trendLabel(vals[0], vals[vals.length - 1])}`}
      />
      <div style={{ fontSize: "0.65rem", color: "#6b7280", marginTop: 2 }}>
        {data.points.length} readings · hover to inspect
      </div>
      {current != null && <UsualBadge current={current} points={data.points} />}
    </div>
  );
}

// Wind speed + solar irradiance at the region's coordinates, from /carbon/weather
// (Open-Meteo). These are the physical drivers behind a grid's renewable output,
// so they explain *why* the intensity is what it is. A single-point proxy, fetched
// only when a region is opened (so it's free and on-demand, not a globe-wide layer).
export function RegionWeather({ provider, region }: { provider: string; region: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["weather", provider, region],
    queryFn: () => api.regionWeather(provider, region),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  // Stay quiet on load/error: weather is a nice-to-have driver, not core data.
  if (isLoading || isError || !data) return null;

  const wind = Math.round(data.wind_speed_kmh);
  const solar = Math.round(data.solar_irradiance_w_m2);
  // Wind turbines cut in around 12 km/h; solar is meaningful above ~250 W/m2.
  const windOn = wind >= 18;
  const sunOn = solar >= 250;
  const read =
    windOn && sunOn
      ? "Brisk wind and strong sun: renewables likely producing well right now."
      : windOn
        ? "Brisk wind, little sun: wind is the renewable likely carrying the grid."
        : sunOn
          ? "Strong sun, light wind: solar is the renewable likely carrying the grid."
          : "Calm and dim: little wind or sun, so the grid likely leans on baseload.";

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginBottom: 4 }}>Weather now</div>
      <div style={{ display: "flex", gap: 14, fontSize: "0.8rem" }}>
        <span title="Surface wind speed at 10 m (drives wind generation)">
          💨 {wind} <span style={{ color: "#9ca3af", fontSize: "0.7rem" }}>km/h wind</span>
        </span>
        <span title="Shortwave solar irradiance at the surface (drives solar generation)">
          ☀️ {solar} <span style={{ color: "#9ca3af", fontSize: "0.7rem" }}>W/m² sun</span>
        </span>
      </div>
      <div style={{ fontSize: "0.65rem", color: "#9ca3af", marginTop: 3 }}>{read}</div>
      <div style={{ fontSize: "0.58rem", color: "#6b7280", marginTop: 2 }}>
        Single-point estimate · Open-Meteo
      </div>
    </div>
  );
}

// The greenest hour-of-day to schedule a recurring job here -- a one-time cron
// change with permanent savings. From /carbon/best-time (history, or the forecast
// curve as a fallback). Hidden when there's no usable signal yet.
export function RegionBestTime({ provider, region }: { provider: string; region: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["best-time", provider, region],
    queryFn: () => api.bestTime(provider, region),
    staleTime: 30 * 60_000,
    retry: 1,
  });

  if (isLoading || isError || !data || data.cleanest_hour_utc == null) return null;
  const hh = String(data.cleanest_hour_utc).padStart(2, "0");
  const savings = data.shift_savings_pct;

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginBottom: 4 }}>
        Greenest hour to schedule
      </div>
      <div style={{ fontSize: "0.8rem", color: "#4ade80", fontWeight: 600 }}>
        {hh}:00 UTC
        {savings != null && savings > 0 && (
          <span style={{ color: "#86efac", fontWeight: 400 }}>
            {" "}
            · ~{Math.round(savings)}% cleaner
          </span>
        )}
      </div>
      {data.suggested_cron && (
        <code
          style={{
            display: "inline-block",
            marginTop: 3,
            fontSize: "0.66rem",
            color: "#cbd5e1",
            background: "rgba(255,255,255,0.06)",
            padding: "1px 6px",
            borderRadius: 4,
          }}
        >
          {data.suggested_cron}
        </code>
      )}
      <div style={{ fontSize: "0.58rem", color: "#6b7280", marginTop: 2 }}>
        {data.basis === "history"
          ? `from ${data.days_analyzed}-day history · for recurring jobs`
          : "from forecast (history still accumulating)"}
      </div>
    </div>
  );
}

// Next-24h carbon-intensity forecast for the selected region, drawn as a sparkline.
// Read from the precomputed snapshot curve when available (no API call); otherwise
// fetched live from /carbon/forecast. EU zones get a real ENTSO-E day-ahead curve;
// elsewhere it's the labelled time-of-day model.
export function RegionForecast({ provider, region }: { provider: string; region: string }) {
  const snap = useForecastSnapshot(provider, region);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["forecast", provider, region],
    queryFn: () => api.carbonForecast(provider, region, 24),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: !snap, // snapshot already has the curve -> skip the API
  });

  const label = (
    <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginBottom: 4 }}>Next 24h</div>
  );

  // Normalize either source to {ts, c}; the snapshot's compact {t, c} or the API's
  // CarbonIntensity points.
  const points = snap
    ? snap.points.map((p) => ({ ts: p.t, c: p.c }))
    : (data?.points ?? []).map((p) => ({ ts: p.timestamp, c: p.carbon_intensity_gco2_kwh }));
  const method = snap?.method ?? data?.method;
  const surplusHours = snap?.clean_surplus_hours ?? data?.clean_surplus_hours;

  if (!snap && isLoading) {
    return (
      <div style={{ marginTop: 10 }}>
        {label}
        <div style={{ fontSize: "0.7rem", color: "#6b7280" }}>Loading forecast…</div>
      </div>
    );
  }
  if ((!snap && isError) || points.length < 2) return null;

  const vals = points.map((p) => p.c);
  const labels = points.map((p) =>
    new Date(p.ts).toLocaleTimeString(undefined, { hour: "numeric" }),
  );
  const trend = trendLabel(vals[0], vals[vals.length - 1]);
  const methodLabel =
    method === "entsoe_day_ahead"
      ? "ENTSO-E day-ahead"
      : method === "open_meteo_forecast"
        ? "weather forecast (Open-Meteo)"
        : "time-of-day model";

  // Illustrative uncertainty that widens with the horizon, narrowest for the real
  // day-ahead forecast and widest for the bare time-of-day model. Not a measured
  // error band.
  const [base, perHour] =
    method === "entsoe_day_ahead"
      ? [0.04, 0.004]
      : method === "open_meteo_forecast"
        ? [0.06, 0.007]
        : [0.08, 0.01];
  const band = vals.map((v, i): [number, number] => {
    const u = Math.min(0.4, base + perHour * i);
    return [v * (1 - u), v * (1 + u)];
  });

  return (
    <div style={{ marginTop: 10 }}>
      {label}
      <MiniSparkline
        values={vals}
        labels={labels}
        band={band}
        mark="first"
        ariaLabel={`24-hour carbon intensity forecast, trending ${trend}`}
      />
      <div style={{ fontSize: "0.65rem", color: "#6b7280", marginTop: 2 }}>
        {trend} · {methodLabel} · shaded = rough uncertainty
      </div>
      {(() => {
        // Soonest upcoming clean-surplus hour (renewables abundant): the
        // highest-value window to shift a flexible job into.
        const soonest = surplusHours?.find((h) => h >= 1);
        return soonest != null ? (
          <div style={{ fontSize: "0.66rem", color: "#4ade80", marginTop: 3 }}>
            ⚡ Clean-surplus window in ~{soonest}h · highest-value time to run
          </div>
        ) : null;
      })()}
    </div>
  );
}
