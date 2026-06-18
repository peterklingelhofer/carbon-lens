import { useState } from "react";
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

const LINKS: { to: string; label: string; end?: boolean }[] = [
  { to: "/", label: "Home", end: true },
  { to: "/globe", label: "Globe" },
  { to: "/dashboard", label: "Grid Data" },
  { to: "/api-explorer", label: "API Explorer" },
  { to: "/compliance", label: "Compliance" },
  { to: "/sla", label: "SLA" },
  { to: "/scheduler", label: "Scheduler" },
  { to: "/route", label: "Route" },
  { to: "/clean-compute", label: "Clean Compute" },
  { to: "/methodology", label: "Methodology" },
  { to: "/settings", label: "Status" },
  { to: "/about", label: "About" },
];

export function Nav() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

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
          z-index: 20;
        }
        .nav-brand {
          font-weight: 700;
          font-size: clamp(0.95rem, 2.5vw, 1.2rem);
          color: var(--green-700);
          text-decoration: none;
          flex-shrink: 0;
          margin-right: 1rem;
        }
        .nav-links {
          display: flex;
          align-items: center;
          gap: clamp(0rem, 0.5vw, 0.25rem);
          min-width: 0;
        }
        .nav-links a {
          padding: 0.4rem clamp(0.4rem, 1vw, 0.85rem);
          font-size: clamp(0.78rem, 1.5vw, 0.95rem);
          white-space: nowrap;
        }
        /* Hamburger - hidden on desktop, shown on mobile */
        .nav-toggle {
          display: none;
          margin-left: auto;
          background: none;
          border: 1px solid var(--gray-200);
          border-radius: 6px;
          color: inherit;
          font-size: 1.1rem;
          line-height: 1;
          padding: 0.4rem 0.6rem;
          cursor: pointer;
        }
        @media (max-width: 860px) {
          .nav-bar { padding-left: 1.25rem; }
          .nav-toggle { display: inline-flex; align-items: center; }
          .nav-links {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            flex-direction: column;
            align-items: stretch;
            gap: 0.1rem;
            padding: 0.5rem clamp(0.5rem, 3vw, 2rem) 0.75rem;
            background: var(--nav-bg);
            border-bottom: 1px solid var(--gray-200);
            box-shadow: 0 10px 20px rgba(0,0,0,0.12);
          }
          .nav-links.open { display: flex; }
          .nav-links a {
            padding: 0.7rem 0.6rem;
            font-size: 1rem;
            border-radius: 6px;
          }
        }
        @media (prefers-color-scheme: dark) {
          .nav-brand { color: var(--green-400); }
        }
      `}</style>
      <nav className="nav-bar">
        <NavLink to="/" className="nav-brand" onClick={close}>
          Carbon Lens
        </NavLink>
        <button
          type="button"
          className="nav-toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="nav-links"
          onClick={() => setOpen((o) => !o)}
        >
          <span aria-hidden>{open ? "✕" : "☰"}</span>
        </button>
        <div id="nav-links" className={`nav-links${open ? " open" : ""}`}>
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} style={linkStyle} onClick={close}>
              {l.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </>
  );
}
