import { NavLink } from "react-router-dom";

const linkStyle = ({ isActive }: { isActive: boolean }) =>
  ({
    borderRadius: "6px",
    fontWeight: isActive ? 600 : 400,
    // Translucent green tint reads as a highlight on both the light and dark
    // nav; --green-text keeps the label legible in both modes.
    background: isActive ? "rgba(34,197,94,0.10)" : "transparent",
    color: isActive ? "var(--green-text)" : "inherit",
    textDecoration: "none",
    whiteSpace: "nowrap",
  }) as const;

export function Nav() {
  return (
    <>
      <style>{`
        .nav-bar {
          display: flex;
          align-items: center;
          gap: clamp(0.15rem, 1vw, 0.5rem);
          padding: 0.75rem clamp(0.5rem, 3vw, 2rem);
          border-bottom: 1px solid var(--gray-200);
          background: var(--nav-bg);
          position: sticky;
          top: 0;
          z-index: 10;
        }
        .nav-brand {
          font-weight: 700;
          font-size: clamp(0.85rem, 2.5vw, 1.2rem);
          margin-right: clamp(0.25rem, 2vw, 1rem);
          color: var(--green-700);
          text-decoration: none;
          flex-shrink: 0;
        }
        .nav-links {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          row-gap: 0.15rem;
          gap: clamp(0rem, 0.5vw, 0.25rem);
          min-width: 0;
        }
        .nav-links a {
          padding: clamp(0.3rem, 0.8vw, 0.5rem) clamp(0.35rem, 1.2vw, 1rem);
          font-size: clamp(0.72rem, 1.8vw, 0.95rem);
          white-space: nowrap;
        }
        @media (max-width: 640px) {
          .nav-bar { flex-wrap: wrap; }
        }
        @media (prefers-color-scheme: dark) {
          .nav-brand { color: var(--green-400); }
        }
      `}</style>
      <nav className="nav-bar">
        <NavLink to="/" className="nav-brand">
          CarbonLens
        </NavLink>
        <div className="nav-links">
          <NavLink to="/" style={linkStyle} end>
            Home
          </NavLink>
          <NavLink to="/globe" style={linkStyle}>
            Globe
          </NavLink>
          <NavLink to="/api-explorer" style={linkStyle}>
            API Explorer
          </NavLink>
          <NavLink to="/dashboard" style={linkStyle}>
            Grid Data
          </NavLink>
          <NavLink to="/compliance" style={linkStyle}>
            Compliance
          </NavLink>
          <NavLink to="/sla" style={linkStyle}>
            SLA
          </NavLink>
          <NavLink to="/scheduler" style={linkStyle}>
            Scheduler
          </NavLink>
          <NavLink to="/route" style={linkStyle}>
            Route
          </NavLink>
          <NavLink to="/about" style={linkStyle}>
            About
          </NavLink>
          <NavLink to="/settings" style={linkStyle}>
            Status
          </NavLink>
        </div>
      </nav>
    </>
  );
}
