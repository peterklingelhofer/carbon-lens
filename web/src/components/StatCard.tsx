import type { ReactNode } from "react";
import { InfoTip } from "./InfoTip";

// A bordered metric tile: small label (with optional info tooltip) over a large
// value with an optional unit suffix. `positive` greens the value, `mono` shrinks
// it to a monospace identifier. Shared across the scheduler, SLA, compliance,
// settings and API-explorer result cards.
export function StatCard({
  label,
  value,
  unit,
  positive,
  mono,
  tip,
}: {
  label: string;
  value: string | number;
  unit?: string;
  positive?: boolean;
  mono?: boolean;
  tip?: ReactNode;
}) {
  return (
    <div
      style={{
        padding: "0.75rem",
        borderRadius: 8,
        border: "1px solid var(--gray-200)",
        background: "var(--surface-alt)",
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          color: "var(--gray-500)",
          display: "inline-flex",
          alignItems: "center",
        }}
      >
        {label}
        {tip && (
          <InfoTip label={typeof label === "string" ? label.toLowerCase() : "info"} text={tip} />
        )}
      </div>
      <div
        style={{
          fontSize: mono ? "0.85rem" : "1.3rem",
          fontWeight: 700,
          color: positive ? "var(--green-700)" : "inherit",
          fontFamily: mono ? "var(--mono)" : "inherit",
        }}
      >
        {value}
        {unit && (
          <span style={{ fontSize: "0.75rem", fontWeight: 400, marginLeft: 4 }}>{unit}</span>
        )}
      </div>
    </div>
  );
}
