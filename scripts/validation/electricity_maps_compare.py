"""Compare CarbonLens intensities against Electricity Maps for the same zones.

STATUS: NOT RUN. This project holds no Electricity Maps API key, so
docs/VALIDATION.md reports this comparison as unrun rather than estimating it. The
script is complete and runnable by anyone with a key.

    CARBON_LENS_ELECTRICITY_MAPS_API_KEY=... \\
      uv run python scripts/validation/electricity_maps_compare.py --zones FR DE NL PL

Two comparisons, and the second is the interesting one:

1. Production-based: our fuel-mix weighted average against Electricity Maps'
   `carbon-intensity/latest`. Any systematic gap here is a factor-table difference,
   because both sides are computing the same quantity from a similar mix. Their
   published defaults differ from this project's corpus in known ways (solar 45
   against our 48, battery discharge given world-average intensity rather than
   excluded), so a small gap is expected and a large one is a finding.

2. Consumption-based: our flow-traced number against their consumption intensity.
   This tests the flow tracer against an independent implementation of a comparable
   method. A gap here points at either the TRACED_ZONES cut being too small (we
   model a subnetwork; they model more of it) or at the factor table again, and the
   two can be told apart by whether the gap tracks a zone's import share.

Zones must be given as CarbonLens grid zones; the Electricity Maps zone key is
assumed identical unless --map is supplied.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carbonlens.carbon_sources.entsoe import ENTSOECarbonSource  # noqa: E402
from carbonlens.carbon_sources.flow_tracing import ConsumptionIntensitySource  # noqa: E402

EM_BASE = "https://api.electricitymap.org/v3"


def em_get(path: str, key: str, params: dict) -> dict | None:
    url = f"{EM_BASE}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"auth-token": key})
    try:
        with urllib.request.urlopen(request, timeout=45) as fh:
            return json.load(fh)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        print(f"  Electricity Maps {path} for {params.get('zone')}: {exc}", file=sys.stderr)
        return None


def _summary(rows: list[dict], field: str) -> dict:
    deltas = [r[field] for r in rows if r.get(field) is not None]
    if not deltas:
        return {"n": 0}
    return {
        "n": len(deltas),
        "mean_signed_delta_gco2_kwh": round(statistics.mean(deltas), 1),
        "mean_abs_delta_gco2_kwh": round(statistics.mean(abs(d) for d in deltas), 1),
        "max_abs_delta_gco2_kwh": round(max(abs(d) for d in deltas), 1),
    }


async def run(zones: list[str], em_key: str, entsoe_token: str, zone_map: dict[str, str]) -> dict:
    ours = await ENTSOECarbonSource(entsoe_token).get_carbon_intensity_batch(zones)
    traced = await ConsumptionIntensitySource(entsoe_token).compute() if entsoe_token else {}

    rows = []
    for zone in zones:
        mine = ours.get(zone)
        if mine is None:
            rows.append({"zone": zone, "note": "no CarbonLens reading"})
            continue
        em_zone = zone_map.get(zone, zone)
        prod = em_get("carbon-intensity/latest", em_key, {"zone": em_zone})
        cons = em_get(
            "carbon-intensity/latest", em_key, {"zone": em_zone, "emissionFactorType": "lifecycle"}
        )

        theirs_prod = (prod or {}).get("carbonIntensity")
        theirs_cons = (cons or {}).get("carbonIntensity")
        mine_cons = traced.get(zone)

        rows.append(
            {
                "zone": zone,
                "em_zone": em_zone,
                "ours_production_gco2_kwh": mine.carbon_intensity_gco2_kwh,
                "theirs_production_gco2_kwh": theirs_prod,
                "production_delta_gco2_kwh": (
                    round(mine.carbon_intensity_gco2_kwh - theirs_prod, 1)
                    if theirs_prod is not None
                    else None
                ),
                "ours_consumption_gco2_kwh": mine_cons,
                "theirs_consumption_gco2_kwh": theirs_cons,
                "consumption_delta_gco2_kwh": (
                    round(mine_cons - theirs_cons, 1)
                    if mine_cons is not None and theirs_cons is not None
                    else None
                ),
            }
        )

    return {
        "sampled_at": datetime.now(UTC).isoformat(),
        "production": _summary(rows, "production_delta_gco2_kwh"),
        "consumption": _summary(rows, "consumption_delta_gco2_kwh"),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zones", nargs="+", default=["FR", "DE", "NL", "PL", "ES", "BE"])
    parser.add_argument("--map", default="", help="ZONE:EM_ZONE,ZONE:EM_ZONE overrides")
    parser.add_argument("--out", help="write the JSON result here")
    args = parser.parse_args()

    em_key = os.environ.get("CARBON_LENS_ELECTRICITY_MAPS_API_KEY", "")
    if not em_key:
        print(
            "CARBON_LENS_ELECTRICITY_MAPS_API_KEY not set.\n"
            "This is why docs/VALIDATION.md reports this comparison as NOT RUN: it needs "
            "a commercial key this project does not have.",
            file=sys.stderr,
        )
        return 2

    entsoe_token = os.environ.get("CARBON_LENS_ENTSOE_TOKEN", "")
    if not entsoe_token:
        print(
            "CARBON_LENS_ENTSOE_TOKEN not set; needed for our side of the comparison",
            file=sys.stderr,
        )
        return 2

    zone_map = {}
    for pair in args.map.split(","):
        zone, sep, em = pair.partition(":")
        if sep:
            zone_map[zone.strip()] = em.strip()

    result = asyncio.run(run(args.zones, em_key, entsoe_token, zone_map))
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
