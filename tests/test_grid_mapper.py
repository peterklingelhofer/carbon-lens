from carbon_mesh.grid.mapper import GridMapper


def test_get_region(grid_mapper: GridMapper):
    region = grid_mapper.get_region("aws", "us-west-2")
    assert region is not None
    assert region.grid_zone == "US-NW-BPAT"
    assert region.provider == "aws"


def test_get_region_unknown(grid_mapper: GridMapper):
    assert grid_mapper.get_region("aws", "nonexistent") is None


def test_list_regions_all(grid_mapper: GridMapper):
    regions = grid_mapper.list_regions()
    assert len(regions) > 30  # We defined ~40 regions


def test_list_regions_by_provider(grid_mapper: GridMapper):
    aws_regions = grid_mapper.list_regions("aws")
    gcp_regions = grid_mapper.list_regions("gcp")
    assert all(r.provider == "aws" for r in aws_regions)
    assert all(r.provider == "gcp" for r in gcp_regions)


def test_list_providers(grid_mapper: GridMapper):
    providers = grid_mapper.list_providers()
    assert set(providers) == {"aws", "gcp", "azure"}


def test_get_grid_zone(grid_mapper: GridMapper):
    assert grid_mapper.get_grid_zone("gcp", "europe-north1") == "FI"
    assert grid_mapper.get_grid_zone("azure", "swedencentral") == "SE-SE3"
