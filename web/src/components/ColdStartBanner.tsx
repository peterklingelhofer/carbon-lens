import { useEffect, useState } from "react";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";

// The free-tier API (Render) sleeps after ~15 min idle and takes ~50s to wake.
// When any request stays in flight past this threshold, show a banner so the
// wait reads as "waking up", not "broken". CDN/snapshot fetches are sub-second,
// so only a genuine cold start trips it.
const WAKE_THRESHOLD_MS = 4000;

export function ColdStartBanner() {
  const busy = useIsFetching() + useIsMutating() > 0;
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!busy) return;
    const t = setTimeout(() => setShow(true), WAKE_THRESHOLD_MS);
    return () => {
      clearTimeout(t);
      setShow(false);
    };
  }, [busy]);

  if (!show) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.6rem",
        padding: "0.6rem 1rem",
        background: "var(--green-600)",
        color: "white",
        fontSize: "0.85rem",
        boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
      }}
    >
      <span
        aria-hidden
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          border: "2px solid rgba(255,255,255,0.4)",
          borderTopColor: "white",
          animation: "cl-spin 0.7s linear infinite",
          flexShrink: 0,
        }}
      />
      Waking up the API — the free-tier server sleeps after 15 min of inactivity and
      takes ~50s to start. This only happens on the first request.
    </div>
  );
}
