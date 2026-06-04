import { type ReactNode, useCallback, useId, useState } from "react";

// A small "i" icon that reveals a plain-language definition on hover, focus, or
// click — for domain jargon (gCO₂/kWh, carbon intensity, balancing authority…).
// Keyboard-accessible: it's a real button with an aria-label and role=tooltip.
export function InfoTip({
  label,
  text,
  placement = "bottom",
}: {
  label: string;
  text: ReactNode;
  placement?: "top" | "bottom";
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const pos = placement === "top" ? { bottom: "calc(100% + 6px)" } : { top: "calc(100% + 6px)" };

  // The tip is centred on the icon, but near a screen edge centring would push
  // it off-window. A callback ref measures the tip the moment it mounts (before
  // paint, so no flicker) and nudges it back via the transform so it's always
  // fully on-screen — works for icons anywhere (legend corner, table cells…).
  const clampToViewport = useCallback((el: HTMLSpanElement | null) => {
    if (!el) return;
    el.style.transform = "translateX(-50%)";
    const pad = 8;
    const r = el.getBoundingClientRect();
    let shift = 0;
    if (r.left < pad) shift = pad - r.left;
    else if (r.right > window.innerWidth - pad) shift = window.innerWidth - pad - r.right;
    if (shift) el.style.transform = `translateX(calc(-50% + ${shift}px))`;
  }, []);

  return (
    <span
      style={{
        position: "relative",
        display: "inline-flex",
        verticalAlign: "middle",
      }}
    >
      <button
        type="button"
        aria-label={`What is ${label}?`}
        aria-describedby={open ? id : undefined}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen((o) => !o);
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        style={{
          width: 15,
          height: 15,
          borderRadius: "50%",
          border: "1px solid currentColor",
          background: "transparent",
          color: "inherit",
          opacity: 0.65,
          fontSize: 10,
          fontStyle: "italic",
          fontFamily: "Georgia, serif",
          fontWeight: 700,
          lineHeight: 1,
          cursor: "help",
          padding: 0,
          marginLeft: 5,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        i
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          ref={clampToViewport}
          style={{
            position: "absolute",
            ...pos,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 100,
            width: 230,
            maxWidth: "72vw",
            background: "var(--card-bg)",
            color: "var(--gray-700)",
            border: "1px solid var(--gray-200)",
            borderRadius: 8,
            padding: "8px 10px",
            fontSize: "0.72rem",
            fontWeight: 400,
            // Reset inherited text styling from the surrounding context: the
            // globe title's drop-shadow and the legend labels' uppercase /
            // italics would otherwise bleed into the tip and garble it.
            fontStyle: "normal",
            textTransform: "none",
            letterSpacing: "normal",
            textShadow: "none",
            lineHeight: 1.5,
            textAlign: "left",
            boxShadow: "var(--card-shadow)",
            whiteSpace: "normal",
            pointerEvents: "none",
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}
