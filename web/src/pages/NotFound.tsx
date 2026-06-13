import { Link } from "react-router-dom";

// A wrong URL is a dead end, so point people at the places they most likely
// wanted instead of just an apology.
const SUGGESTIONS: { to: string; label: string; desc: string }[] = [
  { to: "/globe", label: "Live globe", desc: "Grid carbon intensity worldwide" },
  { to: "/dashboard", label: "Grid data", desc: "Every region, sortable and searchable" },
  { to: "/api-explorer", label: "API explorer", desc: "Try the endpoints in the browser" },
  { to: "/methodology", label: "Methodology", desc: "How every number is produced" },
];

export function NotFound() {
  return (
    <div
      style={{
        maxWidth: 560,
        margin: "0 auto",
        padding: "4rem 2rem",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: "4rem", fontWeight: 700, color: "var(--gray-300)" }}>404</div>
      <h1 style={{ margin: "0.5rem 0 1rem", fontSize: "1.5rem" }}>Page not found</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        The page you're looking for doesn't exist or has been moved. Try one of these instead:
      </p>

      <div style={{ display: "grid", gap: "0.75rem", textAlign: "left", marginBottom: "2rem" }}>
        {SUGGESTIONS.map((s) => (
          <Link
            key={s.to}
            to={s.to}
            style={{
              display: "block",
              padding: "0.9rem 1.1rem",
              border: "1px solid var(--gray-300)",
              borderRadius: 8,
              textDecoration: "none",
              color: "inherit",
            }}
          >
            <span style={{ fontWeight: 600, color: "var(--green-text)" }}>{s.label}</span>
            <span style={{ display: "block", fontSize: "0.85rem", color: "var(--gray-500)" }}>
              {s.desc}
            </span>
          </Link>
        ))}
      </div>

      <Link
        to="/"
        style={{
          display: "inline-block",
          padding: "0.75rem 2rem",
          background: "var(--btn-green)",
          color: "white",
          borderRadius: 8,
          textDecoration: "none",
          fontWeight: 600,
        }}
      >
        Back to Home
      </Link>
    </div>
  );
}
