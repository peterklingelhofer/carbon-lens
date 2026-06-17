"""Local impact ledger for `carbonlens run` -- an honest, on-disk record of what
each carbon-aware run did and roughly how much it avoided. No server, no account:
one JSON line per run under the CLI config dir. The pure ``summarize`` is kept
separate from I/O so it's unit-testable without touching the disk or the clock.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from carbon_mesh.cli.client import CONFIG_DIR

LEDGER_FILE: Path = CONFIG_DIR / "ledger.jsonl"


def append(entry: dict) -> None:
    """Append one run record as a JSON line."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def read() -> list[dict]:
    """Read all ledger records (skipping any unparseable lines)."""
    if not LEDGER_FILE.exists():
        return []
    out: list[dict] = []
    for line in LEDGER_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def summarize(entries: list[dict], now: datetime, days: int) -> dict:
    """Aggregate ledger entries from the last ``days`` into an honest summary.

    The counterfactual is 'running at the moment you invoked', so a run-now job
    avoids nothing by definition. Real grams avoided are summed ONLY for runs that
    supplied job energy (kWh) -- per-kWh intensity reductions aren't additive
    without it. Everything else is reported as an average rate, not a fake total.
    """
    cutoff = now.timestamp() - days * 86_400
    recent: list[dict] = []
    for e in entries:
        ts = e.get("ts")
        try:
            t = datetime.fromisoformat(ts).timestamp() if ts else None
        except (TypeError, ValueError):
            t = None
        if t is None or t >= cutoff:
            recent.append(e)

    shifted = [e for e in recent if (e.get("deferred_hours") or 0) > 0]
    reductions = [e.get("reduction_gco2_kwh", 0.0) or 0.0 for e in shifted]
    avg_reduction = round(sum(reductions) / len(reductions), 1) if reductions else 0.0

    with_energy = [e for e in shifted if e.get("energy_kwh")]
    grams = sum(
        (e.get("reduction_gco2_kwh", 0.0) or 0.0) * (e.get("energy_kwh") or 0.0)
        for e in with_energy
    )

    return {
        "jobs": len(recent),
        "shifted": len(shifted),
        "jobs_with_energy": len(with_energy),
        "avg_reduction_gco2_kwh": avg_reduction,
        "grams_avoided": round(grams, 1),
        "kg_avoided": round(grams / 1000, 2),
        "days": days,
    }
