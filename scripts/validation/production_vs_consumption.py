"""Measure the spread between production-based and consumption-based intensity.

Answers a question the flow-tracing feature has to justify: does accounting for
imports actually change the number enough to be worth the complexity, and for which
zones? Runs the live ENTSO-E production feed and the flow tracer over the same
instant, and reports the per-zone difference.

Needs a free ENTSO-E token:

    CARBON_LENS_ENTSOE_TOKEN=... uv run python scripts/validation/production_vs_consumption.py

Writes JSON to stdout, and to --out if given. Results are recorded in
docs/VALIDATION.md; rerunning will give different numbers, because it samples one
instant of a live grid.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carbonlens.carbon_sources.entsoe import (  # noqa: E402
    ENTSOE_ZONE_MAP,
    ENTSOECarbonSource,
)
from carbonlens.carbon_sources.flow_tracing import (  # noqa: E402
    BORDERS,
    TRACED_ZONES,
    ConsumptionIntensitySource,
)


async def _borders(source: ConsumptionIntensitySource, zones: set[str]) -> list[dict]:
    """Net flow on every border where both ends reported production.

    Captured so a zero delta can be told apart from a missing measurement: a zone
    with no evaluable border is not a zone with no imports.
    """
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start = (now - timedelta(hours=2)).strftime("%Y%m%d%H00")
    end = now.strftime("%Y%m%d%H00")

    out = []
    for a, b in BORDERS:
        if a not in zones or b not in zones:
            out.append({"a": a, "b": b, "evaluable": False, "net_b_to_a_mw": None})
            continue
        ea, eb = ENTSOE_ZONE_MAP[a], ENTSOE_ZONE_MAP[b]
        into_a = await source._flow(ea, eb, start, end)
        into_b = await source._flow(eb, ea, start, end)
        out.append({"a": a, "b": b, "evaluable": True, "net_b_to_a_mw": round(into_a - into_b, 1)})
    return out


def _classify(zone: str, delta_pct: float, borders: list[dict]) -> str:
    """Why this zone's delta looks the way it does.

    Distinguishes the three cases that otherwise all render as "0.0%".
    """
    evaluable = [b for b in borders if b["evaluable"] and zone in (b["a"], b["b"])]
    if not evaluable:
        return "no_evaluable_border"
    imports = 0.0
    for b in evaluable:
        net = b["net_b_to_a_mw"] or 0.0
        # net_b_to_a is positive when power flows b -> a.
        if b["a"] == zone and net > 0:
            imports += net
        elif b["b"] == zone and net < 0:
            imports += -net
    if imports <= 0:
        return "net_exporter_no_imports"
    return "importer" if abs(delta_pct) >= 5 else "importer_small_effect"


async def run(token: str) -> dict:
    production = await ENTSOECarbonSource(token).get_carbon_intensity_batch(TRACED_ZONES)
    tracer = ConsumptionIntensitySource(token)
    consumption = await tracer.compute()
    borders = await _borders(tracer, set(production))

    missing = sorted(set(TRACED_ZONES) - set(production))
    unevaluable = [f"{b['a']}-{b['b']}" for b in borders if not b["evaluable"]]

    rows = []
    for zone in sorted(set(production) & set(consumption)):
        prod = production[zone].carbon_intensity_gco2_kwh
        cons = consumption[zone]
        if prod <= 0:
            continue
        delta_pct = (cons - prod) / prod * 100
        rows.append(
            {
                "zone": zone,
                "production_gco2_kwh": round(prod, 1),
                "consumption_gco2_kwh": round(cons, 1),
                "delta_gco2_kwh": round(cons - prod, 1),
                "delta_pct": round(delta_pct, 1),
                "load_mw": production[zone].grid_load_mw,
                "interpretation": _classify(zone, delta_pct, borders),
            }
        )

    rows.sort(key=lambda r: abs(r["delta_pct"]), reverse=True)
    # Only zones whose imports were actually measurable say anything about whether
    # flow tracing matters. The rest only report a gap in the data.
    measured = [r for r in rows if r["interpretation"].startswith("importer")]
    deltas = [abs(r["delta_pct"]) for r in measured]
    return {
        "sampled_at": datetime.now(UTC).isoformat(),
        "traced_zones": TRACED_ZONES,
        "zones_with_no_production_data": missing,
        "unevaluable_borders": unevaluable,
        "zones_compared": len(rows),
        "zones_with_measurable_imports": len(measured),
        "mean_abs_delta_pct_importers": round(sum(deltas) / len(deltas), 1) if deltas else None,
        "max_abs_delta_pct_importers": round(max(deltas), 1) if deltas else None,
        "rows": rows,
        "borders": borders,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write the JSON result here as well as to stdout")
    args = parser.parse_args()

    token = os.environ.get("CARBON_LENS_ENTSOE_TOKEN", "")
    if not token:
        print("CARBON_LENS_ENTSOE_TOKEN is not set; cannot run", file=sys.stderr)
        return 2

    result = asyncio.run(run(token))
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
