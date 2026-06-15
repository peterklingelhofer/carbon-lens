import { type PointerEvent, useState } from "react";
import { intensityColor } from "../lib/intensity";

// A compact carbon-intensity sparkline (coloured by the latest value), shared by
// the history and forecast panels. `mark` dots the current reading: the last
// point for history (most recent), the first for a forecast (now).
//
// Hover (or press/drag on touch) to inspect any point: a guide line + dot snap to
// the nearest sample and the readout below shows its time and value. Min/max are
// labelled on the y-axis and the first/last `labels` on the x-axis.
export function MiniSparkline({
  values,
  labels,
  band,
  mark,
  ariaLabel,
  unit = "gCO₂/kWh",
}: {
  values: number[];
  labels?: string[];
  // Optional per-point [low, high] envelope drawn as a shaded area behind the line.
  band?: [number, number][];
  mark?: "first" | "last";
  ariaLabel: string;
  unit?: string;
}) {
  const [active, setActive] = useState<number | null>(null);

  // Tick labels / readout use the value range; the plot domain also includes the
  // band so a wide envelope doesn't clip.
  const min = Math.min(...values);
  const max = Math.max(...values);
  const domainMin = band ? Math.min(min, ...band.map((b) => b[0])) : min;
  const domainMax = band ? Math.max(max, ...band.map((b) => b[1])) : max;
  const span = domainMax - domainMin || 1;
  const w = 224;
  const h = 52;
  const padL = 30; // room for y-axis tick labels
  const padR = 4;
  const padT = 6;
  const padB = 4;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const n = values.length - 1;

  const x = (i: number) => padL + (n === 0 ? 0 : (i / n) * plotW);
  const y = (v: number) => padT + plotH - ((v - domainMin) / span) * plotH;
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const lineColor = intensityColor(values[values.length - 1]);
  const markIdx = mark === "first" ? 0 : values.length - 1;

  // Band polygon: high edge left→right, then low edge right→left, closed.
  const bandPath = band
    ? `M ${[
        ...band.map(([, hi], i) => `${x(i).toFixed(1)},${y(hi).toFixed(1)}`),
        ...band.map(([lo], i) => `${x(i).toFixed(1)},${y(lo).toFixed(1)}`).reverse(),
      ].join(" L ")} Z`
    : null;

  const locate = (e: PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const vbX = ((e.clientX - rect.left) / rect.width) * w;
    const i = Math.round(((vbX - padL) / plotW) * n);
    setActive(Math.max(0, Math.min(n, i)));
  };

  const labelFor = (i: number) => labels?.[i] ?? `+${i}h`;
  const tick = { fontSize: "7px", fill: "var(--gray-400)" } as const;

  return (
    <div>
      <svg
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={ariaLabel}
        style={{ display: "block", touchAction: "none", cursor: "crosshair" }}
        onPointerMove={locate}
        onPointerDown={locate}
        onPointerLeave={() => setActive(null)}
      >
        {/* y-axis min/max ticks */}
        <text x={0} y={padT + 3} style={tick}>
          {Math.round(max)}
        </text>
        <text x={0} y={padT + plotH} style={tick}>
          {Math.round(min)}
        </text>
        {bandPath && <path d={bandPath} fill={lineColor} fillOpacity={0.15} stroke="none" />}
        <polyline
          points={points}
          fill="none"
          stroke={lineColor}
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {mark && active === null && (
          <circle cx={x(markIdx)} cy={y(values[markIdx])} r={2.2} fill="#fff" />
        )}
        {active !== null && (
          <>
            <line
              x1={x(active)}
              y1={padT}
              x2={x(active)}
              y2={padT + plotH}
              stroke="var(--gray-400)"
              strokeWidth={0.75}
              strokeDasharray="2 2"
            />
            <circle
              cx={x(active)}
              cy={y(values[active])}
              r={3}
              fill="#fff"
              stroke={intensityColor(values[active])}
              strokeWidth={1.5}
            />
          </>
        )}
      </svg>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.6rem",
          color: "var(--gray-400)",
          paddingLeft: padL,
        }}
      >
        <span>{labelFor(0)}</span>
        <span>{labelFor(n)}</span>
      </div>
      <div style={{ fontSize: "0.65rem", color: "#cbd5e1", minHeight: "1.1em", marginTop: 2 }}>
        {active !== null
          ? `${labelFor(active)}: ${Math.round(values[active])} ${unit}`
          : `range ${Math.round(min)}–${Math.round(max)} ${unit}`}
      </div>
    </div>
  );
}

// Direction of a series start -> end, with a 5% deadband so small wiggles read
// as "steady" rather than flapping between cleaner/dirtier.
export function trendLabel(first: number, last: number): string {
  const pct = first > 0 ? Math.round(((last - first) / first) * 100) : 0;
  if (pct <= -5) return `cleaner (${pct}%)`;
  if (pct >= 5) return `dirtier (+${pct}%)`;
  return "steady";
}
