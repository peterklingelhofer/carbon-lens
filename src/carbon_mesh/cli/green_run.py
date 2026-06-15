"""Pure decision logic for `carbonlens run` -- kept separate from I/O so it's
unit-testable without the network or the clock."""

from __future__ import annotations


def choose_run_index(
    intensities: list[float],
    max_intensity: float | None,
    max_wait_hours: int,
) -> tuple[int, str]:
    """Pick which forecast hour to run at.

    ``intensities[0]`` is now; ``intensities[i]`` is i hours ahead. Only hours
    0..``max_wait_hours`` are considered. Returns ``(index, reason)``:

    - ``max_intensity`` set: the earliest hour at/under the threshold -> reason
      "threshold"; if none in the window, the cleanest hour -> "cleanest_fallback".
    - ``max_intensity`` is None: the cleanest hour in the window -> "cleanest".

    An empty forecast yields ``(0, "now")``.
    """
    window = intensities[: max_wait_hours + 1]
    if not window:
        return 0, "now"

    cleanest = min(range(len(window)), key=lambda i: window[i])
    if max_intensity is None:
        return cleanest, "cleanest"

    for i, value in enumerate(window):
        if value <= max_intensity:
            return i, "threshold"
    return cleanest, "cleanest_fallback"
