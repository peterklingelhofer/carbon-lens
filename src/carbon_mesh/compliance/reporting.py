"""Compliance reporting engine — generates CSRD-aligned reports from emissions calculations."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from carbon_mesh.models.compliance import (
    AccountingMethod,
    ComplianceReport,
    ComplianceReportSummary,
    EmissionsCalculation,
)


class ReportingEngine:
    """Generate GHG Protocol / CSRD compliance reports from emissions calculations."""

    def generate_report(
        self,
        org_id: str,
        org_name: str,
        calculations: list[EmissionsCalculation],
        report_name: str = "",
    ) -> ComplianceReport:
        """Aggregate emissions calculations into a CSRD-aligned compliance report."""
        if not calculations:
            now = datetime.now(timezone.utc)
            return ComplianceReport(
                id=str(uuid.uuid4()),
                org_id=org_id,
                org_name=org_name,
                report_name=report_name or "Empty Report",
                period_start=now,
                period_end=now,
                generated_at=now,
                scope2_location_kgco2e=0,
                scope2_location_by_provider={},
                scope2_location_by_region={},
                scope2_market_kgco2e=0,
                scope2_market_by_provider={},
                scope2_market_by_region={},
                scope3_cat1_kgco2e=0,
                scope3_cat1_by_provider={},
                scope3_cat1_by_service={},
                total_kgco2e=0,
                total_energy_kwh=0,
                avg_renewable_percentage=0,
                total_cloud_regions_used=0,
                total_providers_used=0,
                carbon_saved_kgco2e=0,
                carbon_saved_percentage=0,
            )

        # Determine period from calculations
        period_start = min(c.period_start for c in calculations)
        period_end = max(c.period_end for c in calculations)

        # Scope 2 (location-based) — direct compute/storage
        s2_calcs = [c for c in calculations if c.scope.value == "scope_2"]
        s2_location_total = sum(c.emissions_kgco2e for c in s2_calcs if c.method == AccountingMethod.LOCATION_BASED)
        s2_market_total = sum(c.emissions_kgco2e for c in s2_calcs if c.method == AccountingMethod.MARKET_BASED)

        # If all calcs use one method, report both as same (conservative)
        if s2_location_total == 0 and s2_market_total > 0:
            s2_location_total = s2_market_total
        elif s2_market_total == 0 and s2_location_total > 0:
            s2_market_total = s2_location_total

        s2_by_provider = _group_sum(s2_calcs, lambda c: c.provider)
        s2_by_region = _group_sum(s2_calcs, lambda c: f"{c.provider}/{c.region}")

        # Scope 3 Category 1 — managed cloud services
        s3_calcs = [c for c in calculations if c.scope.value == "scope_3_cat1"]
        s3_total = sum(c.emissions_kgco2e for c in s3_calcs)
        s3_by_provider = _group_sum(s3_calcs, lambda c: c.provider)
        s3_by_service = _group_sum(s3_calcs, lambda c: c.service)

        # Totals
        total_kgco2e = s2_location_total + s3_total
        total_energy = sum(c.energy_kwh for c in calculations)
        all_regions = {f"{c.provider}/{c.region}" for c in calculations}
        all_providers = {c.provider for c in calculations}

        # Average renewable %
        weighted_renewable = sum(c.renewable_percentage * c.energy_kwh for c in calculations)
        avg_renewable = weighted_renewable / total_energy if total_energy > 0 else 0

        # Carbon savings estimate: compare actual intensity to worst-case (coal baseline ~900 gCO2/kWh)
        coal_baseline_gco2 = 900.0
        worst_case_kgco2e = total_energy * coal_baseline_gco2 / 1000.0
        carbon_saved = max(0, worst_case_kgco2e - total_kgco2e)
        saved_pct = (carbon_saved / worst_case_kgco2e * 100) if worst_case_kgco2e > 0 else 0

        # Data quality summary
        quality_counts: dict[str, int] = defaultdict(int)
        for c in calculations:
            quality_counts[c.emission_factor_quality] += 1

        # Data sources used
        sources = sorted({c.emission_factor_source for c in calculations})

        if not report_name:
            report_name = f"Cloud Emissions Report — {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}"

        return ComplianceReport(
            id=str(uuid.uuid4()),
            org_id=org_id,
            org_name=org_name,
            report_name=report_name,
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            scope2_location_kgco2e=round(s2_location_total, 4),
            scope2_location_by_provider=_round_dict(s2_by_provider),
            scope2_location_by_region=_round_dict(s2_by_region),
            scope2_market_kgco2e=round(s2_market_total, 4),
            scope2_market_by_provider=_round_dict(s2_by_provider),
            scope2_market_by_region=_round_dict(s2_by_region),
            scope3_cat1_kgco2e=round(s3_total, 4),
            scope3_cat1_by_provider=_round_dict(s3_by_provider),
            scope3_cat1_by_service=_round_dict(s3_by_service),
            total_kgco2e=round(total_kgco2e, 4),
            total_energy_kwh=round(total_energy, 4),
            avg_renewable_percentage=round(avg_renewable, 1),
            total_cloud_regions_used=len(all_regions),
            total_providers_used=len(all_providers),
            carbon_saved_kgco2e=round(carbon_saved, 4),
            carbon_saved_percentage=round(saved_pct, 1),
            data_sources=sources,
            data_quality_summary=dict(quality_counts),
            calculation_count=len(calculations),
            eu_taxonomy_eligible=True,
            eu_taxonomy_aligned=avg_renewable >= 80,  # Simplified: aligned if >80% renewable
            taxonomy_notes=(
                "Substantially contributes to climate change mitigation via carbon-aware compute scheduling. "
                "EU Taxonomy alignment requires >80% renewable energy and Do No Significant Harm assessment."
            ),
        )

    def summarize(self, report: ComplianceReport) -> ComplianceReportSummary:
        return ComplianceReportSummary(
            id=report.id,
            report_name=report.report_name,
            period_start=report.period_start,
            period_end=report.period_end,
            generated_at=report.generated_at,
            total_kgco2e=report.total_kgco2e,
            total_energy_kwh=report.total_energy_kwh,
            carbon_saved_percentage=report.carbon_saved_percentage,
        )


def _group_sum(
    calcs: list[EmissionsCalculation],
    key_fn: object,
) -> dict[str, float]:
    """Group calculations by key function and sum emissions."""
    groups: dict[str, float] = defaultdict(float)
    for c in calcs:
        groups[key_fn(c)] += c.emissions_kgco2e  # type: ignore[operator]
    return dict(groups)


def _round_dict(d: dict[str, float], digits: int = 4) -> dict[str, float]:
    return {k: round(v, digits) for k, v in d.items()}
