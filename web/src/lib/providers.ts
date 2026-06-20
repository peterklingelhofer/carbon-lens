import type { CSSProperties } from "react";

// Cloud providers offered in the region pickers, and a sensible default region
// for each, kept here so the heatmap and comparison pickers stay in sync
export const PROVIDERS = ["aws", "gcp", "azure", "scaleway", "ovh", "hetzner"];

// The hyperscaler subset (used where only the big three are offered, e.g. siting)
export const HYPERSCALERS = ["aws", "gcp", "azure"];

export const DEFAULT_REGION: Record<string, string> = {
  aws: "us-east-1",
  gcp: "us-central1",
  azure: "eastus",
  scaleway: "fr-par",
  ovh: "gra",
  hetzner: "fsn1",
};

// The active/inactive style for a provider pill button in a picker row
export function providerButtonStyle(active: boolean): CSSProperties {
  return {
    padding: "0.3rem 0.9rem",
    borderRadius: 6,
    border: "1px solid var(--gray-200)",
    background: active ? "var(--btn-green)" : "var(--surface)",
    color: active ? "white" : "var(--gray-700)",
    cursor: "pointer",
    fontSize: "0.8rem",
  };
}
