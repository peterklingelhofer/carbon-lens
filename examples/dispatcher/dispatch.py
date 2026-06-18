"""Minimal carbon-aware dispatcher -- the loosely-coupled pattern the companion
`carbon-aware-dispatcher` follows. Polls /carbon/signal and decides run vs wait,
honouring clean surplus and an optional intensity cap. Loop it as a sidecar/cron.

    uv run python examples/dispatcher/dispatch.py aws/us-east-1

Decoupling: this only depends on the stable /carbon/signal contract (guarded by
tests/test_signal_contract.py), not CarbonLens internals.
"""

from __future__ import annotations

import sys
import time

from carbon_mesh.sdk import CarbonClient, is_good_time


def decide(signal: dict, max_intensity: float | None = None) -> dict:
    """Return ``{action: 'run'|'wait', reason, wait_hours}`` from a signal."""
    if is_good_time(signal, max_intensity):
        reason = "clean surplus" if signal.get("clean_surplus") else "grid is clean enough"
        return {"action": "run", "reason": reason, "wait_hours": 0}
    wait = signal.get("surplus_window_in_hours") or signal.get("cleaner_window_in_hours")
    return {"action": "wait", "reason": "grid is dirty", "wait_hours": wait}


def run_loop(region: str, max_intensity: float | None = None, poll_seconds: float = 600) -> None:
    client = CarbonClient()
    while True:
        plan = decide(client.signal(region), max_intensity)
        if plan["action"] == "run":
            print(f"RUN ({plan['reason']})")
            return
        print(f"WAIT ({plan['reason']}; next window ~{plan['wait_hours']}h) — re-checking…")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    region = sys.argv[1] if len(sys.argv) > 1 else "aws/us-east-1"
    run_loop(region)
