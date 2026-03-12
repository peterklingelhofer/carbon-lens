import pytest

from carbon_mesh.engine.router import RoutingEngine
from carbon_mesh.models.routing import JobConstraints


@pytest.mark.asyncio
async def test_route_picks_greenest(engine: RoutingEngine):
    constraints = JobConstraints(providers=["aws", "gcp"])
    response = await engine.route(constraints)

    # Quebec (CA-QC) has 10 gCO2/kWh — should be top pick
    assert response.recommended.carbon_intensity_gco2_kwh <= 30
    assert response.recommended.renewable_percentage >= 90


@pytest.mark.asyncio
async def test_route_respects_data_residency(engine: RoutingEngine):
    constraints = JobConstraints(providers=["aws"], data_residency=["EU"])
    response = await engine.route(constraints)

    # Should only return EU regions
    eu_prefixes = ("eu-",)
    assert response.recommended.region.startswith(eu_prefixes)


@pytest.mark.asyncio
async def test_route_specific_regions(engine: RoutingEngine):
    constraints = JobConstraints(
        providers=["aws"],
        candidate_regions=["us-east-1", "us-west-2"],
    )
    response = await engine.route(constraints)

    # us-west-2 (Oregon/hydro) should beat us-east-1 (Virginia/PJM)
    assert response.recommended.region == "us-west-2"
    assert len(response.alternatives) == 1
    assert response.alternatives[0].region == "us-east-1"


@pytest.mark.asyncio
async def test_route_invalid_constraints(engine: RoutingEngine):
    constraints = JobConstraints(
        providers=["aws"],
        candidate_regions=["nonexistent-region"],
    )
    with pytest.raises(ValueError, match="No matching regions"):
        await engine.route(constraints)
