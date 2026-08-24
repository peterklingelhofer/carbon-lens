"""Measure how much of the UK/EU intensity difference is accounting basis, not grid.

CarbonLens reports UK zones using NESO's published intensity, which is computed on a
DIRECT combustion basis (wind, solar, hydro, nuclear and pumped storage all score
0). Every fuel-mix zone is reported on an IPCC AR5 LIFECYCLE basis (wind 11, solar
48, nuclear 12). `/route` ranks these against each other as though they were the
same quantity.

This takes NESO's own live generation mix, recomputes it under this project's
lifecycle factors, and reports the gap. Any difference is pure methodology: same
grid, same instant, same mix, two accounting boundaries.

    uv run python scripts/validation/accounting_basis_gap.py

Needs no credentials; the NESO API is free and unauthenticated.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carbonlens.carbon_sources.emission_factors import calculate_carbon_intensity  # noqa: E402

NESO_BASE = "https://api.carbonintensity.org.uk"

# NESO fuel label -> our normalized fuel key. NESO's "imports" has no equivalent in
# a production-based table; it lands in the unsourced `other` bucket, which is
# itself a limitation worth seeing (NESO prices each interconnector separately).
NESO_FUEL_MAP = {
    "biomass": "biomass",
    "coal": "coal",
    "gas": "natural_gas",
    "nuclear": "nuclear",
    "hydro": "hydro",
    "solar": "solar",
    "wind": "wind",
    "imports": "other",
    "other": "other",
}


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{NESO_BASE}{path}", timeout=45) as fh:
        return json.load(fh)


def run() -> dict:
    generation = _get("/generation")["data"]
    intensity = _get("/intensity")["data"][0]

    published = intensity["intensity"]["actual"] or intensity["intensity"]["forecast"]

    mix: dict[str, float] = {}
    raw: dict[str, float] = {}
    for entry in generation["generationmix"]:
        pct = float(entry["perc"])
        raw[entry["fuel"]] = pct
        key = NESO_FUEL_MAP.get(entry["fuel"], "other")
        mix[key] = mix.get(key, 0.0) + pct

    lifecycle = calculate_carbon_intensity(mix)

    # How much of the gap is the unsourced `other` factor standing in for imports?
    # Recompute with imports at NESO's own per-interconnector figures as a bound.
    without_imports = {k: v for k, v in mix.items() if k != "other"}
    import_pct = mix.get("other", 0.0)
    non_import_total = sum(without_imports.values())
    sensitivity = {}
    if non_import_total > 0:
        base = calculate_carbon_intensity(without_imports) * non_import_total
        for label, factor in (
            ("our_other_assumption_300", 300),
            ("neso_french_interconnector_53", 53),
            ("neso_irish_interconnector_458", 458),
            ("neso_dutch_interconnector_474", 474),
        ):
            sensitivity[label] = round(
                (base + import_pct * factor) / (non_import_total + import_pct), 1
            )

    return {
        "sampled_at": datetime.now(UTC).isoformat(),
        "settlement_period": {"from": generation["from"], "to": generation["to"]},
        "neso_generation_mix_pct": raw,
        "neso_published_direct_gco2_kwh": published,
        "same_mix_on_our_lifecycle_basis_gco2_kwh": round(lifecycle, 1),
        "gap_gco2_kwh": round(lifecycle - published, 1),
        "gap_pct": round((lifecycle - published) / published * 100, 1) if published else None,
        "import_share_pct": import_pct,
        "lifecycle_under_different_import_factors": sensitivity,
        "note": (
            "The gap is methodology, not grid: same instant, same mix. A UK zone is "
            "therefore reported cleaner than an equivalently-dirty fuel-mix zone, and "
            "/route compares them directly. The sensitivity block bounds how much of "
            "the gap is attributable to the unsourced `other` factor standing in for "
            "NESO's separately-priced interconnector imports."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write the JSON result here")
    args = parser.parse_args()

    result = run()
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
