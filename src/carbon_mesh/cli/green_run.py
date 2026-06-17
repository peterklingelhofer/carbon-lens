"""Pure decision logic for `carbonlens run` -- kept separate from I/O so it's
unit-testable without the network or the clock."""

from __future__ import annotations


def choose_run_index(
    intensities: list[float],
    max_intensity: float | None,
    max_wait_hours: int,
    surplus_hours: list[int] | None = None,
    min_savings_pct: float = 5.0,
) -> tuple[int, str]:
    """Pick which forecast hour to run at.

    ``intensities[0]`` is now; ``intensities[i]`` is i hours ahead. Only hours
    0..``max_wait_hours`` are considered. ``surplus_hours`` lists offsets the
    forecast flags as clean surplus (renewables abundant -> near-zero marginal),
    the highest-value time to add load. Returns ``(index, reason)``:

    - now is clean surplus -> ``(0, "surplus_now")``.
    - ``max_intensity`` set: earliest hour at/under the cap -> "threshold"; if none,
      the soonest surplus window -> "surplus", else the cleanest -> "cleanest_fallback".
    - ``max_intensity`` None: the soonest surplus window -> "surplus", else the
      cleanest hour -> "cleanest" *unless* it saves less than ``min_savings_pct`` over
      now, in which case run now -> "now_no_benefit" (don't idle for a trivial gain).

    An empty forecast yields ``(0, "now")``.
    """
    window = intensities[: max_wait_hours + 1]
    if not window:
        return 0, "now"

    surplus = sorted(h for h in (surplus_hours or []) if 0 <= h < len(window))

    # Now is clean surplus -- the best possible case, run immediately.
    if surplus and surplus[0] == 0:
        return 0, "surplus_now"

    if max_intensity is not None:
        # Run as soon as the grid is acceptable to the caller.
        for i, value in enumerate(window):
            if value <= max_intensity:
                return i, "threshold"
        # Nothing meets the cap: prefer a clean-surplus window, else the cleanest.
        if surplus:
            return surplus[0], "surplus"
        cleanest = min(range(len(window)), key=lambda i: window[i])
        return cleanest, "cleanest_fallback"

    # No threshold: a clean-surplus window is the highest-value time to run.
    if surplus:
        return surplus[0], "surplus"

    # Otherwise the cleanest hour -- but waiting has its own cost (delayed results,
    # idle infra), so only defer for a meaningful improvement over running now.
    cleanest = min(range(len(window)), key=lambda i: window[i])
    if cleanest == 0:
        return 0, "now"
    now_v = window[0]
    improvement = (now_v - window[cleanest]) / now_v * 100 if now_v else 0.0
    if improvement < min_savings_pct:
        return 0, "now_no_benefit"
    return cleanest, "cleanest"
