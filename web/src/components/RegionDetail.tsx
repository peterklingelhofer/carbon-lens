import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { MiniSparkline, trendLabel } from "./MiniSparkline";

// Past-7-days carbon intensity for the selected region, from /carbon/history.
// The archive accumulates over time, so a region shows nothing until it has been
// observed -- handled with an honest "still accumulating" note rather than a gap.
export function RegionHistory({ provider, region }: { provider: string; region: string }) {
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
    </div>
  );
}

// Next-24h carbon-intensity forecast for the selected region, fetched live from
// the API's /carbon/forecast endpoint and drawn as a sparkline. EU zones get a
// real ENTSO-E day-ahead curve; elsewhere it's the labelled time-of-day model.
export function RegionForecast({ provider, region }: { provider: string; region: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["forecast", provider, region],
    queryFn: () => api.carbonForecast(provider, region, 24),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const label = (
    <div style={{ fontSize: "0.72rem", color: "#9ca3af", marginBottom: 4 }}>Next 24h</div>
  );

  if (isLoading) {
    return (
      <div style={{ marginTop: 10 }}>
        {label}
        <div style={{ fontSize: "0.7rem", color: "#6b7280" }}>Loading forecast…</div>
      </div>
    );
  }
  if (isError || !data || data.points.length < 2) return null;

  const vals = data.points.map((p) => p.carbon_intensity_gco2_kwh);
  const labels = data.points.map((p) =>
    new Date(p.timestamp).toLocaleTimeString(undefined, { hour: "numeric" }),
  );
  const trend = trendLabel(vals[0], vals[vals.length - 1]);
  const methodLabel =
    data.method === "entsoe_day_ahead"
      ? "ENTSO-E day-ahead"
      : data.method === "open_meteo_forecast"
        ? "weather forecast (Open-Meteo)"
        : "time-of-day model";

  // Illustrative uncertainty that widens with the horizon, narrowest for the real
  // day-ahead forecast and widest for the bare time-of-day model. Not a measured
  // error band.
  const [base, perHour] =
    data.method === "entsoe_day_ahead"
      ? [0.04, 0.004]
      : data.method === "open_meteo_forecast"
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
    </div>
  );
}
