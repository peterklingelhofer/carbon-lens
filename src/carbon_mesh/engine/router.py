import uuid
from datetime import UTC, datetime

from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.engine.cache import IntensityCache
from carbon_mesh.engine.scorer import score_candidates
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.models.region import CloudRegion
from carbon_mesh.models.routing import (
    JobConstraints,
    RegionRecommendation,
    RouteResponse,
)

# Simple data residency mapping for filtering
_RESIDENCY_PREFIXES: dict[str, list[str]] = {
    "US": ["us-"],
    "EU": ["eu-", "europe-"],
    "CA": ["ca-", "canada", "northamerica-northeast"],
    "AP": ["ap-", "asia-"],
}


def _matches_residency(region: CloudRegion, residency: list[str]) -> bool:
    region_lower = region.region.lower()
    for r in residency:
        r_upper = r.upper()
        prefixes = _RESIDENCY_PREFIXES.get(r_upper, [])
        if prefixes:
            if any(region_lower.startswith(p) for p in prefixes):
                return True
        elif r_upper in region.location.upper():
            return True
    return False


class RoutingEngine:
    def __init__(
        self,
        carbon_source: CarbonDataSource,
        grid_mapper: GridMapper,
        cache: IntensityCache,
    ) -> None:
        self._carbon_source = carbon_source
        self._grid_mapper = grid_mapper
        self._cache = cache

    async def route(self, constraints: JobConstraints) -> RouteResponse:
        candidates: list[CloudRegion] = []
        for provider in constraints.providers:
            regions = self._grid_mapper.list_regions(provider)
            for r in regions:
                if constraints.candidate_regions and r.region not in constraints.candidate_regions:
                    continue
                if constraints.data_residency and not _matches_residency(
                    r, constraints.data_residency
                ):
                    continue
                candidates.append(r)

        if not candidates:
            raise ValueError(
                f"No matching regions found for providers={constraints.providers}, "
                f"candidate_regions={constraints.candidate_regions}, "
                f"data_residency={constraints.data_residency}"
            )

        # Deduplicate grid zones so we fetch each zone's carbon data only once
        zone_set = list({c.grid_zone for c in candidates})
        intensities = await self._cache.get_or_fetch_batch(
            zone_set, self._carbon_source.get_carbon_intensity_batch
        )

        scorer_input = []
        for c in candidates:
            ci = intensities.get(c.grid_zone)
            if ci is None:
                continue
            scorer_input.append(
                {
                    "provider": c.provider,
                    "region": c.region,
                    "grid_zone": c.grid_zone,
                    "carbon_intensity": ci.carbon_intensity_gco2_kwh,
                    "renewable_percentage": ci.renewable_percentage,
                }
            )

        scored = score_candidates(
            scorer_input,
            carbon_weight=constraints.carbon_weight,
            cost_weight=constraints.cost_weight,
        )

        if not scored:
            raise ValueError("No candidates could be scored — carbon data unavailable")

        best = scored[0]
        alternatives = scored[1:]

        return RouteResponse(
            recommended=RegionRecommendation(
                provider=best.provider,
                region=best.region,
                grid_zone=best.grid_zone,
                carbon_intensity_gco2_kwh=best.carbon_intensity,
                renewable_percentage=best.renewable_percentage,
                score=best.score,
                carbon_savings_vs_worst_pct=best.carbon_savings_vs_worst_pct,
            ),
            alternatives=[
                RegionRecommendation(
                    provider=s.provider,
                    region=s.region,
                    grid_zone=s.grid_zone,
                    carbon_intensity_gco2_kwh=s.carbon_intensity,
                    renewable_percentage=s.renewable_percentage,
                    score=s.score,
                    carbon_savings_vs_worst_pct=s.carbon_savings_vs_worst_pct,
                )
                for s in alternatives
            ],
            request_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
        )
