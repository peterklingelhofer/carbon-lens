from pathlib import Path

import yaml

from carbon_mesh.models.region import CloudRegion


def _parse_region(provider: str, region_name: str, region_data: dict) -> CloudRegion:
    return CloudRegion(
        provider=provider,
        region=region_name,
        grid_zone=region_data["grid_zone"],
        location=region_data["location"],
        latitude=region_data["latitude"],
        longitude=region_data["longitude"],
        eia_respondent=region_data.get("eia_respondent"),
        gridstatus_iso=region_data.get("gridstatus_iso"),
    )


class GridMapper:
    def __init__(self, yaml_path: Path) -> None:
        with open(yaml_path) as f:
            self._data: dict = yaml.safe_load(f)

    def get_region(self, provider: str, region: str) -> CloudRegion | None:
        provider_data = self._data.get(provider, {})
        region_data = provider_data.get(region)
        if region_data is None:
            return None
        return _parse_region(provider, region, region_data)

    def list_regions(self, provider: str | None = None) -> list[CloudRegion]:
        regions: list[CloudRegion] = []
        providers = [provider] if provider else list(self._data.keys())
        for p in providers:
            for region_name, region_data in self._data.get(p, {}).items():
                regions.append(_parse_region(p, region_name, region_data))
        return regions

    def list_providers(self) -> list[str]:
        return list(self._data.keys())

    def grid_zones(self) -> list[CloudRegion]:
        """One representative region per distinct grid zone, sorted by zone. Used
        for zone-level lookups (e.g. on-prem datacenters that aren't a cloud region
        but sit on a grid zone we already cover)."""
        seen: dict[str, CloudRegion] = {}
        for provider in self._data:
            for region_name, region_data in self._data[provider].items():
                region = _parse_region(provider, region_name, region_data)
                seen.setdefault(region.grid_zone, region)
        return sorted(seen.values(), key=lambda r: r.grid_zone)

    def get_grid_zone(self, provider: str, region: str) -> str | None:
        region_obj = self.get_region(provider, region)
        return region_obj.grid_zone if region_obj else None

    def get_eia_respondent(self, provider: str, region: str) -> str | None:
        region_obj = self.get_region(provider, region)
        return region_obj.eia_respondent if region_obj else None

    def get_gridstatus_iso(self, provider: str, region: str) -> str | None:
        region_obj = self.get_region(provider, region)
        return region_obj.gridstatus_iso if region_obj else None

    def get_eia_respondents(self) -> dict[str, str]:
        """Return mapping of EIA respondent → grid_zone for all regions that have one."""
        result: dict[str, str] = {}
        for provider in self._data:
            for region_data in self._data[provider].values():
                resp = region_data.get("eia_respondent")
                if resp:
                    result[resp] = region_data["grid_zone"]
        return result
