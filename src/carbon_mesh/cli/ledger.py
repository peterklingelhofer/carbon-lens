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


def read_file(path: Path) -> list[dict]:
    """Read one ledger file's records (skipping any unparseable lines)."""
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def read() -> list[dict]:
    """Read this host's local ledger records."""
    return read_file(LEDGER_FILE)


def _within(ts: str | None, cutoff: float) -> bool:
    """Whether an entry's timestamp is within the window (undated entries kept)."""
    try:
        t = datetime.fromisoformat(ts).timestamp() if ts else None
    except (TypeError, ValueError):
        t = None
    return t is None or t >= cutoff


def verdict(ratio: float) -> str:
    """Plain-English read of a calibration ratio (actual/predicted)."""
    return (
        "well-calibrated"
        if 0.85 <= ratio <= 1.15
        else ("over-promised" if ratio < 0.85 else "under-promised")
    )


def fleet_summary(entries: list[dict], now: datetime, days: int, top: int = 20) -> dict:
    """Org-level rollup across many hosts' ledgers, broken down by region.

    Same honest rules as ``summarize``: real kg avoided only from runs that supplied
    energy; run-now jobs avoid nothing. Concatenate each host's ``read_file`` output
    and pass it here for a fleet view.
    """
    cutoff = now.timestamp() - days * 86_400
    recent = [e for e in entries if _within(e.get("ts"), cutoff)]

    by_region: dict[str, dict] = {}
    total_kg = 0.0
    measured = 0
    shifted_total = 0
    energy_jobs = 0
    for e in recent:
        region = e.get("region", "?")
        row = by_region.setdefault(
            region, {"region": region, "jobs": 0, "shifted": 0, "kg_avoided": 0.0, "_reds": []}
        )
        row["jobs"] += 1
        if (e.get("deferred_hours") or 0) > 0:
            row["shifted"] += 1
            shifted_total += 1
            red = e.get("reduction_gco2_kwh", 0.0) or 0.0
            row["_reds"].append(red)
            if e.get("basis") == "measured":
                measured += 1
            if e.get("energy_kwh"):
                energy_jobs += 1
                kg = red * e["energy_kwh"] / 1000
                row["kg_avoided"] += kg
                total_kg += kg

    regions = []
    for row in by_region.values():
        reds = row.pop("_reds")
        row["avg_reduction_gco2_kwh"] = round(sum(reds) / len(reds), 1) if reds else 0.0
        row["kg_avoided"] = round(row["kg_avoided"], 2)
        regions.append(row)
    regions.sort(key=lambda r: r["kg_avoided"], reverse=True)

    return {
        "jobs": len(recent),
        "shifted": shifted_total,
        "measured": measured,
        "jobs_with_energy": energy_jobs,
        "total_kg_avoided": round(total_kg, 2),
        "regions": regions[:top],
        "days": days,
    }


def adjusted_prediction(predicted: float, ratio: float) -> float:
    """A submit-time prediction nudged by the rolling calibration ratio (actual/predicted).

    Self-correcting: if past forecasts ran 10% high (ratio 0.9), a fresh prediction is
    scaled down 10%. The raw prediction is still recorded separately, so this never
    feeds back into the calibration that produced ``ratio``.
    """
    return round(predicted * ratio, 1)


def calibration(entries: list[dict], now: datetime, days: int) -> dict:
    """How well submit-time forecasts predicted the run-time actual reduction.

    Honest scope: only shifted jobs whose reduction was re-measured at execution
    (``basis == "measured"``) and that recorded a submit-time prediction -- those are
    the only entries where predicted and actual are both real. ``calibration_ratio`` is
    actual / predicted: >1 means the forecast under-promised, <1 means it over-promised.
    With no qualifying samples, every figure is 0 and ``samples`` is 0.
    """
    cutoff = now.timestamp() - days * 86_400
    pairs: list[tuple[float, float]] = []
    for e in entries:
        if not _within(e.get("ts"), cutoff):
            continue
        if (e.get("deferred_hours") or 0) <= 0 or e.get("basis") != "measured":
            continue
        if "predicted_reduction_gco2_kwh" not in e:
            continue
        predicted = e.get("predicted_reduction_gco2_kwh") or 0.0
        actual = e.get("reduction_gco2_kwh") or 0.0
        pairs.append((predicted, actual))

    if not pairs:
        return {
            "samples": 0,
            "mean_predicted_gco2_kwh": 0.0,
            "mean_actual_gco2_kwh": 0.0,
            "calibration_ratio": 0.0,
            "mean_abs_error_gco2_kwh": 0.0,
            "days": days,
        }

    n = len(pairs)
    pred_sum = sum(p for p, _ in pairs)
    act_sum = sum(a for _, a in pairs)
    mae = sum(abs(a - p) for p, a in pairs) / n
    ratio = round(act_sum / pred_sum, 2) if pred_sum else 0.0
    return {
        "samples": n,
        "mean_predicted_gco2_kwh": round(pred_sum / n, 1),
        "mean_actual_gco2_kwh": round(act_sum / n, 1),
        "calibration_ratio": ratio,
        "mean_abs_error_gco2_kwh": round(mae, 1),
        "days": days,
    }


