"""Shared httpx connection pool for all carbon data providers.

Reuses TCP connections and TLS sessions across providers that talk to
different hosts, reducing handshake overhead on repeated requests.
"""

import httpx

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
