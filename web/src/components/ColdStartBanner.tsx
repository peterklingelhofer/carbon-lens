import { useEffect, useState } from "react";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { getLastApiResponseAt } from "../api/client";

// The free-tier API (Render) sleeps after ~15 min idle and takes ~50s to wake.
// When an API request stays in flight past this threshold, show a banner so the
// wait reads as a deliberate state, not "broken".
const DELAY_MS = 4000;

// If the API answered within this window it's almost certainly still awake
// (Render's idle timeout is ~15 min), so a slow request is just slow — show a
// neutral spinner instead of the "waking up" copy. Only show the cold-start
// message when we have NOT heard from the API recently (first request / long idle).
const LIKELY_AWAKE_MS = 10 * 60 * 1000;

type Mode = "hidden" | "loading" | "waking";

export function ColdStartBanner() {
  // Count only real API traffic — exclude the CDN snapshot query, which is fast
  // and unrelated to the API server waking up.
  const apiFetching = useIsFetching({ predicate: (q) => q.queryKey[0] !== "snapshot" });
  const mutating = useIsMutating();
  const busy = apiFetching + mutating > 0;
  const [mode, setMode] = useState<Mode>("hidden");

  useEffect(() => {
    if (!busy) return;
    const t = setTimeout(() => {
      const last = getLastApiResponseAt();
      const likelyAwake = last > 0 && Date.now() - last < LIKELY_AWAKE_MS;
      setMode(likelyAwake ? "loading" : "waking");
    }, DELAY_MS);
    return () => {
      clearTimeout(t);
      setMode("hidden");
    };
  }, [busy]);

  if (mode === "hidden") return null;

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
      {mode === "waking"
        ? "Waking up the API — the free-tier server sleeps after 15 min of inactivity and takes ~50s to start. This only happens on the first request."
        : "Loading…"}
    </div>
  );
}
