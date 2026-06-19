import hashlib
import json
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
    """Region <-> grid-zone lookups, backed by a static YAML map.

    The map never changes after load, so every region is parsed into a
    ``CloudRegion`` exactly once at construction and the derived lookups are
    precomputed. Read paths (hit on nearly every API request and inside the
    routing/scheduler loops) are then plain dict/list reads instead of
    re-validating ~75 Pydantic models per call -- the largest steady-state CPU
    win in the API.
    """

    def __init__(self, yaml_path: Path) -> None:
        with open(yaml_path) as f:
            data: dict = yaml.safe_load(f)

        self._regions: list[CloudRegion] = []
        self._by_key: dict[tuple[str, str], CloudRegion] = {}
        self._by_provider: dict[str, list[CloudRegion]] = {}
        self._providers: list[str] = list(data.keys())
        self._eia_respondents: dict[str, str] = {}
        self._regions_payload: dict[str | None, tuple[list[dict], str]] = {}

        for provider in data:
            bucket = self._by_provider.setdefault(provider, [])
            for region_name, region_data in data[provider].items():
                region = _parse_region(provider, region_name, region_data)
                self._regions.append(region)
                self._by_key[(provider, region_name)] = region
                bucket.append(region)
                if region.eia_respondent:
                    self._eia_respondents[region.eia_respondent] = region.grid_zone

        # One representative region per distinct grid zone, sorted by zone.
        zone_reps: dict[str, CloudRegion] = {}
        for region in self._regions:
            zone_reps.setdefault(region.grid_zone, region)
        self._zone_reps: list[CloudRegion] = sorted(zone_reps.values(), key=lambda r: r.grid_zone)

    def get_region(self, provider: str, region: str) -> CloudRegion | None:
        return self._by_key.get((provider, region))

    def list_regions(self, provider: str | None = None) -> list[CloudRegion]:
        if provider is None:
            return list(self._regions)
        return list(self._by_provider.get(provider, ()))

    def list_providers(self) -> list[str]:
        return list(self._providers)

    def regions_payload(self, provider: str | None = None) -> tuple[list[dict], str]:
        """The ``/regions`` JSON body and its ETag, computed once per provider filter.

        The region map is immutable, so the Pydantic ``model_dump`` and the MD5
        hash are pure waste to redo per request -- memoize both."""
        cached = self._regions_payload.get(provider)
        if cached is None:
            content = [r.model_dump() for r in self.list_regions(provider)]
            etag = '"' + hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest() + '"'
            cached = (content, etag)
            self._regions_payload[provider] = cached
        return cached

    def grid_zones(self) -> list[CloudRegion]:
        """One representative region per distinct grid zone, sorted by zone. Used
        for zone-level lookups (e.g. on-prem datacenters that aren't a cloud region
        but sit on a grid zone we already cover)."""
        return list(self._zone_reps)

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
        return dict(self._eia_respondents)
