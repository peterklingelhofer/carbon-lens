"""Carbon-aware HTTP shedding/degradation middleware (Starlette / FastAPI).

For ALWAYS-ON services -- not deferrable batch -- carbon-awareness means doing *less
non-essential work* when the grid is dirty. This middleware:

- tags every response with ``X-Carbon-Mode: full|reduced`` (and ``X-Carbon-Intensity``)
  so the app/client can degrade gracefully (lower media quality, skip prefetch,
  defer analytics beacons), and
- optionally **sheds** requests the caller marked optional (``X-Carbon-Optional: 1``)
  with a 503 + ``Retry-After`` while the grid is dirty.

The grid signal is fetched once per ``refresh_seconds`` and cached, so per-request
overhead is nil. The SDK client is synchronous (``httpx.get``), so refreshes run in a
worker thread and never block the event loop: the very first request awaits the fetch
(nothing is cached yet), and every later refresh happens in the background while the
request serves the last good signal (stale-while-revalidate). Reuses ``carbon_mesh.sdk``
so the decision matches every other surface.

    from fastapi import FastAPI
    from carbon_mesh.middleware import CarbonAwareShedder

    app = FastAPI()
    app.add_middleware(CarbonAwareShedder, region="aws/us-east-1", max_intensity=300,
                       shed_optional=True)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from carbon_mesh.sdk import DEFAULT_API_URL, CarbonClient, is_good_time


def carbon_mode(signal: dict, max_intensity: float | None = None) -> str:
    """'full' when now is a good time to run, else 'reduced' (shed/degrade)."""
    return "full" if is_good_time(signal, max_intensity) else "reduced"


_TRUTHY = {"1", "true", "yes", "on"}


class CarbonAwareShedder(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        region: str,
        api_url: str = DEFAULT_API_URL,
        max_intensity: float | None = None,
        optional_header: str = "x-carbon-optional",
        refresh_seconds: float = 300.0,
        shed_optional: bool = False,
        client: object | None = None,
        _clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(app)
        self._region = region
        self._client = client or CarbonClient(api_url)
        self._max_intensity = max_intensity
        self._optional_header = optional_header
        self._refresh = refresh_seconds
        self._shed_optional = shed_optional
        self._clock = _clock
        self._signal: dict = {}
        self._fetched_at: float | None = None
        self._refreshing = False
        self._refresh_task: asyncio.Task | None = None

    def _is_stale(self) -> bool:
        return self._fetched_at is None or self._clock() - self._fetched_at >= self._refresh

    async def _fetch_signal(self) -> None:
        """Refresh the cached signal off the event loop (the SDK client blocks)."""
        try:
            self._signal = await asyncio.to_thread(
                self._client.signal,  # type: ignore[attr-defined]
                self._region,
            )
        except Exception:
            pass  # keep the last good signal; never fail a request over this
        finally:
            self._fetched_at = self._clock()
            self._refreshing = False

    async def _current_signal(self) -> dict:
        if self._is_stale() and not self._refreshing:
            self._refreshing = True
            if self._fetched_at is None:
                # Nothing cached yet -- await the first fetch (in a thread, so the
                # event loop keeps serving other requests during the round-trip).
                await self._fetch_signal()
            else:
                # We have a prior signal: revalidate in the background and serve
                # the stale value now, so no request ever waits on the network.
                self._refresh_task = asyncio.create_task(self._fetch_signal())
        return self._signal

    async def dispatch(self, request, call_next):
        signal = await self._current_signal()
        mode = carbon_mode(signal, self._max_intensity)

        if (
            self._shed_optional
            and mode == "reduced"
            and request.headers.get(self._optional_header, "").lower() in _TRUTHY
        ):
            resp = PlainTextResponse(
                "Deferred: the grid is dirty and this request was marked optional.",
                status_code=503,
            )
            resp.headers["X-Carbon-Mode"] = mode
            resp.headers["Retry-After"] = "600"
            return resp

        response = await call_next(request)
        response.headers["X-Carbon-Mode"] = mode
        intensity = signal.get("intensity_gco2_kwh")
        if intensity is not None:
            response.headers["X-Carbon-Intensity"] = str(intensity)
        return response
