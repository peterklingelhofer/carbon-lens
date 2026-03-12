from pydantic import BaseModel


class CloudRegion(BaseModel):
    provider: str
    region: str
    grid_zone: str
    location: str
    latitude: float
    longitude: float
    eia_respondent: str | None = None
    gridstatus_iso: str | None = None
