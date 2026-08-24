"""Backtest the merit-order marginal heuristic against WattTime's measured MOER.

STATUS: NOT RUN. This project holds no WattTime credentials, so docs/VALIDATION.md
reports this comparison as unrun rather than estimating it. The script is complete
and runnable by anyone who has a login.

    WATTTIME_USERNAME=... WATTTIME_PASSWORD=... \\
      uv run python scripts/validation/watttime_backtest.py --region CAISO_NORTH --hours 168

What it compares. CarbonLens estimates marginal intensity with a merit-order
heuristic: the emission factor of the most flexible fossil fuel currently running
(see emission_factors.calculate_marginal_intensity). WattTime publishes a measured
marginal operating emissions rate for the same grid. This pairs them hour by hour
and reports correlation, mean absolute error and bias.

Note on the handoff. The brief for this work asked for the estimator's "r²
confidence band", describing a regression estimator that emits r². That estimator
lives in the companion project carbon-aware-dispatcher, not here. CarbonLens's
marginal number is a merit-order lookup that emits no confidence signal at all,
which is itself a finding: there is no r² to gate the feature on, so if this
backtest shows poor agreement the remedy is to add a confidence signal, not to
threshold an existing one.

Because the heuristic takes one of a small set of fuel factors (490 for gas, 820
for coal, 650 for oil), expect it to be a step function against a continuous
measured signal. Rank correlation is therefore reported alongside Pearson.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carbonlens.carbon_sources.marginal import moer_to_gco2_kwh  # noqa: E402

LOGIN_URL = "https://api.watttime.org/login"
HISTORICAL_URL = "https://api.watttime.org/v3/historical"


def _get(url: str, token: str | None = None, params: dict | None = None, auth: str | None = None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if auth:
        request.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(request, timeout=60) as fh:
        return json.load(fh)


def login(username: str, password: str) -> str:
    import base64

    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    return _get(LOGIN_URL, auth=auth)["token"]


def fetch_moer(token: str, region: str, start: datetime, end: datetime) -> dict[datetime, float]:
    body = _get(
        HISTORICAL_URL,
        token=token,
        params={
            "region": region,
            "start": start.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "signal_type": "co2_moer",
        },
    )
    out: dict[datetime, float] = {}
    for point in body.get("data", []):
        ts = datetime.fromisoformat(str(point["point_time"]).replace("Z", "+00:00"))
        out[ts.replace(minute=0, second=0, microsecond=0)] = moer_to_gco2_kwh(float(point["value"]))
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs) ** 0.5 * sum((y - my) ** 2 for y in ys) ** 0.5
    return num / den if den else None


def spearman(xs: list[float], ys: list[float]) -> float | None:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        for rank, i in enumerate(order):
            out[i] = float(rank)
        return out

    return pearson(ranks(xs), ranks(ys))


def compare(measured: dict[datetime, float], estimated: dict[datetime, float]) -> dict:
    hours = sorted(set(measured) & set(estimated))
    if not hours:
        return {"paired_hours": 0, "note": "no overlapping hours"}
    m = [measured[h] for h in hours]
    e = [estimated[h] for h in hours]
    errors = [a - b for a, b in zip(e, m)]
    return {
        "paired_hours": len(hours),
        "measured_mean_gco2_kwh": round(statistics.mean(m), 1),
        "estimated_mean_gco2_kwh": round(statistics.mean(e), 1),
        "mean_absolute_error_gco2_kwh": round(statistics.mean(abs(x) for x in errors), 1),
        "bias_gco2_kwh": round(statistics.mean(errors), 1),
        "rmse_gco2_kwh": round((statistics.mean(x * x for x in errors)) ** 0.5, 1),
        "pearson_r": (lambda r: round(r, 3) if r is not None else None)(pearson(e, m)),
        "spearman_rho": (lambda r: round(r, 3) if r is not None else None)(spearman(e, m)),
        "distinct_estimated_values": sorted(set(e)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="CAISO_NORTH", help="WattTime region code")
    parser.add_argument("--hours", type=int, default=168, help="lookback window")
    parser.add_argument(
        "--estimates",
        help="JSON file of {iso8601_hour: heuristic_marginal_gco2_kwh} to compare against. "
        "Produce it by recording marginal_intensity_gco2_kwh from /api/v1/carbon over the "
        "same window; the heuristic needs a live fuel mix and cannot be reconstructed "
        "from the published archive, which stores only average intensity.",
    )
    parser.add_argument("--out", help="write the JSON result here")
    args = parser.parse_args()

    username = os.environ.get("WATTTIME_USERNAME", "")
    password = os.environ.get("WATTTIME_PASSWORD", "")
    if not username or not password:
        print(
            "WATTTIME_USERNAME / WATTTIME_PASSWORD not set.\n"
            "This is why docs/VALIDATION.md reports this backtest as NOT RUN: the "
            "comparison needs credentials this project does not have. Register free at "
            "https://watttime.org/ and rerun.",
            file=sys.stderr,
        )
        return 2

    if not args.estimates:
        print("--estimates is required; see --help for how to record it", file=sys.stderr)
        return 2

    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=args.hours)

    try:
        token = login(username, password)
        measured = fetch_moer(token, args.region, start, end)
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as exc:
        print(f"WattTime fetch failed: {exc}", file=sys.stderr)
        return 1

    with open(args.estimates) as fh:
        raw = json.load(fh)
    estimated = {
        datetime.fromisoformat(k).replace(minute=0, second=0, microsecond=0): float(v)
        for k, v in raw.items()
    }

    result = {
        "region": args.region,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "comparison": compare(measured, estimated),
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
