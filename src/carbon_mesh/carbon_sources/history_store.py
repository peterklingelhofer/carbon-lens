"""Reader for the rolling carbon-intensity history archive.

The snapshot builder accumulates a ``history.json`` (per-region time series) and
publishes it alongside the snapshot. This loads that archive once and caches it,
the same fixed-quota pattern as the snapshot: viewer traffic never hits upstream.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import httpx

_CACHE_TTL_SECONDS = 300.0


def _parse_ts(value: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


class HistoryStore:
    """Loads the published history archive (URL or file path) and serves a single
    region's series. ``data`` can be injected directly (tests) to skip any I/O."""

    def __init__(self, source: str, data: dict | None = None) -> None:
        self._source = source
        self._data = data
        self._cache: dict | None = None
        self._fetched_at = 0.0

    async def _load(self) -> dict:
        if self._data is not None:
            return self._data
        if not self._source:
            return {}
        now = time.monotonic()
        if self._cache is not None and now - self._fetched_at < _CACHE_TTL_SECONDS:
            return self._cache
        try:
            if self._source.startswith(("http://", "https://")):
                async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                    resp = await client.get(self._source)
                    resp.raise_for_status()
                    data = resp.json()
            else:
                with open(self._source) as f:
                    data = json.load(f)
        except Exception:
            # Archive missing/unreachable -- history is best-effort, never fatal.
            data = {}
        self._cache = data
        self._fetched_at = now
        return data

    async def series_for(self, region_key: str, since: datetime) -> list[dict]:
        """Return ``[{"t","c","r"}, ...]`` for a ``provider/region`` key, oldest
        first, dropping points older than ``since``."""
        data = await self._load()
        points = data.get("series", {}).get(region_key, [])
        out: list[dict] = []
        for p in points:
            ts = _parse_ts(p.get("t", ""))
            if ts is not None and ts >= since:
                out.append(p)
        return out
