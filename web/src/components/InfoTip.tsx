import { type ReactNode, useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

// A small "i" icon that reveals a plain-language definition on hover, focus, or
// click - for domain jargon (gCO₂/kWh, carbon intensity, balancing authority…).
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
  const btnRef = useRef<HTMLButtonElement>(null);

  // The tip is rendered in a portal on document.body with fixed positioning, so
  // an ancestor with overflow:auto/hidden (the globe detail card, a table cell)
  // can never clip it. A callback ref measures both the icon and the tip the
  // moment it mounts (before paint, no flicker) and places the tip centred on
  // the icon, above or below per `placement`, then clamps it into the viewport.
  const positionTip = useCallback(
    (el: HTMLSpanElement | null) => {
      if (!el || !btnRef.current) return;
      const pad = 8;
      const b = btnRef.current.getBoundingClientRect();
      const t = el.getBoundingClientRect();
      let left = b.left + b.width / 2 - t.width / 2;
      left = Math.max(pad, Math.min(left, window.innerWidth - pad - t.width));
      const top =
        placement === "top"
          ? Math.max(pad, b.top - t.height - 6)
          : Math.min(b.bottom + 6, window.innerHeight - pad - t.height);
      el.style.left = `${left}px`;
      el.style.top = `${top}px`;
      el.style.visibility = "visible";
    },
    [placement],
  );

  // A fixed tip doesn't follow a scrolling ancestor, so close it on any scroll
  // or resize rather than letting it drift away from its icon.
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  return (
    <span
      style={{
        position: "relative",
        display: "inline-flex",
        verticalAlign: "middle",
      }}
    >
      <button
        ref={btnRef}
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
      {open &&
        createPortal(
          <span
            id={id}
            role="tooltip"
            ref={positionTip}
            style={{
              position: "fixed",
              left: 0,
              top: 0,
              visibility: "hidden",
              zIndex: 1000,
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
          </span>,
          document.body,
        )}
    </span>
  );
}
