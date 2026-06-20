from dataclasses import dataclass


@dataclass
class ScoredCandidate:
    provider: str
    region: str
    grid_zone: str
    carbon_intensity: float
    renewable_percentage: float
    score: float
    carbon_savings_vs_worst_pct: float


def score_candidates(
    candidates: list[dict],
    carbon_weight: float = 0.7,
    cost_weight: float = 0.3,
) -> list[ScoredCandidate]:
    """Score and rank candidates by carbon intensity.

    Lower score = greener; the returned list is sorted cleanest-first, so the
    router relies on ``scored[0]`` being the best pick.

    candidates: list of dicts with keys:
        provider, region, grid_zone, carbon_intensity, renewable_percentage
    """
    if not candidates:
        return []

    intensities = [c["carbon_intensity"] for c in candidates]
    min_intensity = min(intensities)
    max_intensity = max(intensities)
    intensity_range = max_intensity - min_intensity

    scored = []
    for c in candidates:
        if intensity_range > 0:
            normalized_carbon = (c["carbon_intensity"] - min_intensity) / intensity_range
        else:
            normalized_carbon = 0.0

        # cost_weight is a no-op placeholder for now: cost data isn't wired in, so
        # the score is carbon-only
        score = carbon_weight * normalized_carbon

        if max_intensity > 0:
            savings = (1 - c["carbon_intensity"] / max_intensity) * 100
        else:
            savings = 0.0

        scored.append(
            ScoredCandidate(
                provider=c["provider"],
                region=c["region"],
                grid_zone=c["grid_zone"],
                carbon_intensity=c["carbon_intensity"],
                renewable_percentage=c["renewable_percentage"],
                score=round(score, 4),
                carbon_savings_vs_worst_pct=round(savings, 1),
            )
        )

    scored.sort(key=lambda s: s.score)
    return scored
