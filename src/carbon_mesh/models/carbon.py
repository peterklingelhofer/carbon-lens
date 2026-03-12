from datetime import datetime

from pydantic import BaseModel, Field


class CarbonIntensity(BaseModel):
    grid_zone: str
    carbon_intensity_gco2_kwh: float = Field(ge=0, description="Grams CO2 per kWh")
    renewable_percentage: float = Field(ge=0, le=100)
    timestamp: datetime
    source: str


class EnergyMix(BaseModel):
    solar: float = 0
    wind: float = 0
    hydro: float = 0
    nuclear: float = 0
    gas: float = 0
    coal: float = 0
    other: float = 0
