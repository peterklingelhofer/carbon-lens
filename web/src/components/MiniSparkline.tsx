import { intensityColor } from "../lib/intensity";

// A compact carbon-intensity sparkline (coloured by the latest value), shared by
// the history and forecast panels. `mark` dots the current reading: the last
// point for history (most recent), the first for a forecast (now).
export function MiniSparkline({
  values,
  mark,
  ariaLabel,
}: {
  values: number[];
  mark?: "first" | "last";
  ariaLabel: string;
}) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 224;
  const h = 44;
  const n = values.length - 1;
  const x = (i: number) => (i / n) * w;
  const y = (v: number) => h - 4 - ((v - min) / span) * (h - 8);
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const markIdx = mark === "first" ? 0 : values.length - 1;
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label={ariaLabel}
      style={{ display: "block" }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={intensityColor(values[values.length - 1])}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {mark && <circle cx={x(markIdx)} cy={y(values[markIdx])} r={2.2} fill="#fff" />}
    </svg>
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
