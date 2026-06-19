"""Build the public 'state of clean compute' report and write it as JSON.

Reads the rolling history archive and the snapshot (for region metadata), and
writes a compact report: most-shiftable grids and greenest regions. Run in CI
after the snapshot, and published to the data branch alongside it.

    uv run python scripts/build_clean_compute_report.py \
        --history history.json --snapshot snapshot.json --out clean_compute_report.json
"""

import argparse
import json
import urllib.request
from datetime import datetime, timezone

from carbon_mesh.engine.clean_compute import (
    build_clean_compute_report,
    update_clean_compute_history,
)


def _load(path_or_url: str) -> dict:
    if path_or_url.startswith(("http://", "https://")):
        with urllib.request.urlopen(path_or_url, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read())
    with open(path_or_url) as f:
        return json.load(f)


def _region_meta(snapshot: dict) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    for r in snapshot.get("regions", []):
        key = f"{r['provider']}/{r['region']}"
        meta[key] = {"grid_zone": r.get("grid_zone", ""), "location": r.get("location", "")}
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the state-of-clean-compute report")
    parser.add_argument("--history", default="history.json", help="History archive (path or URL)")
    parser.add_argument(
        "--snapshot", default="snapshot.json", help="Snapshot (for region metadata)"
    )
    parser.add_argument("--out", default="clean_compute_report.json", help="Output path")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument(
        "--calibration",
        default="",
        help="Optional forecast-calibration JSON (path or URL) from `carbonlens calibration "
        "--json` or /accounting/org-statement; included only when it has samples",
    )
    parser.add_argument(
        "--history-out",
        default="clean_compute_history.json",
        help="Rolling daily-summary output for the trend chart; '' to skip",
    )
    parser.add_argument(
        "--history-baseline",
        default="https://raw.githubusercontent.com/peterklingelhofer/carbonlens/data/clean_compute_history.json",
        help="Previous report-history (URL or path) to append to; '' to disable",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    history = _load(args.history)
    snapshot = _load(args.snapshot)

    calibration: dict | None = None
    if args.calibration:
        try:
            loaded = _load(args.calibration)
            # Accept either a bare calibration block or an org-statement wrapping one.
            calibration = loaded.get("forecast_calibration", loaded)
        except Exception:
            calibration = None

    report = build_clean_compute_report(
        history, _region_meta(snapshot), now, days=args.days, calibration=calibration
    )

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print(
        f"Wrote {args.out}: {len(report['most_shiftable'])} shiftable grids, "
        f"{len(report['greenest_regions'])} regions"
    )

    # Maintain the rolling daily-summary history for the trend chart (one point/day).
    if args.history_out:
        baseline: dict = {}
        if args.history_baseline:
            try:
                baseline = _load(args.history_baseline)
            except Exception:
                baseline = {}
        updated = update_clean_compute_history(baseline, report, now.date().isoformat())
        with open(args.history_out, "w") as f:
            json.dump(updated, f, indent=2)
        print(f"Wrote {args.history_out}: {len(updated['days'])} day(s) of trend")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
