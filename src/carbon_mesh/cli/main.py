"""CarbonLens CLI — Find the greenest cloud region for your workload."""

import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from carbon_mesh.cli import client, ledger
from carbon_mesh.cli.green_run import choose_run_index, choose_run_plan

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

    # Record what this run did, for an honest impact tally (`carbonlens impact`).
    # Counterfactual is running now, so reduction is 0 unless we deferred.
    reduction = (
        max(0.0, now_v - chosen_v)
        if (idx > 0 and now_v is not None and chosen_v is not None)
        else 0.0
    )
    ledger.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "region": chosen_label,
            "reason": reason,
            "deferred_hours": idx,
            "now_gco2_kwh": now_v,
            "chosen_gco2_kwh": chosen_v,
            "reduction_gco2_kwh": round(reduction, 1),
            "energy_kwh": energy_kwh,
        }
    )

    # Tell the command which region was chosen, so it can target it.
    env = {**os.environ, "CARBONLENS_REGION": chosen_label} if multi else None
    result = subprocess.run(command, env=env)
    raise typer.Exit(result.returncode)


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
    console.print(
        f"  Avg intensity cut:  {summary['avg_reduction_gco2_kwh']} gCO2/kWh "
        "(deferred jobs, vs running now)"
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


@app.command(name="best-time")
def best_time(
    region: str = typer.Argument(help="Region in provider/region format, e.g. aws/us-east-1"),
    days: int = typer.Option(14, "--days", help="History window to analyze"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Find the greenest hour-of-day to schedule a recurring job (and a cron line)."""
    provider, _, reg = region.partition("/")
    if not provider or not reg:
        console.print("[red]Error:[/red] region must be provider/region, e.g. aws/us-east-1")
        raise typer.Exit(1)
    try:
        data = client.best_time(provider, reg, days)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print_json(json.dumps(data))
        return

    basis = {
        "history": f"observed over the last {data['days_analyzed']} days",
        "forecast": "estimated from the next-48h forecast (history still accumulating)",
        "insufficient": "no data yet",
    }.get(data["basis"], data["basis"])

    console.print()
    console.print(f"[bold green]Greenest time to run[/bold green] — {region}")
    console.print(f"  Basis: {basis}")
    if data.get("cleanest_hour_utc") is not None:
        console.print(
            f"  Cleanest hour: [bold]{data['cleanest_hour_utc']:02d}:00 UTC[/bold] "
            f"(~{data['ranked_hours'][0]['mean_gco2_kwh']:.0f} gCO2/kWh)"
        )
        console.print(f"  Suggested cron: [cyan]{data['suggested_cron']}[/cyan]  # daily, UTC")
        if len(data.get("ranked_hours", [])) > 1:
            tail = ", ".join(
                f"{h['hour_utc']:02d}:00 (~{h['mean_gco2_kwh']:.0f})"
                for h in data["ranked_hours"][1:]
            )
            console.print(f"  Other clean hours: {tail}")
    else:
        console.print("  Not enough data yet to recommend an hour.")
    console.print()


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
