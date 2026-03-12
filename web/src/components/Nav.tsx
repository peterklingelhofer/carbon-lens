import { NavLink } from "react-router-dom";

const linkStyle = ({ isActive }: { isActive: boolean }) =>
  ({
    padding: "0.5rem 1rem",
    borderRadius: "6px",
    fontWeight: isActive ? 600 : 400,
    background: isActive ? "var(--green-100)" : "transparent",
    color: isActive ? "var(--green-800)" : "inherit",
    textDecoration: "none",
    fontSize: "0.95rem",
  }) as const;

export function Nav() {
  return (
    <>
      <style>{`
        .nav-link-label {
          display: inline;
        }
        @media (max-width: 600px) {
          .nav-bar {
            padding: 0.5rem 1rem !important;
            gap: 0.25rem !important;
          }
          .nav-bar .nav-brand {
            margin-right: 0.5rem !important;
            font-size: 1rem !important;
          }
          .nav-link-label {
            font-size: 0.8rem !important;
          }
        }
      `}</style>
      <nav
        className="nav-bar"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.75rem 2rem",
          borderBottom: "1px solid var(--gray-200)",
          background: "var(--nav-bg)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <span
          className="nav-brand"
          style={{
            fontWeight: 700,
            fontSize: "1.2rem",
            marginRight: "2rem",
            color: "var(--green-700)",
          }}
        >
          Carbon Mesh
        </span>
        <NavLink to="/" style={linkStyle} end>
          <span className="nav-link-label">Home</span>
        </NavLink>
        <NavLink to="/dashboard" style={linkStyle}>
          <span className="nav-link-label">Dashboard</span>
        </NavLink>
        <NavLink to="/route" style={linkStyle}>
          <span className="nav-link-label">Route Demo</span>
        </NavLink>
        <NavLink to="/plans" style={linkStyle}>
          <span className="nav-link-label">Plans</span>
        </NavLink>
        <NavLink to="/settings" style={linkStyle}>
          <span className="nav-link-label">Settings</span>
        </NavLink>
      </nav>
    </>
  );
}
