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


def choose_run_plan(
    regions: list[tuple[str, list[float], list[int]]],
    max_intensity: float | None,
    max_wait_hours: int,
    min_savings_pct: float = 5.0,
) -> tuple[str, int, str]:
    """Co-optimise over region AND time: pick the best (region, hour) to run.

    ``regions`` is a list of ``(label, intensities, surplus_hours)`` (each like the
    inputs to ``choose_run_index``). Returns ``(label, index, reason)``. Priority,
    same spirit as the single-region case but across all candidates:

    1. a clean-surplus window (soonest, then cleanest) -- highest value;
    2. with ``max_intensity``, the soonest hour at/under the cap (then cleanest);
    3. otherwise the globally cleanest (region, hour), unless it beats the best
       run-now option by less than ``min_savings_pct`` -> run now where it's cleanest.
    """
    cands: list[tuple[str, int, float, bool]] = []  # (label, hour, intensity, surplus)
    for label, intensities, surplus_hours in regions:
        window = intensities[: max_wait_hours + 1]
        sset = {h for h in (surplus_hours or []) if 0 <= h < len(window)}
        for h, v in enumerate(window):
            cands.append((label, h, v, h in sset))

    if not cands:
        return (regions[0][0] if regions else ""), 0, "now"

    now_cands = [c for c in cands if c[1] == 0]
    best_now = min(now_cands, key=lambda c: c[2]) if now_cands else None

    # 1) Clean surplus -- run-now surplus beats deferring; else soonest, then cleanest.
    surplus = [c for c in cands if c[3]]
    if surplus:
        now_surplus = [c for c in surplus if c[1] == 0]
        if now_surplus:
            best = min(now_surplus, key=lambda c: c[2])
            return best[0], 0, "surplus_now"
        best = min(surplus, key=lambda c: (c[1], c[2]))
        return best[0], best[1], "surplus"

    # 2) Threshold: soonest hour at/under the cap (then cleanest), across regions.
    if max_intensity is not None:
        under = [c for c in cands if c[2] <= max_intensity]
        if under:
            best = min(under, key=lambda c: (c[1], c[2]))
            return best[0], best[1], "threshold"
        best = min(cands, key=lambda c: c[2])
        return best[0], best[1], "cleanest_fallback"

    # 3) Globally cleanest, but don't defer for a trivial gain over the best now.
    best = min(cands, key=lambda c: c[2])
    if best[1] == 0:
        return best[0], 0, "now"
    if best_now is not None and best_now[2]:
        improvement = (best_now[2] - best[2]) / best_now[2] * 100
        if improvement < min_savings_pct:
            return best_now[0], 0, "now_no_benefit"
    return best[0], best[1], "cleanest"
