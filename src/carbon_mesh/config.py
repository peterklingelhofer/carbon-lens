from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CARBON_MESH_"}

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

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    use_database: bool = False
    database_url: str = "postgresql+asyncpg://carbon_mesh:carbon_mesh@localhost:5432/carbon_mesh"

    # Auth — fail closed by default; set CARBON_MESH_API_KEY_REQUIRED=false for the open public demo
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

    # Stripe (leave empty to disable billing integration)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""  # Stripe Price ID for Pro plan
    stripe_price_id_enterprise: str = ""  # Stripe Price ID for Enterprise plan

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
