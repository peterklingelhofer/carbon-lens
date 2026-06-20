// Carbon-intensity colour scale (green = clean -> red = dirty), shared by the
// globe beams and the detail-panel sparklines.
export function intensityRGB(v: number): [number, number, number] {
  if (v <= 50) return [34, 197, 94]; // green
  if (v <= 150) return [132, 204, 22]; // lime
  if (v <= 300) return [234, 179, 8]; // amber
  if (v <= 500) return [249, 115, 22]; // orange
  return [239, 68, 68]; // red
}

export function intensityColor(v: number): string {
  const [r, g, b] = intensityRGB(v);
  return `rgb(${r},${g},${b})`;
}

// Theme-aware variant of the same scale, returning CSS custom properties so the
// colour adapts to light/dark mode (used where the value sits in normal page UI
// rather than on the always-dark globe)
export function intensityVarColor(v: number): string {
  if (v <= 50) return "var(--green-500)";
  if (v <= 150) return "var(--green-400)";
  if (v <= 300) return "var(--amber)";
  if (v <= 500) return "var(--orange-400)";
  return "var(--red-400)";
}

// Human label + theme-aware colour for an intensity, on the canonical thresholds
export function intensityLabel(v: number): { label: string; color: string } {
  if (v <= 50) return { label: "Very Clean", color: "var(--green-text)" };
  if (v <= 150) return { label: "Clean", color: "var(--green-500)" };
  if (v <= 300) return { label: "Moderate", color: "var(--amber)" };
  if (v <= 500) return { label: "Dirty", color: "var(--orange-400)" };
  return { label: "Very Dirty", color: "var(--red-500)" };
}

// Renewable share: high % is greener, so the scale runs the opposite way from
// carbon intensity (high = green, low = red).
export function renewableRGB(pct: number): [number, number, number] {
  if (pct >= 80) return [34, 197, 94]; // green
  if (pct >= 60) return [132, 204, 22]; // lime
  if (pct >= 40) return [234, 179, 8]; // amber
  if (pct >= 20) return [249, 115, 22]; // orange
  return [239, 68, 68]; // red
}
