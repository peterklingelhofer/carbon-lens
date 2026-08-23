"""Detect a clean-surplus (likely oversupply / curtailment) moment on a grid.

When renewables dominate generation, carbon is very low, and little or no fossil
sits on the margin, extra demand is largely served by clean power that might
otherwise be curtailed (spilled). Those are the highest-value moments to shift
flexible load into: running then is close to carbon-free at the margin.

This is a heuristic from renewable share, intensity, and the marginal estimate --
NOT measured curtailment or price data, which we don't have for free. It errs
conservative so a 'surplus' flag is a strong, defensible signal rather than a guess.
"""


def is_clean_surplus(
    renewable_pct: float,
    intensity_gco2_kwh: float,
    marginal_gco2_kwh: float | None,
) -> bool:
    """Whether the grid looks like clean oversupply right now (see module docstring)."""
    # Renewables must dominate generation.
    if renewable_pct < 85:
        return False
    # And the grid must be genuinely low-carbon right now.
    if intensity_gco2_kwh > 80:
        return False
    # And the margin must be clean: a high marginal means fossil still sets the price,
    # so extra load would burn fuel rather than soak up would-be-curtailed renewables.
    if marginal_gco2_kwh is not None and marginal_gco2_kwh > 100:
        return False
    return True


def surplus_offsets(points) -> list[int]:
    """Indices of the forecast points that look like clean surplus.

    Duck-typed on CarbonIntensity (renewable_percentage, carbon_intensity_gco2_kwh,
    marginal_intensity_gco2_kwh) so it works for both the live reading and projected
    points (whose marginal is unknown -> treated as clean if share and carbon qualify).
    """
    return [
        i
        for i, p in enumerate(points)
        if is_clean_surplus(
            p.renewable_percentage,
            p.carbon_intensity_gco2_kwh,
            p.marginal_intensity_gco2_kwh,
        )
    ]
