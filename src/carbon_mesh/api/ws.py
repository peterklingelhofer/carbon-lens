"""WebSocket endpoint for real-time carbon intensity streaming."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper, group_regions_by_zone

logger = logging.getLogger("carbon_mesh.ws")

ws_router = APIRouter()

# Default interval between broadcasts (seconds). Callers may override via the
# initial subscription message.
DEFAULT_INTERVAL_SECONDS = 60

# Popular regions used when the client does not specify a subscription list.
DEFAULT_REGIONS: list[dict[str, str]] = [
    {"provider": "aws", "region": "us-east-1"},
    {"provider": "aws", "region": "eu-west-1"},
    {"provider": "aws", "region": "us-west-2"},
    {"provider": "gcp", "region": "us-central1"},
    {"provider": "gcp", "region": "europe-west1"},
    {"provider": "azure", "region": "eastus"},
    {"provider": "azure", "region": "westeurope"},
]


class RegionSubscription(BaseModel):
    provider: str
    region: str


class SubscriptionMessage(BaseModel):
    regions: list[RegionSubscription] | None = None
    interval_seconds: int | None = None


async def _build_update(
    regions: list[dict[str, str]],
) -> dict[str, Any]:
    """Fetch intensities for all subscribed regions using batch fetching."""
    source = get_carbon_source()
    mapper = get_grid_mapper()

    # Map regions to grid zones, batch-fetch, then reassemble. Unknown regions are
    # silently skipped (the globe sends a fixed, valid list).
    zone_to_regions = group_regions_by_zone(mapper, regions)

    if not zone_to_regions:
        return {
            "type": "carbon_update",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": [],
        }

    try:
        intensities = await source.get_carbon_intensity_batch(list(zone_to_regions.keys()))
    except Exception:
        logger.warning("Batch fetch failed for WebSocket update", exc_info=True)
        intensities = {}

    data = []
    for zone, region_list in zone_to_regions.items():
        intensity = intensities.get(zone)
        if intensity is None:
            continue
        for r in region_list:
            data.append(
                {
                    "provider": r["provider"],
                    "region": r["region"],
                    **intensity.model_dump(mode="json"),
                }
            )

    return {
        "type": "carbon_update",
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }


@ws_router.websocket("/ws/carbon")
async def carbon_intensity_stream(websocket: WebSocket) -> None:
    """Stream real-time carbon intensity data over a WebSocket connection.

    Protocol
    --------
    1. Client connects to ``/ws/carbon``.
    2. (Optional) Client sends a JSON message to configure the subscription::

           {
               "regions": [
                   {"provider": "aws", "region": "us-east-1"},
                   {"provider": "gcp", "region": "europe-west1"}
               ],
               "interval_seconds": 30
           }

       If no message is received within 5 seconds the server falls back to
       ``DEFAULT_REGIONS`` and ``DEFAULT_INTERVAL_SECONDS``.
    3. The server pushes a ``carbon_update`` JSON message every *interval*
       seconds until the client disconnects.
    """
    await websocket.accept()
    logger.info("WebSocket client connected: %s", websocket.client)

    # --- Negotiate subscription ------------------------------------------------
    regions = [dict(r) for r in DEFAULT_REGIONS]
    interval = DEFAULT_INTERVAL_SECONDS

    try:
        # Give the client a short window to send subscription preferences.
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        try:
            msg = SubscriptionMessage.model_validate_json(raw)
            if msg.regions:
                regions = [r.model_dump() for r in msg.regions]
            if msg.interval_seconds and msg.interval_seconds > 0:
                interval = msg.interval_seconds
        except Exception:
            logger.warning("Invalid subscription message, using defaults")
    except (TimeoutError, WebSocketDisconnect):
        # No subscription message — proceed with defaults.
        pass

    logger.info(
        "Streaming %d region(s) every %ds to %s",
        len(regions),
        interval,
        websocket.client,
    )

    # --- Streaming loop --------------------------------------------------------
    shutdown_event: asyncio.Event | None = getattr(websocket.app.state, "shutdown_event", None)
    try:
        while True:
            # Exit cleanly if the server is shutting down
            if shutdown_event and shutdown_event.is_set():
                await websocket.close(code=1001, reason="Server shutting down")
                logger.info("WebSocket closed for shutdown: %s", websocket.client)
                return
            update = await _build_update(regions)
            await websocket.send_json(update)
            # Use wait_for so shutdown_event can interrupt the sleep
            if shutdown_event:
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
                    # Event fired — shut down
                    await websocket.close(code=1001, reason="Server shutting down")
                    logger.info("WebSocket closed for shutdown: %s", websocket.client)
                    return
                except TimeoutError:
                    pass  # Normal — interval elapsed, loop again
            else:
                await asyncio.sleep(interval)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: %s", websocket.client)
    except Exception:
        logger.exception("Unexpected error in WebSocket stream")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
