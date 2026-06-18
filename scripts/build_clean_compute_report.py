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

from carbon_mesh.engine.clean_compute import build_clean_compute_report


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
    args = parser.parse_args()

    history = _load(args.history)
    snapshot = _load(args.snapshot)
    report = build_clean_compute_report(
        history, _region_meta(snapshot), datetime.now(timezone.utc), days=args.days
    )

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print(
        f"Wrote {args.out}: {len(report['most_shiftable'])} shiftable grids, "
        f"{len(report['greenest_regions'])} regions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
