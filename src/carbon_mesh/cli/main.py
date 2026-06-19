"""CarbonLens CLI — Find the greenest cloud region for your workload."""

import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from carbon_mesh.cli import client, energy, ledger
from carbon_mesh.cli.green_run import choose_run_index, choose_run_plan
from carbon_mesh.cli.plan import plan_estimate

app = typer.Typer(
    name="carbonlens",
    help="Carbon-aware multi-cloud routing CLI",
    no_args_is_help=True,
)
console = Console()
config_app = typer.Typer(help="Manage CLI configuration")
app.add_typer(config_app, name="config")


@app.command()
def route(
    providers: str = typer.Option(
        "aws,gcp,azure", "--providers", "-p", help="Comma-separated providers"
    ),
    residency: Optional[str] = typer.Option(
        None, "--residency", "-r", help="Data residency, e.g. EU, US"
    ),
    carbon_weight: float = typer.Option(
        1.0, "--carbon-weight", "-c", help="Carbon optimization weight (0-1)"
    ),
    cost_weight: float = typer.Option(0.0, "--cost-weight", help="Cost optimization weight (0-1)"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Find the greenest cloud region for your workload."""
    provider_list = [p.strip() for p in providers.split(",")]
    residency_list = [r.strip() for r in residency.split(",")] if residency else None

    try:
        data = client.route(provider_list, residency_list, carbon_weight, cost_weight)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(data))
        return

    rec = data["recommended"]
    console.print()
    console.print(f"[bold green]Recommended:[/bold green] {rec['provider']}/{rec['region']}")
    console.print(f"  Grid Zone:        {rec['grid_zone']}")
    console.print(f"  Carbon Intensity: {rec['carbon_intensity_gco2_kwh']} gCO2/kWh")
    console.print(f"  Renewable:        {rec['renewable_percentage']}%")
    console.print(
        f"  Carbon Savings:   {rec['carbon_savings_vs_worst_pct']:.1f}% greener than worst"
    )
    console.print()

    if data.get("alternatives"):
        table = Table(title=f"Alternatives ({len(data['alternatives'])} regions)")
        table.add_column("#", style="dim")
        table.add_column("Region")
        table.add_column("Grid Zone")
        table.add_column("gCO2/kWh", justify="right")
        table.add_column("Renewable", justify="right")
        table.add_column("Score", justify="right")

        for i, alt in enumerate(data["alternatives"][:10], start=2):
            color = (
                "green"
                if alt["carbon_intensity_gco2_kwh"] <= 50
                else ("yellow" if alt["carbon_intensity_gco2_kwh"] <= 200 else "red")
            )
            table.add_row(
                str(i),
                f"{alt['provider']}/{alt['region']}",
                alt["grid_zone"],
                f"[{color}]{alt['carbon_intensity_gco2_kwh']}[/{color}]",
                f"{alt['renewable_percentage']}%",
                f"{alt['score']:.3f}",
            )
        console.print(table)


@app.command()
def intensity(
    region: str = typer.Argument(help="Region in provider/region format, e.g. aws/us-east-1"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Get live carbon intensity for a cloud region."""
    parts = region.split("/", 1)
    if len(parts) != 2:
        console.print(
            "[red]Error:[/red] Region must be in format provider/region (e.g. aws/us-east-1)"
        )
        raise typer.Exit(1)

    try:
        data = client.intensity(parts[0], parts[1])
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(data))
        return

    color = (
        "green"
        if data["carbon_intensity_gco2_kwh"] <= 50
        else ("yellow" if data["carbon_intensity_gco2_kwh"] <= 200 else "red")
    )
    console.print()
    console.print(f"[bold]{region}[/bold]")
    console.print(f"  Grid Zone:        {data['grid_zone']}")
    console.print(
        f"  Carbon Intensity: [{color}]{data['carbon_intensity_gco2_kwh']} gCO2/kWh[/{color}]"
    )
    console.print(f"  Renewable:        {data['renewable_percentage']}%")
    console.print(f"  Source:           {data['source']}")
    console.print(f"  Timestamp:        {data['timestamp']}")
    console.print()


@app.command()
def regions(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """List all supported cloud regions."""
    try:
        data = client.regions(provider)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(data))
        return

    table = Table(title=f"Cloud Regions ({len(data)} total)")
    table.add_column("Provider", style="bold")
    table.add_column("Region")
    table.add_column("Grid Zone")
    table.add_column("Location")

    for r in data:
        table.add_row(r["provider"], r["region"], r["grid_zone"], r["location"])
    console.print(table)


@app.command()
def report(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """View carbon savings report."""
    try:
        data = client.savings()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(data))
        return

    console.print()
    console.print("[bold green]Carbon Savings Report[/bold green]")
    console.print(f"  Total Requests:   {data['total_requests']}")
    console.print(
        f"  Avg Intensity Cut: {data['avg_intensity_reduction_gco2_kwh']} gCO2/kWh "
        f"vs {data['baseline']}"
    )
    console.print(f"  Avg Renewable:    {data['avg_renewable_percentage']}%")

    if data.get("records"):
        console.print()
        table = Table(title=f"Recent Records ({len(data['records'])})")
        table.add_column("Request ID", style="dim", max_width=8)
        table.add_column("Region")
        table.add_column("Intensity", justify="right")
        table.add_column("Saved", justify="right", style="green")
        table.add_column("Time")

        for r in data["records"][:10]:
            table.add_row(
                r["request_id"][:8],
                f"{r['chosen_provider']}/{r['chosen_region']}",
                f"{r['chosen_carbon_intensity']}",
                f"{r['intensity_reduction_gco2_kwh']:.1f}",
                r["timestamp"][:19],
            )
        console.print(table)
    console.print()


@app.command()
def run(
    command: list[str] = typer.Argument(
        ..., help="Command to run when the grid is green, e.g. -- python train.py"
    ),
    region: str = typer.Option(
        ...,
        "--region",
        help="Target region provider/region (e.g. aws/us-east-1). Comma-separate several "
        "movable candidates to co-optimise region AND time, e.g. aws/us-west-2,gcp/europe-west1",
    ),
    max_intensity: Optional[float] = typer.Option(
        None,
        "--max-intensity",
        help="Run as soon as forecast intensity is at/under this (gCO2/kWh); "
        "omit to wait for the cleanest hour in the window",
    ),
    max_wait_hours: int = typer.Option(
        24, "--max-wait-hours", help="Most hours to defer before running anyway"
    ),
    energy_kwh: Optional[float] = typer.Option(
        None,
        "--energy-kwh",
        help="Job energy in kWh; enables a real grams-avoided estimate in `carbonlens impact`",
    ),
    measure_energy: bool = typer.Option(
        False,
        "--measure-energy",
        help="Measure the job's actual CPU-package energy via RAPL (Linux) instead of "
        "--energy-kwh; falls back to --energy-kwh where RAPL is unavailable",
    ),
    report_to: str | None = typer.Option(
        None,
        "--report-to",
        help="POST this run's impact to an org ledger API base URL (its /accounting/impact "
        "endpoint), so org-statement and the Prometheus gauges stay live without a manual gather",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan; don't wait or run"),
):
    """Run a command at the cleanest time (and, with several regions, the cleanest place)."""
    labels = [r.strip() for r in region.split(",") if r.strip()]
    fetched: dict[str, dict] = {}
    for lbl in labels:
        provider, _, reg = lbl.partition("/")
        if not provider or not reg:
            console.print(f"[red]Error:[/red] --region must be provider/region (got '{lbl}')")
            raise typer.Exit(1)
        try:
            fetched[lbl] = client.forecast(provider, reg, max_wait_hours)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    multi = len(labels) > 1
    if not multi:
        chosen_label = labels[0]
        forecast = fetched[chosen_label]
        intensities = [p["carbon_intensity_gco2_kwh"] for p in forecast.get("points", [])]
        if not intensities:
            console.print("[yellow]No forecast available; running now.[/yellow]")
            idx, reason = 0, "now"
        else:
            idx, reason = choose_run_index(
                intensities, max_intensity, max_wait_hours, forecast.get("clean_surplus_hours", [])
            )
    else:
        regions_data = [
            (
                lbl,
                [p["carbon_intensity_gco2_kwh"] for p in fetched[lbl].get("points", [])],
                fetched[lbl].get("clean_surplus_hours", []),
            )
            for lbl in labels
        ]
        chosen_label, idx, reason = choose_run_plan(regions_data, max_intensity, max_wait_hours)
        forecast = fetched[chosen_label]
        intensities = [p["carbon_intensity_gco2_kwh"] for p in forecast.get("points", [])]

    now_v = intensities[0] if intensities else None
    chosen_v = intensities[idx] if intensities else None
    where = f" in [bold]{chosen_label}[/bold]" if multi else ""

    if idx == 0:
        if reason == "surplus_now":
            console.print(
                f"[green]Clean surplus now[/green]{where} (~{now_v:.0f} gCO2/kWh, renewables "
                "abundant) — the highest-value time to run. Running immediately."
            )
        elif reason == "now_no_benefit" and now_v is not None:
            console.print(
                f"[green]Now is about as clean as it gets[/green]{where} (~{now_v:.0f} gCO2/kWh); "
                "waiting would save little, so running now (delay has its own cost)."
            )
        elif now_v is not None:
            console.print(
                f"[green]Grid is green now[/green]{where} (~{now_v:.0f} gCO2/kWh) — running now."
            )
    elif now_v is not None and chosen_v is not None:
        saved = (now_v - chosen_v) / now_v * 100 if now_v else 0.0
        when = forecast["points"][idx]["timestamp"][:16].replace("T", " ")
        note = {
            "surplus": "clean-surplus window (renewables abundant), the highest-value time to run",
            "cleanest_fallback": "no hour under the threshold in the window, picking the cleanest",
        }.get(reason, "cleanest upcoming hour")
        console.print(
            f"[cyan]Deferring {idx}h[/cyan] to {when} UTC{where} "
            f"(~{chosen_v:.0f} vs ~{now_v:.0f} gCO2/kWh now, {saved:.0f}% cleaner) — {note}."
        )

    if dry_run:
        console.print("[dim](dry run — not waiting or executing)[/dim]")
        return

    if idx > 0:
        console.print(f"Waiting {idx}h before running… (Ctrl-C to cancel)")
        time.sleep(idx * 3600)

    # Measured impact: re-read the ACTUAL intensity now, at execution time, and
    # compare to the real reading when we started (now_v). That's a verified avoided
    # intensity, not the forecast we used to pick the window. Fall back to the
    # forecast if the live read fails.
    run_v = now_v
    basis = "now" if idx == 0 else "forecast"
    if idx > 0:
        cprov, _, creg = chosen_label.partition("/")
        try:
            run_v = client.intensity(cprov, creg)["carbon_intensity_gco2_kwh"]
            basis = "measured"
        except Exception:
            run_v = chosen_v
    have_shift = idx > 0 and now_v is not None
    predicted = max(0.0, now_v - chosen_v) if (have_shift and chosen_v is not None) else 0.0
    measured = max(0.0, now_v - run_v) if (have_shift and run_v is not None) else 0.0

    # Self-correcting forecast: nudge the prediction by how this host's past forecasts
    # actually landed (rolling calibration ratio from the local ledger). We keep the raw
    # prediction too, so the adjustment never feeds back into the calibration that made it.
    # Prefer the chosen region's own track record (grids differ); fall back to the fleet.
    _entries = ledger.read()
    _now = datetime.now(timezone.utc)
    region_cal = ledger.calibration_by_region(_entries, _now, 30).get(chosen_label)
    if region_cal and region_cal["samples"] >= 3:
        cal, cal_scope = region_cal, chosen_label
    else:
        cal, cal_scope = ledger.calibration(_entries, _now, 30), "across regions"
    ratio = (
        cal["calibration_ratio"] if cal["samples"] >= 3 and cal["calibration_ratio"] > 0 else None
    )
    predicted_calibrated = ledger.adjusted_prediction(predicted, ratio) if ratio else None
    if ratio is not None and predicted > 0:
        direction = "lower" if ratio < 1 else "higher"
        console.print(
            f"[dim]Calibration-adjusted expected cut: ~{predicted_calibrated:.0f} gCO2/kWh "
            f"(forecasts {cal_scope} have run {abs(round((ratio - 1) * 100))}% {direction} than "
            f"actual over {cal['samples']} runs)[/dim]"
        )

    # Tell the command which region was chosen, so it can target it.
    env = {**os.environ, "CARBONLENS_REGION": chosen_label} if multi else None

    # Optionally measure the job's actual CPU-package energy (RAPL) around the run,
    # so the ledger's avoided-CO2 is a measurement, not the operator's estimate.
    rapl_before = energy.read_rapl_uj() if measure_energy else None
    result = subprocess.run(command, env=env)
    job_energy_kwh = energy_kwh
    if measure_energy and rapl_before is not None:
        rapl_after = energy.read_rapl_uj()
        if rapl_after is not None:
            job_energy_kwh = round(
                energy.energy_kwh_between(rapl_before[0], rapl_after[0], rapl_before[1]), 4
            )
            console.print(f"[dim]Measured ~{job_energy_kwh:.4f} kWh (CPU package, RAPL)[/dim]")
        else:
            console.print("[yellow]RAPL unreadable after run; using --energy-kwh.[/yellow]")
    elif measure_energy:
        console.print("[yellow]RAPL not available here; using --energy-kwh.[/yellow]")

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "region": chosen_label,
        "reason": reason,
        "deferred_hours": idx,
        "now_gco2_kwh": now_v,
        "chosen_gco2_kwh": chosen_v,
        "run_gco2_kwh": run_v,
        "basis": basis,
        "predicted_reduction_gco2_kwh": round(predicted, 1),
        "predicted_reduction_calibrated_gco2_kwh": predicted_calibrated,
        "calibration_ratio_applied": ratio,
        "reduction_gco2_kwh": round(measured, 1),
        "energy_kwh": job_energy_kwh,
        "energy_measured": measure_energy and job_energy_kwh is not None,
    }
    ledger.append(entry)

    # Also push to the org ledger API so org-statement and the Prometheus gauges go
    # live, no manual file gather. Best-effort: a reporting failure never fails the run.
    if report_to:
        try:
            client.report_impact(report_to, entry)
        except Exception as e:
            console.print(f"[yellow]Could not report impact to {report_to}: {e}[/yellow]")

    raise typer.Exit(result.returncode)


@app.command()
def calibration(
    days: int = typer.Option(30, "--days", help="Look back this many days"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Check how well submit-time forecasts predicted the run-time actual reduction.

    Only counts shifted jobs whose reduction was re-measured at execution -- the only
    runs where predicted and actual are both real. A ratio near 1.0 means the forecast
    is well-calibrated; <1 means it over-promised, >1 means it under-promised.
    """
    entries = ledger.read()
    now = datetime.now(timezone.utc)
    cal = ledger.calibration(entries, now, days)
    by_region = ledger.calibration_by_region(entries, now, days)
    if json_output:
        import json

        console.print_json(json.dumps({"overall": cal, "by_region": by_region}))
        return
    if cal["samples"] == 0:
        console.print(f"No re-measured shifted runs in the last {days} days to calibrate against.")
        console.print(
            "[dim]Run with `--measure-energy` (or against a measured-marginal source) so the "
            "run-time actual is recorded.[/dim]"
        )
        return

    def _verdict(r: float) -> str:
        return (
            "well-calibrated"
            if 0.85 <= r <= 1.15
            else ("over-promised" if r < 0.85 else "under-promised")
        )

    ratio = cal["calibration_ratio"]
    console.print(f"[bold green]Forecast calibration — last {days} days[/bold green]")
    console.print(f"  Samples:           {cal['samples']} re-measured shifted run(s)")
    console.print(f"  Mean predicted:    {cal['mean_predicted_gco2_kwh']} gCO2/kWh")
    console.print(f"  Mean actual:       {cal['mean_actual_gco2_kwh']} gCO2/kWh")
    console.print(f"  Mean abs error:    {cal['mean_abs_error_gco2_kwh']} gCO2/kWh")
    console.print(f"  Calibration ratio: {ratio} ([bold]{_verdict(ratio)}[/bold])")

    if len(by_region) > 1:
        table = Table(title="By region (grids differ in forecastability)")
        table.add_column("Region")
        table.add_column("Samples", justify="right")
        table.add_column("Ratio", justify="right")
        table.add_column("Mean abs error", justify="right")
        table.add_column("Verdict")
        for region, rc in sorted(by_region.items(), key=lambda kv: kv[1]["samples"], reverse=True):
            table.add_row(
                region,
                str(rc["samples"]),
                f"{rc['calibration_ratio']}",
                f"{rc['mean_abs_error_gco2_kwh']} gCO2/kWh",
                _verdict(rc["calibration_ratio"]),
            )
        console.print(table)


@app.command()
def impact(
    days: int = typer.Option(30, "--days", help="Look back this many days"),
):
    """Show the honest carbon impact of your `carbonlens run` jobs (local ledger)."""
    summary = ledger.summarize(ledger.read(), datetime.now(timezone.utc), days)
    if summary["jobs"] == 0:
        console.print(f"No carbon-aware runs recorded in the last {days} days.")
        console.print(
            "[dim]Use `carbonlens run --region … -- <cmd>` to start logging impact.[/dim]"
        )
        return
    console.print(f"[bold green]Carbon impact — last {days} days[/bold green]")
    console.print(f"  Jobs run:           {summary['jobs']}")
    console.print(f"  Shifted to cleaner: {summary['shifted']}")
    verified = f" ({summary['measured']} verified at run time)" if summary.get("measured") else ""
    console.print(
        f"  Avg intensity cut:  {summary['avg_reduction_gco2_kwh']} gCO2/kWh "
        f"(deferred jobs, vs running now){verified}"
    )
    if summary["jobs_with_energy"]:
        console.print(
            f"  CO2 avoided:        ~{summary['kg_avoided']} kg (estimated, from "
            f"{summary['jobs_with_energy']} job(s) with --energy-kwh)"
        )
    else:
        console.print(
            "  CO2 avoided:        pass --energy-kwh on runs for a real grams estimate "
            "(intensities alone aren't additive)"
        )


def _cleanest_mean(data: dict) -> float:
    """Mean intensity at a best-time result's cleanest hour (inf if none)."""
    hours = data.get("ranked_hours") or []
    return hours[0]["mean_gco2_kwh"] if hours else float("inf")


def _print_best_time(label: str, data: dict) -> None:
    basis = {
        "history": f"observed over the last {data['days_analyzed']} days",
        "forecast": "estimated from the next-48h forecast (history still accumulating)",
        "insufficient": "no data yet",
    }.get(data["basis"], data["basis"])

    console.print(f"[bold green]Greenest time to run[/bold green] — {label}")
    console.print(f"  Basis: {basis}")
    if data.get("cleanest_hour_utc") is not None:
        console.print(
            f"  Cleanest hour: [bold]{data['cleanest_hour_utc']:02d}:00 UTC[/bold] "
            f"(~{data['ranked_hours'][0]['mean_gco2_kwh']:.0f} gCO2/kWh)"
        )
        if data.get("shift_savings_pct") is not None:
            line = (
                f"  vs worst hour ({data['dirtiest_hour_utc']:02d}:00 UTC): "
                f"~{data['shift_savings_pct']:.0f}% cleaner"
            )
            if data.get("annual_kg_saved") is not None:
                line += f", ~{data['annual_kg_saved']:.0f} kg CO2/yr for this job"
            console.print(line)
        console.print(f"  Suggested cron: [cyan]{data['suggested_cron']}[/cyan]  # daily, UTC")
        if len(data.get("ranked_hours", [])) > 1:
            tail = ", ".join(
                f"{h['hour_utc']:02d}:00 (~{h['mean_gco2_kwh']:.0f})"
                for h in data["ranked_hours"][1:]
            )
            console.print(f"  Other clean hours: {tail}")
    else:
        console.print("  Not enough data yet to recommend an hour.")


@app.command(name="fleet-impact")
def fleet_impact(
    directory: str = typer.Option(
        ..., "--dir", help="Directory of per-host *.jsonl impact ledgers (collected from the fleet)"
    ),
    days: int = typer.Option(30, "--days", help="Look back this many days"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Org-level verified carbon impact across a fleet of hosts' impact ledgers."""
    import glob
    from pathlib import Path

    files = sorted(glob.glob(str(Path(directory) / "*.jsonl")))
    if not files:
        console.print(f"[red]Error:[/red] no *.jsonl ledger files in {directory}")
        raise typer.Exit(1)
    entries: list[dict] = []
    for f in files:
        entries.extend(ledger.read_file(Path(f)))
    summary = ledger.fleet_summary(entries, datetime.now(timezone.utc), days)

    if json_output:
        import json

        console.print_json(json.dumps(summary))
        return

    console.print(
        f"[bold green]Fleet carbon impact — last {days} days[/bold green] ({len(files)} hosts)"
    )
    console.print(f"  Jobs run:           {summary['jobs']}")
    console.print(
        f"  Shifted to cleaner: {summary['shifted']} ({summary['measured']} verified at run time)"
    )
    console.print(
        f"  CO2 avoided:        ~{summary['total_kg_avoided']} kg "
        f"(from {summary['jobs_with_energy']} jobs run with --energy-kwh)"
    )
    if summary["regions"]:
        table = Table(title="By region")
        table.add_column("Region")
        table.add_column("Jobs", justify="right")
        table.add_column("Shifted", justify="right")
        table.add_column("kg avoided", justify="right", style="green")
        for r in summary["regions"]:
            table.add_row(r["region"], str(r["jobs"]), str(r["shifted"]), f"{r['kg_avoided']:.1f}")
        console.print(table)


@app.command(name="org-statement")
def org_statement(
    directory: str = typer.Option(
        ..., "--dir", help="Directory of per-host *.jsonl impact ledgers (collected from the fleet)"
    ),
    org: str = typer.Option("Your organization", "--org", help="Organization name for the header"),
    days: int = typer.Option(90, "--days", help="Reporting period (days)"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """A methodology-stated, org-level carbon-aware-compute statement (for disclosure)."""
    import glob
    from pathlib import Path

    files = sorted(glob.glob(str(Path(directory) / "*.jsonl")))
    if not files:
        console.print(f"[red]Error:[/red] no *.jsonl ledger files in {directory}")
        raise typer.Exit(1)
    entries: list[dict] = []
    for f in files:
        entries.extend(ledger.read_file(Path(f)))
    stmt = ledger.org_statement(entries, datetime.now(timezone.utc), days, org)

    if json_output:
        import json

        console.print_json(json.dumps(stmt))
        return

    console.print(f"\n## Carbon-aware compute statement — {stmt['org']}")
    console.print(f"Period: last {stmt['period_days']} days · {len(files)} host(s)\n")
    console.print(f"- Jobs run: {stmt['jobs']}")
    console.print(
        f"- Shifted to cleaner windows: {stmt['shifted']} "
        f"({stmt['verified_share_pct']}% verified at run time)"
    )
    console.print(
        f"- CO2 avoided: ~{stmt['total_kg_avoided']} kg "
        f"(from {stmt['jobs_with_energy']} jobs with measured energy)"
    )
    console.print(f"\n[dim]Counterfactual:[/dim] {stmt['counterfactual']}")
    console.print(f"[dim]Accounting:[/dim] {stmt['accounting']}")
    if stmt["regions"]:
        table = Table(title="By region")
        table.add_column("Region")
        table.add_column("Jobs", justify="right")
        table.add_column("Shifted", justify="right")
        table.add_column("kg avoided", justify="right", style="green")
        for r in stmt["regions"]:
            table.add_row(r["region"], str(r["jobs"]), str(r["shifted"]), f"{r['kg_avoided']:.1f}")
        console.print(table)
    console.print()


@app.command(name="best-time")
def best_time(
    region: str = typer.Argument(
        help="provider/region (e.g. aws/us-east-1). Comma-separate several to also pick "
        "the greenest place for a recurring job."
    ),
    days: int = typer.Option(14, "--days", help="History window to analyze"),
    energy_kwh: Optional[float] = typer.Option(
        None, "--energy-kwh", help="Daily job energy (kWh) for an annual kg-saved estimate"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Find the greenest hour-of-day (and, with several regions, the greenest place)."""
    labels = [r.strip() for r in region.split(",") if r.strip()]
    results: dict[str, dict] = {}
    for lbl in labels:
        provider, _, reg = lbl.partition("/")
        if not provider or not reg:
            console.print(f"[red]Error:[/red] region must be provider/region (got '{lbl}')")
            raise typer.Exit(1)
        try:
            results[lbl] = client.best_time(provider, reg, days, energy_kwh)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(results if len(labels) > 1 else results[labels[0]]))
        return

    console.print()
    if len(labels) > 1:
        winner = min(labels, key=lambda lbl: _cleanest_mean(results[lbl]))
        console.print(f"[bold]Greenest place + time:[/bold] {winner}\n")
        _print_best_time(winner, results[winner])
        others = ", ".join(
            f"{lbl} ({_cleanest_mean(results[lbl]):.0f} gCO2/kWh)"
            for lbl in labels
            if lbl != winner
        )
        console.print(f"  Compared with: {others}")
    else:
        _print_best_time(labels[0], results[labels[0]])
    console.print()


@app.command()
def siting(
    providers: str = typer.Option(
        "aws,gcp,azure", "--providers", "-p", help="Comma-separated providers to consider"
    ),
    power_watts: Optional[float] = typer.Option(
        None, "--power-watts", help="Continuous load (W) for an annual kg estimate"
    ),
    days: int = typer.Option(30, "--days", help="History window for the typical mean"),
    limit: int = typer.Option(15, "--limit", help="How many candidates to show"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Pick the greenest region to permanently host a 24/7 workload (typical intensity)."""
    try:
        data = client.siting(providers, power_watts, days, limit)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(data))
        return

    rec = data["recommended"]
    console.print()
    console.print(
        f"[bold green]Greenest region to host[/bold green]: "
        f"{rec['provider']}/{rec['region']} ({rec['location']})"
    )
    console.print(f"  Typical: {rec['typical_gco2_kwh']:.0f} gCO2/kWh ({rec['basis']})")
    if data.get("annual_kg_saved_vs_worst") is not None:
        console.print(
            f"  vs worst candidate: ~{data['annual_kg_saved_vs_worst']:.0f} kg CO2/yr saved "
            "at this load"
        )
    table = Table(title=f"Candidates by typical intensity ({data['days_analyzed']}d)")
    table.add_column("#", style="dim")
    table.add_column("Region")
    table.add_column("Location")
    table.add_column("Typical gCO2/kWh", justify="right")
    table.add_column("kg/yr", justify="right")
    for i, o in enumerate(data["options"], start=1):
        table.add_row(
            str(i),
            f"{o['provider']}/{o['region']}",
            o["location"],
            f"{o['typical_gco2_kwh']:.0f}",
            f"{o['annual_kg']:.0f}" if o.get("annual_kg") is not None else "-",
        )
    console.print(table)
    console.print()


@app.command()
def plan(
    power_watts: float = typer.Option(..., "--power-watts", help="Continuous workload power (W)"),
    flexible: float = typer.Option(
        0.5, "--flexible", help="Fraction of the load that can be time-shifted (0-1)"
    ),
    providers: str = typer.Option("aws,gcp,azure", "--providers", "-p"),
    days: int = typer.Option(30, "--days", help="History window"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Estimate the annual carbon opportunity: naive vs greenest-region + time-shifting."""
    try:
        siting_data = client.siting(providers, power_watts, days)
        shift_data = client.shiftability(days, 200)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    est = plan_estimate(siting_data, shift_data, power_watts, flexible)
    if not est.get("available"):
        console.print("Not enough data to plan right now.")
        return
    if json_output:
        import json

        console.print_json(json.dumps(est))
        return

    console.print()
    console.print(f"[bold green]Annual carbon opportunity[/bold green] — {power_watts:.0f} W")
    console.print(f"  Naive (carbon-blind):   {est['naive_annual_kg']:.0f} kg CO2/yr")
    console.print(
        f"  Carbon-aware:           {est['optimized_annual_kg']:.0f} kg CO2/yr "
        f"in [bold]{est['best_region']}[/bold]"
    )
    console.print(
        f"  Total avoided:          ~{est['total_saving_kg']:.0f} kg CO2/yr "
        f"(region {est['region_saving_kg']:.0f} + shifting {est['shift_saving_kg']:.0f})"
    )
    console.print(
        f"  [dim]Assumes {flexible:.0%} of load is shiftable and today's grid patterns hold.[/dim]"
    )
    console.print()


@app.command()
def shiftability(
    days: int = typer.Option(14, "--days", help="History window to analyze"),
    limit: int = typer.Option(20, "--limit", help="How many zones to show"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Rank grid zones by how much carbon-aware scheduling helps (intra-day swing)."""
    try:
        data = client.shiftability(days, limit)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(data))
        return

    zones = data.get("zones", [])
    if not zones:
        console.print("Not enough history yet to rank zones.")
        return
    table = Table(title=f"Where carbon-aware scheduling helps most ({data['days_analyzed']}d)")
    table.add_column("#", style="dim")
    table.add_column("Grid Zone")
    table.add_column("Location")
    table.add_column("Shift savings", justify="right", style="green")
    table.add_column("Best→worst hr", justify="right")
    for i, z in enumerate(zones, start=1):
        table.add_row(
            str(i),
            z["grid_zone"],
            z["location"],
            f"{z['shift_savings_pct']:.0f}%",
            f"{z['cleanest_hour_utc']:02d}→{z['dirtiest_hour_utc']:02d} UTC",
        )
    console.print(table)


def _render_doctor(api: str, checks: dict, ok: bool, json_output: bool) -> None:
    """Print the doctor result as JSON (for CI gating) or a human checklist."""
    if json_output:
        import json

        console.print_json(json.dumps({"api_url": api, "ok": ok, "checks": checks}))
        return

    console.print(f"[bold]CarbonLens doctor[/bold] — checking {api}\n")

    api_check = checks["api_reachable"]
    if not api_check["ok"]:
        console.print(f"[red]✗[/red] API unreachable: {api_check['error']}")
        console.print(
            "\n[red]Cannot continue without the API.[/red] "
            "Set its URL with `carbonlens config set api-url <url>`."
        )
        return
    console.print("[green]✓[/green] API reachable")

    src = checks.get("data_sources", {})
    if "error" in src:
        console.print(f"[yellow]![/yellow] Could not check data sources: {src['error']}")
    elif src.get("ok"):
        console.print(f"[green]✓[/green] Data sources: {src['live']}/{src['total']} live")
    else:
        console.print(
            f"[yellow]![/yellow] Data sources: {src.get('live', 0)}/{src.get('total', 0)} live "
            "(the rest fall back to estimates)"
        )

    marg = checks.get("marginal", {})
    if "error" in marg:
        console.print(f"[yellow]![/yellow] Could not read marginal honesty: {marg['error']}")
    elif marg.get("ok"):
        console.print("[green]✓[/green] Marginal signal: measured (operator key configured)")
    elif marg.get("configured_but_unmapped"):
        console.print(
            "[red]✗[/red] Marginal signal: heuristic, but a marginal key IS configured — no zone "
            "is mapped, so it's silently unused. Set CARBON_LENS_WATTTIME_ZONE_MAP (or "
            "CARBON_LENS_ELECTRICITY_MAPS_ZONE_MAP)."
        )
    else:
        console.print(
            "[yellow]![/yellow] Marginal signal: heuristic "
            "(merit-order estimate; bring a WattTime / Electricity Maps key to measure)"
        )

    console.print()
    if ok:
        console.print("[green]Ready.[/green] API reachable and data sources live.")
    else:
        console.print(
            "[yellow]Usable, with the caveats above.[/yellow] "
            "CarbonLens degrades to honest estimates when a source is unavailable."
        )


@app.command()
def doctor(
    json_output: bool = typer.Option(
        False, "--json", help="Emit the checks as JSON so CI / readiness gates can act on them"
    ),
):
    """Preflight self-test: API reachability, live-vs-estimated sources, marginal basis.

    A quick honesty check before you wire CarbonLens into a pipeline -- it tells you
    which signals are live/measured versus modelled/heuristic, so you know what you're
    acting on. Exits non-zero if the API is unreachable.
    """
    api = client.get_api_url()
    checks: dict = {}
    ok = True

    try:
        client.health()
        checks["api_reachable"] = {"ok": True}
    except Exception as e:
        checks["api_reachable"] = {"ok": False, "error": str(e)}
        _render_doctor(api, checks, ok=False, json_output=json_output)
        raise typer.Exit(1)

    try:
        sh = client.source_health()
        healthy, total = sh.get("healthy", 0), sh.get("total", 0)
        live_ok = healthy == total and bool(total)
        checks["data_sources"] = {"ok": live_ok, "live": healthy, "total": total}
        if not live_ok:
            ok = False
    except Exception as e:
        checks["data_sources"] = {"error": str(e)}
        ok = False

    try:
        h = client.honesty()
        basis = h.get("marginal_basis", "heuristic")
        unmapped = bool(h.get("marginal_configured_but_unmapped"))
        checks["marginal"] = {
            "ok": basis == "measured",
            "basis": basis,
            "configured_but_unmapped": unmapped,
        }
        if unmapped:
            ok = False  # a key was set but no zone mapped -- a misconfiguration, not a choice
    except Exception as e:
        checks["marginal"] = {"error": str(e)}

    _render_doctor(api, checks, ok=ok, json_output=json_output)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(help="Config key: api-url or api-key"),
    value: str = typer.Argument(help="Config value"),
):
    """Set a CLI configuration value."""
    config = client.load_config()
    key_map = {"api-url": "api_url", "api-key": "api_key"}
    internal_key = key_map.get(key)
    if internal_key is None:
        console.print(f"[red]Unknown config key:[/red] {key}. Valid keys: api-url, api-key")
        raise typer.Exit(1)
    config[internal_key] = value
    client.save_config(config)
    console.print(f"[green]Set {key}[/green]")


@config_app.command("show")
def config_show():
    """Show current CLI configuration."""
    config = client.load_config()
    console.print()
    console.print("[bold]CarbonLens CLI Config[/bold]")
    console.print(f"  API URL: {config.get('api_url', 'http://localhost:8000 (default)')}")
    key = config.get("api_key")
    if key:
        console.print(f"  API Key: {key[:10]}...")
    else:
        console.print("  API Key: [dim]not set[/dim]")
    console.print(f"  Config:  {client.CONFIG_FILE}")
    console.print()


if __name__ == "__main__":
    app()
