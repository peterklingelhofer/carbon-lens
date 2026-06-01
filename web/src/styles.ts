/** Shared style constants used across pages. */

export const section = (maxWidth = 900): React.CSSProperties => ({
  maxWidth,
  margin: "0 auto",
  padding: "2rem 1rem",
});

export const card: React.CSSProperties = {
  background: "var(--card-bg)",
  borderRadius: 12,
  padding: "1.5rem",
  border: "1px solid var(--gray-200)",
  boxShadow: "var(--card-shadow)",
  marginBottom: "1.5rem",
};

const PROV_BG: Record<string, string> = {
  aws: "var(--prov-aws-bg)",
  gcp: "var(--prov-gcp-bg)",
  azure: "var(--prov-azure-bg)",
};

/** A cloud-provider label rendered as a solid brand-colored pill with white text.
 *  Identical in light and dark mode — the chip supplies its own contrast. */
export function providerChip(provider: string): React.CSSProperties {
  return {
    display: "inline-block",
    padding: "1px 7px",
    borderRadius: 5,
    fontWeight: 700,
    color: "#fff",
    background: PROV_BG[provider] ?? "var(--prov-gcp-bg)",
  };
}

export const grid3: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "1.5rem",
};

export const badge: React.CSSProperties = {
  display: "inline-block",
  padding: "0.25rem 0.75rem",
  borderRadius: 20,
  fontSize: "0.8rem",
  fontWeight: 600,
  background: "var(--green-100)",
  color: "var(--green-800)",
};
