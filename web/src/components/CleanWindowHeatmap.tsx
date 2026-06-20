import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { FORECAST_WEEK_URL, snapshotEnabled, useSnapshot, useWeekForecast } from "../api/snapshot";
import { intensityColor } from "../lib/intensity";
import { DEFAULT_REGION } from "../lib/providers";
import { card, muted } from "../styles";
import { InfoTip } from "./InfoTip";
import { ProviderRegionPicker } from "./ProviderRegionPicker";

// Grid of the next ~7 days x 24 hours, each cell coloured by projected carbon
// intensity, so the cleanest hours to run a job jump out at a glance.
function Heatmap({ provider, region }: { provider: string; region: string }) {
  // Read the 7-day curve from the lazy-loaded CDN file when available (no API call);
  // otherwise fetch it live. Only this component pays for the week file.
  const week = useWeekForecast(provider, region);
  const {
    data: apiData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["forecast-heatmap", provider, region],
    queryFn: () => api.carbonForecast(provider, region, 168),
    staleTime: 10 * 60_000,
    retry: 1,
    enabled: !FORECAST_WEEK_URL, // CDN week-forecast available -> skip the API
  });

  // Hovered (desktop) / tapped (mobile) cell tooltip with the underlying value.
  // Declared before the early returns below to respect the rules of hooks.
  const [tip, setTip] = useState<{
    key: string;
    x: number;
    y: number;
    label: string;
    hour: number;
    v: number | null;
  } | null>(null);

  // On touch, a tap opens the tooltip; close it again when the next pointer-down
  // lands anywhere outside a heatmap cell.
  useEffect(() => {
    if (!tip) return;
    const onDown = (e: PointerEvent) => {
      if (!(e.target as HTMLElement).closest("[data-heatcell]")) setTip(null);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [tip]);

  // Normalize either source to {ts, c}: the CDN file's compact {t, c} or the API points.
  const points = week
    ? week.points.map((p) => ({ ts: p.t, c: p.c }))
    : (apiData?.points ?? []).map((p) => ({
        ts: p.timestamp,
        c: p.carbon_intensity_gco2_kwh,
      }));
  const fcMethod = week?.method ?? apiData?.method;

  if (FORECAST_WEEK_URL ? !week : isLoading) return <p style={muted}>Loading forecast…</p>;
  if ((!FORECAST_WEEK_URL && isError) || points.length < 2)
    return <p style={muted}>No forecast available for this region.</p>;

  // Bucket points into local-time date -> hour -> intensity.
  const byDate = new Map<string, (number | null)[]>();
  for (const p of points) {
    const d = new Date(p.ts);
    const key = d.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    if (!byDate.has(key)) byDate.set(key, Array(24).fill(null));
    const row = byDate.get(key);
    if (row) row[d.getHours()] = p.c;
  }
  const rows = [...byDate.entries()];
  const method =
    fcMethod === "entsoe_day_ahead"
      ? "ENTSO-E day-ahead for the first ~48h, then a time-of-day model"
      : fcMethod === "open_meteo_forecast"
        ? "an Open-Meteo weather forecast"
        : "a time-of-day model";

  // Hover (desktop) / tap (mobile) shows the cell's value; toggle off on re-tap.
  const showTip = (
    e: React.MouseEvent,
    key: string,
    label: string,
    hour: number,
    v: number | null,
  ) => {
    const r = e.currentTarget.getBoundingClientRect();
    setTip({ key, x: r.left + r.width / 2, y: r.top, label, hour, v });
  };

  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        {/* table-layout: fixed so the labelled 0/6/12/18 columns stay the same
            width as the blank ones -- their two-digit labels overflow (centred)
            into the empty neighbour columns instead of widening their own. */}
        <table
          style={{
            borderCollapse: "collapse",
            fontSize: "0.7rem",
            tableLayout: "fixed",
            width: "max-content",
          }}
        >
          <colgroup>
            <col style={{ width: 90 }} />
            {Array.from({ length: 24 }, (_, h) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed 24-hour columns, index is the hour
              <col key={h} style={{ width: 15 }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th aria-label="day" />
              {Array.from({ length: 24 }, (_, h) => (
                <th
                  // biome-ignore lint/suspicious/noArrayIndexKey: fixed 24-hour columns, index is the hour
                  key={h}
                  style={{
                    color: "var(--gray-400)",
                    fontWeight: 400,
                    padding: 0,
                    overflow: "visible",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h % 6 === 0 ? h : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, hours], di) => (
              <tr key={label}>
                <td style={{ paddingRight: 8, whiteSpace: "nowrap", color: "var(--gray-500)" }}>
                  {label}
                </td>
                {hours.map((v, h) => {
                  const key = `${di}-${h}`;
                  const text =
                    v == null
                      ? `${label} ${h}:00 — no data`
                      : `${label} ${h}:00 — ${Math.round(v)} gCO₂/kWh`;
                  return (
                    // biome-ignore lint/a11y/useKeyWithClickEvents: visual overview grid (168 cells); keyboard/SR users use the "View as a table" alternative and each cell carries an aria-label
                    <td
                      // biome-ignore lint/suspicious/noArrayIndexKey: fixed 24-hour columns, index is the hour
                      key={h}
                      data-heatcell
                      aria-label={text}
                      onMouseEnter={(e) => showTip(e, key, label, h, v)}
                      onMouseLeave={() => setTip((cur) => (cur?.key === key ? null : cur))}
                      onClick={(e) =>
                        tip?.key === key ? setTip(null) : showTip(e, key, label, h, v)
                      }
                      style={{
                        height: 15,
                        background: v == null ? "var(--gray-100)" : intensityColor(v),
                        border: "1px solid var(--surface)",
                        cursor: "pointer",
                        touchAction: "manipulation",
                      }}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tip && (
        <div
          role="tooltip"
          style={{
            position: "fixed",
            left: tip.x,
            top: tip.y - 8,
            transform: "translate(-50%, -100%)",
            background: "var(--gray-900)",
            color: "var(--surface)",
            padding: "5px 9px",
            borderRadius: 6,
            fontSize: "0.72rem",
            lineHeight: 1.35,
            whiteSpace: "nowrap",
            pointerEvents: "none",
            zIndex: 50,
            boxShadow: "0 2px 10px rgba(0,0,0,0.3)",
          }}
        >
          <strong>
            {tip.label} · {String(tip.hour).padStart(2, "0")}:00
          </strong>
          <br />
          {tip.v == null ? "no forecast" : `${Math.round(tip.v)} gCO₂/kWh`}
        </div>
      )}
      <p style={{ ...muted, marginTop: 8 }}>
        Greener = cleaner; each cell is one local-time hour. Projection from {method} — directional
        guidance, not a precise prediction.
      </p>
    </div>
  );
}

export function CleanWindowHeatmap() {
  const [provider, setProvider] = useState("aws");
  const [region, setRegion] = useState(DEFAULT_REGION.aws);

  const { data: snapshot } = useSnapshot();
  const { data: apiRegions } = useQuery({
    queryKey: ["regions", provider],
    queryFn: () => api.regions(provider),
    staleTime: 60 * 60_000,
    enabled: !snapshotEnabled, // region list comes from the snapshot in production
  });
  const regions = snapshot ? snapshot.regions.filter((r) => r.provider === provider) : apiRegions;

  return (
    <div style={{ ...card, marginTop: "1.5rem" }}>
      <h2
        style={{ margin: "0 0 0.25rem", fontSize: "1.1rem", display: "flex", alignItems: "center" }}
      >
        7-day clean-window outlook
        <InfoTip
          label="clean-window outlook"
          text="Projected carbon intensity for each hour over the next week, so you can pick the greenest time to run flexible jobs. EU zones use ENTSO-E's real day-ahead forecast for ~48h; beyond that (and elsewhere) it's a local time-of-day model."
        />
      </h2>
      <ProviderRegionPicker
        provider={provider}
        region={region}
        regions={regions}
        onSelectProvider={(p) => {
          setProvider(p);
          setRegion(DEFAULT_REGION[p]);
        }}
        onSelectRegion={setRegion}
        regionLabel="Region"
        showLocation
      />
      <Heatmap provider={provider} region={region} />
    </div>
  );
}
