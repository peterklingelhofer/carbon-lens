from datetime import datetime

from pydantic import BaseModel


class EmissionsRecord(BaseModel):
    request_id: str
    timestamp: datetime
    chosen_provider: str
    chosen_region: str
    chosen_grid_zone: str
    chosen_carbon_intensity: float
    worst_carbon_intensity: float
    carbon_saved_gco2_kwh: float
    chosen_renewable_pct: float = 0.0


class CarbonSavingsReport(BaseModel):
    total_requests: int
    total_carbon_saved_gco2_kwh: float
    avg_renewable_percentage: float
    records: list[EmissionsRecord]
