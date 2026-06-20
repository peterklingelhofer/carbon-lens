"""Carbon-aware Apache Airflow integration -- a *deferrable* sensor.

Put ``CarbonAwareSensor`` before a flexible task in a DAG and it succeeds only once
the grid is a good time to run. Because it's deferrable, it frees the worker slot
while waiting (the poll runs in the triggerer process), so it can wait hours for a
clean window without holding a slot -- the right way to make a DAG carbon-aware,
unlike a blocking call.

    from carbon_mesh.integrations.airflow import CarbonAwareSensor

    wait_for_clean = CarbonAwareSensor(
        task_id="wait_for_clean_grid",
        region="aws/us-east-1",      # or zone/FR for on-prem grids
        max_intensity=150,
        max_wait_hours=6,            # proceed anyway after this (deadline backstop)
    )
    wait_for_clean >> train_model

Apache Airflow is an optional dependency -- ``pip install apache-airflow``. The
module imports without it; only instantiating the sensor requires it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from carbon_mesh.integrations import _require
from carbon_mesh.sdk import DEFAULT_API_URL, is_good_time

try:
    from airflow.sensors.base import BaseSensorOperator
    from airflow.triggers.base import BaseTrigger, TriggerEvent

    _HAS_AIRFLOW = True
except ImportError:  # pragma: no cover - exercised only without Airflow installed
    BaseSensorOperator = object  # type: ignore[assignment,misc]
    BaseTrigger = object  # type: ignore[assignment,misc]
    TriggerEvent = None  # type: ignore[assignment,misc]
    _HAS_AIRFLOW = False


def _signal_url(api_url: str, region: str) -> str:
    """Signal URL for a provider/region or zone/<id> annotation."""
    provider, _, reg = region.partition("/")
    return f"{api_url.rstrip('/')}/api/v1/carbon/signal/{provider}/{reg}"


class CarbonCleanTrigger(BaseTrigger):
    """Async trigger that fires when ``region`` is a good time to run.

    Polls the CarbonLens signal from the triggerer until the grid is clean or
    ``max_wait_hours`` passes; fires either way (event ``reason`` is clean/deadline).
    """

    def __init__(
        self,
        region: str,
        api_url: str = DEFAULT_API_URL,
        max_wait_hours: float = 24.0,
        max_intensity: float | None = None,
        poll_seconds: float = 600.0,
    ) -> None:
        super().__init__()
        self.region = region
        self.api_url = api_url
        self.max_wait_hours = max_wait_hours
        self.max_intensity = max_intensity
        self.poll_seconds = poll_seconds

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return (
            "carbon_mesh.integrations.airflow.CarbonCleanTrigger",
            {
                "region": self.region,
                "api_url": self.api_url,
                "max_wait_hours": self.max_wait_hours,
                "max_intensity": self.max_intensity,
                "poll_seconds": self.poll_seconds,
            },
        )

    async def run(self) -> AsyncIterator[Any]:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.max_wait_hours * 3600
        url = _signal_url(self.api_url, self.region)
        async with httpx.AsyncClient(timeout=20) as client:
            while True:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    signal = resp.json()
                except httpx.HTTPError:
                    signal = {}
                if signal and is_good_time(signal, self.max_intensity):
                    yield TriggerEvent({"reason": "clean", "signal": signal})
                    return
                if loop.time() >= deadline:
                    yield TriggerEvent({"reason": "deadline", "signal": signal})
                    return
                await asyncio.sleep(self.poll_seconds)


class CarbonAwareSensor(BaseSensorOperator):
    """Deferrable sensor that succeeds once ``region`` is a good time to run.

    Frees the worker while waiting; proceeds when the grid is clean or the deadline
    is hit (so it never blocks a DAG forever). The downstream task then runs.
    """

    def __init__(
        self,
        *,
        region: str,
        api_url: str = DEFAULT_API_URL,
        max_wait_hours: float = 24.0,
        max_intensity: float | None = None,
        poll_seconds: float = 600.0,
        **kwargs: Any,
    ) -> None:
        _require(_HAS_AIRFLOW, "Airflow", "apache-airflow")
        super().__init__(**kwargs)
        self.region = region
        self.api_url = api_url
        self.max_wait_hours = max_wait_hours
        self.max_intensity = max_intensity
        self.poll_seconds = poll_seconds

    def execute(self, context: Any) -> None:
        self.defer(
            trigger=CarbonCleanTrigger(
                region=self.region,
                api_url=self.api_url,
                max_wait_hours=self.max_wait_hours,
                max_intensity=self.max_intensity,
                poll_seconds=self.poll_seconds,
            ),
            method_name="execute_complete",
        )

    def execute_complete(self, context: Any, event: dict | None = None) -> dict | None:
        # Clean or deadline -> let the DAG proceed; the event carries the reason.
        return event
