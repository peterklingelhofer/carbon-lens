import { th } from "../styles";
import { InfoTip } from "./InfoTip";

// A table header cell with an optional info tooltip, right- or left-aligned.
// Shared by the route-demo and API-explorer result tables.
export function TableHeadCell({
  label,
  tip,
  align = "left",
}: {
  label: string;
  tip?: string;
  align?: "left" | "right";
}) {
  return (
    <th style={{ ...th, textAlign: align }}>
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: align === "right" ? "flex-end" : "flex-start",
        }}
      >
        {label}
        {tip && <InfoTip label={label} text={tip} />}
      </span>
    </th>
  );
}