def calibration_by_region(entries: list[dict], now: datetime, days: int) -> dict[str, dict]:
    """Per-region forecast calibration -- grids differ in how forecastable they are.

    Returns ``{region: <calibration block>}`` for each region that has at least one
    qualifying (re-measured, shifted, predicted) run, so the self-correcting forecast can
    use the relevant grid's own track record instead of a fleet-wide average.
    """
    by_region: dict[str, list[dict]] = {}
    for e in entries:
        by_region.setdefault(e.get("region", "?"), []).append(e)
    out: dict[str, dict] = {}
    for region, group in by_region.items():
        cal = calibration(group, now, days)
        if cal["samples"] > 0:
            out[region] = cal
    return out


def org_statement(
    entries: list[dict], now: datetime, days: int, org_name: str = "Your organization"
) -> dict:
    """A methodology-stated, org-level carbon-aware-compute statement for disclosure.

    Builds on ``fleet_summary`` and adds the explicit counterfactual and accounting
    basis, plus the share of savings that were verified (re-measured at run time)
    rather than forecast -- so a sustainability team can cite it honestly.
    """
    s = fleet_summary(entries, now, days)
    verified_share = round(s["measured"] / s["shifted"] * 100, 1) if s["shifted"] else 0.0
    return {
        "org": org_name,
        "period_days": days,
        "jobs": s["jobs"],
        "shifted": s["shifted"],
        "verified_share_pct": verified_share,
        "jobs_with_energy": s["jobs_with_energy"],
        "total_kg_avoided": s["total_kg_avoided"],
        "forecast_calibration": calibration(entries, now, days),
        "regions": s["regions"],
        "counterfactual": (
            "running each job at the moment it was submitted (i.e. without carbon-aware deferral)"
        ),
        "accounting": (
            "Location-based. CO2 avoided is summed only for jobs that supplied energy (kWh); "
            "intensity reductions alone aren't additive. Verified jobs re-measured the grid at "
            "execution time; the rest are forecast estimates. An estimate, not an assured "
            "third-party attestation."
        ),
    }


def disclosure_markdown(stmt: dict) -> str:
    """Render an org-statement dict as a self-contained, citable Markdown disclosure.

    Combines the headline numbers, the stated counterfactual/accounting basis, the
    per-region breakdown, and -- crucially -- the forecast accuracy, so a reader can
    judge not just how much was avoided but how trustworthy the estimate is.
    """
    lines = [f"# Carbon-aware compute statement — {stmt['org']}", ""]
    lines.append(f"**Period:** last {stmt['period_days']} days")
    lines.append("")
    lines.append(f"- Jobs run: {stmt['jobs']}")
    lines.append(
        f"- Shifted to cleaner windows: {stmt['shifted']} "
        f"({stmt['verified_share_pct']}% verified at run time)"
    )
    lines.append(
        f"- CO2 avoided: ~{stmt['total_kg_avoided']} kg "
        f"(from {stmt['jobs_with_energy']} jobs with measured energy)"
    )
    cal = stmt.get("forecast_calibration") or {}
    if cal.get("samples"):
        ratio = cal["calibration_ratio"]
        lines.append(
            f"- Forecast accuracy: ratio {ratio} ({verdict(ratio)}); predicted "
            f"{round(cal['mean_predicted_gco2_kwh'])} vs actual "
            f"{round(cal['mean_actual_gco2_kwh'])} gCO2/kWh across {cal['samples']} verified runs"
        )
    lines.append("")
    if stmt.get("regions"):
        lines += [
            "## By region",
            "",
            "| Region | Jobs | Shifted | kg avoided |",
            "| --- | ---: | ---: | ---: |",
        ]
        for r in stmt["regions"]:
            lines.append(
                f"| {r['region']} | {r['jobs']} | {r['shifted']} | {r['kg_avoided']:.1f} |"
            )
        lines.append("")
    lines.append(f"**Counterfactual:** {stmt['counterfactual']}")
    lines.append("")
    lines.append(f"**Accounting:** {stmt['accounting']}")
    lines.append("")
    return "\n".join(lines)


def summarize(entries: list[dict], now: datetime, days: int) -> dict:
    """Aggregate ledger entries from the last ``days`` into an honest summary.

    The counterfactual is 'running at the moment you invoked', so a run-now job
    avoids nothing by definition. Real grams avoided are summed ONLY for runs that
    supplied job energy (kWh) -- per-kWh intensity reductions aren't additive
    without it. Everything else is reported as an average rate, not a fake total.
    """
    cutoff = now.timestamp() - days * 86_400
    recent = [e for e in entries if _within(e.get("ts"), cutoff)]

    shifted = [e for e in recent if (e.get("deferred_hours") or 0) > 0]
    reductions = [e.get("reduction_gco2_kwh", 0.0) or 0.0 for e in shifted]
    avg_reduction = round(sum(reductions) / len(reductions), 1) if reductions else 0.0

    with_energy = [e for e in shifted if e.get("energy_kwh")]
    grams = sum(
        (e.get("reduction_gco2_kwh", 0.0) or 0.0) * (e.get("energy_kwh") or 0.0)
        for e in with_energy
    )
    # How many shifted jobs have a verified (re-measured at run time) reduction
    # rather than a forecast estimate.
    measured = sum(1 for e in shifted if e.get("basis") == "measured")

    return {
        "jobs": len(recent),
        "shifted": len(shifted),
        "measured": measured,
        "jobs_with_energy": len(with_energy),
        "avg_reduction_gco2_kwh": avg_reduction,
        "grams_avoided": round(grams, 1),
        "kg_avoided": round(grams / 1000, 2),
        "days": days,
    }
