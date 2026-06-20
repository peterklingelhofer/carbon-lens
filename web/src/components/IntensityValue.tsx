import { intensityColor } from "../lib/intensity";

// A large carbon-intensity number coloured by the shared scale, with a small
// "gCO₂/kWh" suffix. `size` sets the number's font size (the suffix scales with it).
export function IntensityValue({ value, size = "1.6rem" }: { value: number; size?: string }) {
  return (
    <span style={{ fontSize: size, fontWeight: 700, color: intensityColor(value) }}>
      {value}
      <span style={{ fontSize: "0.7rem", fontWeight: 400, color: "var(--gray-500)" }}>
        {" "}
        gCO₂/kWh
      </span>
    </span>
  );
}
