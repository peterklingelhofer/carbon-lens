"""Emissions calculator: converts cloud usage + carbon intensity into kgCO2e.

Follows GHG Protocol Corporate Standard, Scope 2 Guidance (2015), and Scope 3
Category 1 methodology for purchased cloud services.

Two conformance limits, both real and neither previously written down:

1. Scope 2 Guidance §1.5.1 requires DUAL REPORTING: a company with contractual
   instruments "shall report scope 2 emissions in two ways", location-based and
   market-based, labelled. This calculator takes a single `method` and returns a
   single figure, so a caller can produce a one-method report that does not conform.
   Callers wanting conformance must run it twice and report both.
2. The Scope 2 / Scope 3 Cat 1 split below keys off a hardcoded list of managed
   service names. That split is this project's own judgement about where the
   operational boundary falls; the standard does not enumerate cloud services.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from carbonlens.carbon_sources.base import CarbonDataSource
from carbonlens.citations_generated import CitationId
from carbonlens.grid.mapper import GridMapper
from carbonlens.models.compliance import (
    PROVIDER_PUE,
    AccountingMethod,
    CloudUsageRecord,
    EmissionsCalculation,
    EmissionScope,
)
from carbonlens.provenance import data_quality

logger = logging.getLogger(__name__)

# The standards this calculator implements.
CITATIONS: tuple[CitationId, ...] = (
    "ghg-protocol-scope2-guidance",
    "ghg-protocol-corporate-standard",
    "ghg-protocol-scope3-standard",
    "gsf-sci-specification",
)


class EmissionsCalculator:
    """Calculate emissions from cloud usage records using real-time grid data."""

    def __init__(
        self,
        carbon_source: CarbonDataSource,
        grid_mapper: GridMapper,
    ) -> None:
        self._carbon_source = carbon_source
        self._grid_mapper = grid_mapper

    async def calculate(
        self,
        usage_records: list[CloudUsageRecord],
        method: AccountingMethod = AccountingMethod.LOCATION_BASED,
    ) -> list[EmissionsCalculation]:
        """Calculate emissions for a batch of usage records.

        Steps (GHG Protocol):
        1. Map cloud region to grid zone
        2. Fetch carbon intensity for each grid zone
        3. emissions_kgco2e = energy_kwh × intensity_gco2_kwh / 1000
        """
        if not usage_records:
            return []

        # 1. Collect unique grid zones
        region_to_zone: dict[str, str] = {}
        for rec in usage_records:
            key = f"{rec.provider}/{rec.region}"
            if key not in region_to_zone:
                zone = self._grid_mapper.get_grid_zone(rec.provider, rec.region)
                if zone:
                    region_to_zone[key] = zone

        # 2. Batch-fetch carbon intensity
        unique_zones = list(set(region_to_zone.values()))
        intensities = await self._carbon_source.get_carbon_intensity_batch(unique_zones)

        # 3. Calculate emissions for each record
        now = datetime.now(UTC)
        calculations: list[EmissionsCalculation] = []

        for rec in usage_records:
            key = f"{rec.provider}/{rec.region}"
            zone = region_to_zone.get(key)
            if not zone:
                logger.warning("No grid zone for %s, skipping", key)
                continue

            ci = intensities.get(zone)
            if not ci:
                logger.warning("No carbon data for zone %s, skipping", zone)
                continue

            emissions_kgco2e = rec.energy_kwh * ci.carbon_intensity_gco2_kwh / 1000.0

            calculations.append(
                EmissionsCalculation(
                    id=str(uuid.uuid4()),
                    org_id=rec.org_id,
                    scope=_scope_for_service(rec.service),
                    method=method,
                    provider=rec.provider,
                    region=rec.region,
                    grid_zone=zone,
                    service=rec.service,
                    resource_type=rec.resource_type,
                    usage_quantity=rec.usage_quantity,
                    usage_unit=rec.usage_unit,
                    energy_kwh=rec.energy_kwh,
                    emission_factor_gco2_kwh=ci.carbon_intensity_gco2_kwh,
                    emission_factor_source=ci.source,
                    emission_factor_quality=_data_quality(ci.source),
                    emissions_kgco2e=round(emissions_kgco2e, 6),
                    renewable_percentage=ci.renewable_percentage,
                    pue=PROVIDER_PUE.get(rec.provider, PROVIDER_PUE["default"]),
                    period_start=rec.period_start,
                    period_end=rec.period_end,
                    calculated_at=now,
                )
            )

        return calculations


def _scope_for_service(service: str) -> EmissionScope:
    """Classify service into GHG Protocol emission scope.

    Scope 2: Direct electricity consumption (compute, storage you operate)
    Scope 3 Cat 1: Managed services where the provider operates the infra
    """
    managed_services = {
        "lambda",
        "cloud-functions",
        "cloud-run",
        "fargate",
        "dynamodb",
        "aurora-serverless",
        "bigquery",
        "cosmosdb",
        "cloudfront",
        "cloud-cdn",
        "azure-cdn",
        "sqs",
        "sns",
        "pubsub",
        "event-grid",
    }
    if service.lower() in managed_services:
        return EmissionScope.SCOPE_3_CAT1
    return EmissionScope.SCOPE_2


def _data_quality(source: str) -> str:
    """Map carbon data source to data quality level per GHG Protocol.

    Delegates to the provenance registry rather than keeping a second list of
    source names. The previous local list had drifted out of sync with the strings
    providers actually stamp on a reading: it tested for "uk", "aemo" and "eskom"
    while the providers emit "uk_carbon_intensity", "openelectricity" and
    "eskom_heuristic", so every UK, Australian, Canadian and Taiwanese reading was
    graded "estimated" on compliance reports despite coming from a live
    grid-operator feed, and the Eskom time-of-day model was graded "measured".
    """
    return data_quality(source)
