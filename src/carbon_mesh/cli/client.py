"""Thin HTTP client for the CarbonLens API."""

import json
from pathlib import Path

import httpx

CONFIG_DIR = Path.home() / ".carbon-mesh"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_api_url() -> str:
    return load_config().get("api_url", "http://localhost:8000")


def get_api_key() -> str | None:
    return load_config().get("api_key")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    key = get_api_key()
    if key:
        headers["X-API-Key"] = key
    return headers


def route(
    providers: list[str],
    residency: list[str] | None = None,
    carbon_weight: float = 1.0,
    cost_weight: float = 0.0,
) -> dict:
    body = {
        "constraints": {
            "providers": providers,
            "carbon_weight": carbon_weight,
            "cost_weight": cost_weight,
        }
    }
    if residency:
        body["constraints"]["data_residency"] = residency

    resp = httpx.post(
        f"{get_api_url()}/api/v1/route",
        json=body,
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def regions(provider: str | None = None) -> list[dict]:
    url = f"{get_api_url()}/api/v1/regions"
    if provider:
        url += f"?provider={provider}"
    resp = httpx.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def intensity(provider: str, region: str) -> dict:
    resp = httpx.get(
        f"{get_api_url()}/api/v1/carbon/{provider}/{region}",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def savings() -> dict:
    resp = httpx.get(
        f"{get_api_url()}/api/v1/accounting/savings",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def forecast(provider: str, region: str, hours: int = 24) -> dict:
    resp = httpx.get(
        f"{get_api_url()}/api/v1/carbon/forecast/{provider}/{region}",
        params={"hours": hours},
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def report_impact(api_url: str, entry: dict) -> dict:
    """POST one run's impact to an org ledger API (the /accounting/impact endpoint)."""
    resp = httpx.post(
        f"{api_url.rstrip('/')}/api/v1/accounting/impact",
        json=entry,
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def siting(
    providers: str = "aws,gcp,azure",
    power_watts: float | None = None,
    days: int = 30,
    limit: int = 20,
) -> dict:
    params: dict = {"providers": providers, "days": days, "limit": limit}
    if power_watts is not None:
        params["power_watts"] = power_watts
    resp = httpx.get(
        f"{get_api_url()}/api/v1/carbon/siting", params=params, headers=_headers(), timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def shiftability(days: int = 14, limit: int = 25) -> dict:
    resp = httpx.get(
        f"{get_api_url()}/api/v1/carbon/shiftability",
        params={"days": days, "limit": limit},
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def best_time(provider: str, region: str, days: int = 14, energy_kwh: float | None = None) -> dict:
    params: dict = {"days": days}
    if energy_kwh is not None:
        params["energy_kwh"] = energy_kwh
    resp = httpx.get(
        f"{get_api_url()}/api/v1/carbon/best-time/{provider}/{region}",
        params=params,
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
