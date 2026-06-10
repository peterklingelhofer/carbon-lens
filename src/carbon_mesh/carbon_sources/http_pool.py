"""Shared httpx connection pool for all carbon data providers.

Reuses TCP connections and TLS sessions across providers that talk to
different hosts, reducing handshake overhead on repeated requests.
"""

import asyncio

import httpx

# ENTSO-E throttles bursts (HTTP 429) and occasionally 5xx/empties under load --
# which is why a snapshot run could fetch some zones and silently drop others.
# Cap how many ENTSO-E requests fly at once, and retry transient failures.
ENTSOE_SEMAPHORE = asyncio.Semaphore(6)


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: object = None,
    *,
    attempts: int = 3,
    base_delay: float = 0.6,
    semaphore: asyncio.Semaphore | None = None,
) -> httpx.Response:
    """GET with bounded retries on transient failures (timeouts, 429, 5xx).

    Retries with exponential backoff; raises the last error if all attempts
    fail. An optional semaphore caps concurrency against rate-limited hosts.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            if semaphore is not None:
                async with semaphore:
                    resp = await client.get(url, params=params)
            else:
                resp = await client.get(url, params=params)
            if resp.status_code == 429 or resp.status_code >= 500:
                resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                await asyncio.sleep(base_delay * (2**attempt))
    assert last_exc is not None
    raise last_exc


# Shared transport pool — reused across all carbon sources.
# Limits chosen for a single-process API that fans out to ~10 providers.
_transport = httpx.AsyncHTTPTransport(
    retries=1,
    limits=httpx.Limits(
        max_connections=30,
        max_keepalive_connections=15,
        keepalive_expiry=120,
    ),
)


def shared_client(
    *,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> httpx.AsyncClient:
    """Create an AsyncClient backed by the shared connection pool.

    Each caller gets its own client (with its own base_url / auth headers),
    but they all share the underlying TCP/TLS connections via ``_transport``.
    """
    return httpx.AsyncClient(
        transport=_transport,
        base_url=base_url,
        headers=headers or {},
        timeout=timeout,
    )
