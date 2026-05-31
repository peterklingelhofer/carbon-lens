"""Verify the SlowAPI rate limiter is wired and actually enforces the default limit.

The suite disables the limiter by default (see conftest); this test re-enables it
locally to prove enforcement, then restores the disabled state.
"""

from fastapi.testclient import TestClient


def test_rate_limit_enforced(client: TestClient):
    from carbon_mesh.main import limiter

    limiter.enabled = True
    try:
        # Default limit is 100/minute — exceed it from a single client address
        statuses = [client.get("/health").status_code for _ in range(130)]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert 429 in statuses, "rate limiter did not return 429 after exceeding the default limit"
    assert statuses[0] == 200, "first request should succeed before the limit is reached"
