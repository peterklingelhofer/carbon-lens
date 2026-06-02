import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div
      style={{
        maxWidth: 500,
        margin: "0 auto",
        padding: "4rem 2rem",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: "4rem", fontWeight: 700, color: "var(--gray-300)" }}>
        404
      </div>
      <h1 style={{ margin: "0.5rem 0 1rem", fontSize: "1.5rem" }}>Page not found</h1>
      <p style={{ color: "var(--gray-500)", marginBottom: "2rem" }}>
        The page you're looking for doesn't exist or has been moved.
      </p>
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
