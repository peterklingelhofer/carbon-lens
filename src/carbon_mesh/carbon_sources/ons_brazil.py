"""ONS Brazil provider — free, no API key required.

Covers 5 Brazilian power subsystems: S (South), SE (Southeast),
NE (Northeast), N (North), CS (Centro-South).
Data from ONS (Operador Nacional do Sistema Elétrico).
"""

from datetime import datetime, timezone

import httpx

from carbon_mesh.models.carbon import CarbonIntensity

BRAZIL_ZONES = {"BR-S", "BR-SE", "BR-NE", "BR-N", "BR-CS"}

API_URL = "https://integra.ons.org.br/api/energiaagora/Get"

# Typical defaults (Brazil is ~60-70% hydro)
_REGION_DEFAULTS: dict[str, tuple[float, float]] = {
    "BR-S": (80, 85),    # South — heavy hydro
    "BR-SE": (120, 70),  # Southeast — hydro + thermal
    "BR-NE": (100, 75),  # Northeast — wind + hydro
    "BR-N": (60, 90),    # North — almost all hydro
    "BR-CS": (110, 72),  # Centro-South — mixed
}

# ONS subsystem name → zone mapping
_SUBSYSTEM_MAP = {
    "Sul": "BR-S",
    "Sudeste": "BR-SE",
    "Nordeste": "BR-NE",
    "Norte": "BR-N",
    "Centro-Sul": "BR-CS",
    "Sul/Sudeste/Centro-Oeste": "BR-SE",
}


class ONSBrazilCarbonSource:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in BRAZIL_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        if grid_zone not in BRAZIL_ZONES:
            raise ValueError(f"Unknown Brazil zone: {grid_zone}")

        try:
            return await self._fetch_live(grid_zone)
        except Exception:
            return self._heuristic(grid_zone)

    async def _fetch_live(self, grid_zone: str) -> CarbonIntensity:
        resp = await self._client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

        # Parse generation by source
        hydro_mw = 0.0
        thermal_mw = 0.0
        wind_mw = 0.0
        solar_mw = 0.0
        nuclear_mw = 0.0
        total_mw = 0.0

        for entry in data if isinstance(data, list) else data.get("Data", data.get("data", [])):
            if not isinstance(entry, dict):
                continue
            subsystem = entry.get("subsistema", entry.get("Subsistema", ""))
            zone = _SUBSYSTEM_MAP.get(subsystem)
            if zone != grid_zone:
                continue

            source_type = entry.get("combustivel", entry.get("tipo", "")).lower()
            value = float(entry.get("geracao", entry.get("valor", 0)) or 0)

            if "hidr" in source_type or "hydro" in source_type:
                hydro_mw += value
            elif "eolic" in source_type or "wind" in source_type:
                wind_mw += value
            elif "solar" in source_type:
                solar_mw += value
            elif "nucle" in source_type:
                nuclear_mw += value
            elif "termi" in source_type or "therm" in source_type:
                thermal_mw += value

            total_mw += value

        if total_mw == 0:
            raise ValueError("No generation data")

        # Thermal in Brazil is mostly gas (~490 gCO2/kWh)
        intensity = (thermal_mw * 490) / total_mw
        renewable_pct = ((hydro_mw + wind_mw + solar_mw) / total_mw) * 100

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=round(intensity, 1),
            renewable_percentage=round(renewable_pct, 1),
            timestamp=datetime.now(timezone.utc),
            source="ons_brazil",
        )

    def _heuristic(self, grid_zone: str) -> CarbonIntensity:
        intensity, renewable_pct = _REGION_DEFAULTS.get(grid_zone, (100, 75))
        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=float(intensity),
            renewable_percentage=float(renewable_pct),
            timestamp=datetime.now(timezone.utc),
            source="ons_brazil_heuristic",
        )

    async def get_carbon_intensity_batch(
        self, grid_zones: list[str]
    ) -> dict[str, CarbonIntensity]:
        results: dict[str, CarbonIntensity] = {}
        for zone in grid_zones:
            if self.can_handle(zone):
                try:
                    results[zone] = await self.get_carbon_intensity(zone)
                except Exception:
                    pass
        return results
