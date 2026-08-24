"""Measure what the snapshot's carry-forward behaviour costs in accuracy.

When an upstream feed has a brief gap, the snapshot builder carries a zone's last
live reading forward rather than dropping the zone to an estimate. That is a design
decision the README states. This turns it into a measured error bar.

Method. In the published archive a carry-forward appears as consecutive samples with
an identical intensity AND renewable percentage. For each such run we take the
carried value, the next different value, and the elapsed time, and treat
|carried - next| as the error the carry had accumulated by the moment fresh data
arrived. That is an upper bound on the error during the run, above the mean error, and
it is the quantity a consumer of a stale reading actually cares about.

Two limits, both handled below:

* A repeated value is not proof of a carry-forward. A stable grid can
  report the same rounded number twice in a row. Series that never vary at all
  (fixed heuristics and mock fixtures) are excluded outright, and the report says
  what fraction of runs are short enough to be plausibly coincidental.
* The archive samples irregularly (roughly every 30-90 minutes), so gap durations
  are resolved only to the sampling interval.

    uv run python scripts/validation/carry_forward_error.py \\
        --archive https://raw.githubusercontent.com/peterklingelhofer/carbon-lens/data/history.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import urllib.request
from datetime import datetime

ARCHIVE_URL = "https://raw.githubusercontent.com/peterklingelhofer/carbon-lens/data/history.json"


def load(source: str) -> dict:
    if source.startswith("http"):
        with urllib.request.urlopen(source, timeout=120) as fh:
            return json.load(fh)
    with open(source) as fh:
        return json.load(fh)


def _ts(point: dict) -> datetime:
    return datetime.fromisoformat(point["t"])


def analyse(series: dict[str, list[dict]]) -> dict:
    runs: list[dict] = []
    constant_series: list[str] = []
    varying = 0
    total_points = 0
    carried_points = 0

    for key, points in series.items():
        points = [p for p in points if p.get("c") is not None]
        if len(points) < 3:
            continue
        total_points += len(points)
        values = {(p["c"], p.get("r")) for p in points}
        if len(values) == 1:
            # A fixed heuristic or a mock fixture: every point is identical by
            # construction, so it says nothing about carry-forward.
            constant_series.append(key)
            continue
        varying += 1

        i = 0
        while i < len(points):
            j = i
            while (
                j + 1 < len(points)
                and points[j + 1]["c"] == points[i]["c"]
                and points[j + 1].get("r") == points[i].get("r")
            ):
                j += 1
            repeats = j - i  # number of samples that merely repeated the first
            if repeats >= 1 and j + 1 < len(points):
                carried_points += repeats
                fresh = points[j + 1]
                held_hours = (_ts(points[j]) - _ts(points[i])).total_seconds() / 3600
                to_fresh_hours = (_ts(fresh) - _ts(points[i])).total_seconds() / 3600
                runs.append(
                    {
                        "series": key,
                        "repeats": repeats,
                        "held_hours": round(held_hours, 2),
                        "hours_to_fresh": round(to_fresh_hours, 2),
                        "carried_gco2_kwh": points[i]["c"],
                        "fresh_gco2_kwh": fresh["c"],
                        "abs_error_gco2_kwh": round(abs(fresh["c"] - points[i]["c"]), 1),
                        "signed_error_gco2_kwh": round(fresh["c"] - points[i]["c"], 1),
                        "rel_error_pct": (
                            round(abs(fresh["c"] - points[i]["c"]) / points[i]["c"] * 100, 1)
                            if points[i]["c"]
                            else None
                        ),
                    }
                )
            i = j + 1

    def bucket(lo: float, hi: float) -> dict | None:
        chosen = [r for r in runs if lo <= r["held_hours"] < hi]
        if not chosen:
            return None
        errors = [r["abs_error_gco2_kwh"] for r in chosen]
        signed = [r["signed_error_gco2_kwh"] for r in chosen]
        return {
            "held_hours_range": f"{lo}-{hi}",
            "n": len(chosen),
            "mean_abs_error_gco2_kwh": round(statistics.mean(errors), 1),
            "median_abs_error_gco2_kwh": round(statistics.median(errors), 1),
            "p90_abs_error_gco2_kwh": round(sorted(errors)[int(len(errors) * 0.9)], 1),
            "max_abs_error_gco2_kwh": round(max(errors), 1),
            "mean_signed_error_gco2_kwh": round(statistics.mean(signed), 1),
        }

    errors = [r["abs_error_gco2_kwh"] for r in runs]
    signed = [r["signed_error_gco2_kwh"] for r in runs]
    return {
        "series_examined": varying,
        "series_excluded_as_constant": len(constant_series),
        "excluded_series": sorted(constant_series),
        "total_points": total_points,
        "carried_points": carried_points,
        "carried_share_pct": (
            round(carried_points / total_points * 100, 1) if total_points else None
        ),
        "carry_runs": len(runs),
        "single_repeat_runs": sum(1 for r in runs if r["repeats"] == 1),
        "overall": {
            "mean_abs_error_gco2_kwh": round(statistics.mean(errors), 1) if errors else None,
            "median_abs_error_gco2_kwh": round(statistics.median(errors), 1) if errors else None,
            "p90_abs_error_gco2_kwh": (
                round(sorted(errors)[int(len(errors) * 0.9)], 1) if errors else None
            ),
            "max_abs_error_gco2_kwh": round(max(errors), 1) if errors else None,
            "mean_signed_error_gco2_kwh": round(statistics.mean(signed), 1) if signed else None,
        },
        "by_hold_duration": [
            b for b in (bucket(0, 2), bucket(2, 4), bucket(4, 8), bucket(8, 1e9)) if b
        ],
        "worst_runs": sorted(runs, key=lambda r: -r["abs_error_gco2_kwh"])[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", default=ARCHIVE_URL, help="URL or path to history.json")
    parser.add_argument("--out", help="write the JSON result here as well as to stdout")
    args = parser.parse_args()

    doc = load(args.archive)
    result = analyse(doc["series"])
    result["archive_generated_at"] = doc.get("generated_at")
    result["archive"] = args.archive

    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
