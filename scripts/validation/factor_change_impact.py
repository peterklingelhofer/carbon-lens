"""Quantify what the 2026-08-23 factor-corpus change did to reported intensities.

Phase 0 of the provenance work moved four things: coal 900 -> 820, gas 430 -> 490,
solar 41 -> 48, and storage from "factor 0, counted in the denominator" to "excluded
from the average". Each change is defended in data/emission-factors.json. This
measures the combined effect on real grids rather than asserting it is small.

Runs the live ENTSO-E fuel mix for the traced European zones and recomputes each
zone's intensity under both factor tables.

    CARBON_LENS_ENTSOE_TOKEN=... uv run python scripts/validation/factor_change_impact.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carbonlens.carbon_sources.entsoe import ENTSOE_ZONES, ENTSOECarbonSource  # noqa: E402

# The table carbon-lens shipped before 2026-08-23, including its treatment of
# storage as a zero-carbon generator inside the denominator.
OLD_FACTORS = {
    "coal": 900,
    "natural_gas": 430,
    "oil": 650,
    "petroleum": 650,
    "nuclear": 12,
    "hydro": 24,
    "wind": 11,
    "solar": 41,
    "geothermal": 38,
    "biomass": 230,
    "battery": 0,
    "other": 300,
}


def old_intensity(mix: dict[str, float]) -> float | None:
    """Reproduce the pre-change calculation exactly, storage included at 0."""
    total = sum(mw for mw in mix.values() if mw > 0)
    if total <= 0:
        return None
    weighted = sum(
        mw * OLD_FACTORS.get(fuel, OLD_FACTORS["other"]) for fuel, mw in mix.items() if mw > 0
    )
    return weighted / total


async def run(token: str, zones: list[str]) -> dict:
    readings = await ENTSOECarbonSource(token).get_carbon_intensity_batch(zones)

    rows = []
    for zone, reading in sorted(readings.items()):
        mix = reading.power_breakdown_mw or {}
        before = old_intensity(mix)
        if before is None or before <= 0:
            continue
        after = reading.carbon_intensity_gco2_kwh
        rows.append(
            {
                "zone": zone,
                "before_gco2_kwh": round(before, 1),
                "after_gco2_kwh": round(after, 1),
                "delta_gco2_kwh": round(after - before, 1),
                "delta_pct": round((after - before) / before * 100, 1),
                "coal_share_pct": round(
                    100 * mix.get("coal", 0) / max(sum(v for v in mix.values() if v > 0), 1), 1
                ),
                "gas_share_pct": round(
                    100 * mix.get("natural_gas", 0) / max(sum(v for v in mix.values() if v > 0), 1),
                    1,
                ),
            }
        )

    rows.sort(key=lambda r: -abs(r["delta_pct"]))
    deltas = [r["delta_pct"] for r in rows]
    return {
        "sampled_at": datetime.now(UTC).isoformat(),
        "zones": len(rows),
        "mean_signed_delta_pct": round(statistics.mean(deltas), 1) if deltas else None,
        "mean_abs_delta_pct": round(statistics.mean(abs(d) for d in deltas), 1) if deltas else None,
        "max_abs_delta_pct": round(max(abs(d) for d in deltas), 1) if deltas else None,
        "zones_moved_up": sum(1 for d in deltas if d > 0),
        "zones_moved_down": sum(1 for d in deltas if d < 0),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write the JSON result here")
    args = parser.parse_args()

    token = os.environ.get("CARBON_LENS_ENTSOE_TOKEN", "")
    if not token:
        print("CARBON_LENS_ENTSOE_TOKEN is not set; cannot run", file=sys.stderr)
        return 2

    result = asyncio.run(run(token, sorted(ENTSOE_ZONES)))
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
