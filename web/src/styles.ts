/** Shared style constants used across pages. */

export const section = (maxWidth = 900): React.CSSProperties => ({
  maxWidth,
  margin: "0 auto",
  padding: "2rem",
});

export const card: React.CSSProperties = {
  background: "var(--card-bg)",
  borderRadius: 12,
  padding: "1.5rem",
  border: "1px solid var(--gray-200)",
  marginBottom: "1.5rem",
};

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
