"""Shared carbon-intensity classification.

One source of truth for the colour ramp and the green/yellow/red tier so the
badge, embed widget, and Prometheus gauges stay consistent. The two functions
deliberately keep their own cutoffs: the 5-band colour ramp is finer than the
3-band signal tier, so they are not unified.
"""

from __future__ import annotations

# Neutral gray for the "unknown region / zone" state
GRAY = "#9ca3af"


def intensity_color(value: float) -> str:
    """5-band green->red colour ramp for a gCO2/kWh reading (badge + embed)."""
    if value <= 50:
        return "#22c55e"  # green
    if value <= 150:
        return "#84cc16"  # lime
    if value <= 300:
        return "#eab308"  # amber
    if value <= 500:
        return "#f97316"  # orange
    return "#ef4444"  # red


def intensity_tier(value: float) -> int:
    """0 green (<=150), 1 yellow (<=400), 2 red -- same thresholds as the signal state."""
    if value <= 150:
        return 0
    if value <= 400:
        return 1
    return 2
