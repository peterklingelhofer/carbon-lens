import json
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    model_config = {"env_prefix": "CARBON_LENS_"}

    # API keys for carbon data providers
    eia_api_key: str = ""
    grid_status_api_key: str = ""
    electricity_maps_api_key: str = ""
    entsoe_token: str = ""

    # Carbon source mode: "hybrid" (recommended), "mock", "eia", "gridstatus", "electricity_maps"
    carbon_source: str = "hybrid"
    cache_ttl_seconds: int = 300

    region_map_path: Path = (
        Path(__file__).resolve().parent.parent.parent / "data" / "region_grid_map.yaml"
    )

    host: str = "0.0.0.0"
    port: int = 8000

    # CORS — accepts a JSON array (`["https://a","https://b"]`), a comma-separated
    # list (`https://a,https://b`), or a single bare origin (`https://a`).
    # NoDecode skips pydantic-settings' built-in JSON parsing so the validator
    # below can handle all three forms (a bare URL is not valid JSON).
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                return json.loads(s)
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    # Database
    use_database: bool = False
    database_url: str = "postgresql+asyncpg://carbon_mesh:carbon_mesh@localhost:5432/carbon_mesh"

    # Auth — fail closed by default; set CARBON_LENS_API_KEY_REQUIRED=false for the open public demo
    api_key_required: bool = True
    admin_secret: str = ""

    # Rate limiting
    rate_limit_default: str = "100/minute"
    rate_limit_route: str = "30/minute"

    # Logging
    log_format: str = "text"  # "text" or "json"
    log_level: str = "INFO"

    # Startup
    auto_migrate: bool = False  # Run alembic upgrade head on startup

    # Request limits
    max_request_body_bytes: int = 1_048_576  # 1 MB

    @property
    def configured_providers(self) -> dict[str, bool]:
        """Return which data providers have credentials configured."""
        return {
            "EIA (US grid)": bool(self.eia_api_key),
            "GridStatus (US ISOs)": bool(self.grid_status_api_key),
            "ENTSO-E (Europe)": bool(self.entsoe_token),
            "Electricity Maps (global)": bool(self.electricity_maps_api_key),
            "UK Carbon Intensity": True,  # No key needed
            "AEMO (Australia)": True,  # No key needed
            "Grid India": True,  # Heuristic, no key
            "ONS Brazil": True,  # Heuristic, no key
            "Eskom (South Africa)": True,  # Heuristic, no key
            "Open-Meteo (weather)": True,  # Free, no key
        }

    @property
    def normalized_database_url(self) -> str:
        """Normalize database URL for asyncpg (handles Render/Railway postgres:// URLs)."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
