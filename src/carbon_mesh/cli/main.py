"""Carbon Mesh CLI — Find the greenest cloud region for your workload."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from carbon_mesh.cli import client

app = typer.Typer(
    name="carbon-mesh",
    help="Carbon-aware multi-cloud routing CLI",
    no_args_is_help=True,
)
console = Console()
config_app = typer.Typer(help="Manage CLI configuration")
app.add_typer(config_app, name="config")


@app.command()
def route(
    providers: str = typer.Option("aws,gcp,azure", "--providers", "-p", help="Comma-separated providers"),
    residency: Optional[str] = typer.Option(None, "--residency", "-r", help="Data residency, e.g. EU, US"),
    carbon_weight: float = typer.Option(1.0, "--carbon-weight", "-c", help="Carbon optimization weight (0-1)"),
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
    console.print(f"  Carbon Savings:   {rec['carbon_savings_vs_worst_pct']:.1f}% greener than worst")
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
            color = "green" if alt["carbon_intensity_gco2_kwh"] <= 50 else (
                "yellow" if alt["carbon_intensity_gco2_kwh"] <= 200 else "red"
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
        console.print("[red]Error:[/red] Region must be in format provider/region (e.g. aws/us-east-1)")
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

    color = "green" if data["carbon_intensity_gco2_kwh"] <= 50 else (
        "yellow" if data["carbon_intensity_gco2_kwh"] <= 200 else "red"
    )
    console.print()
    console.print(f"[bold]{region}[/bold]")
    console.print(f"  Grid Zone:        {data['grid_zone']}")
    console.print(f"  Carbon Intensity: [{color}]{data['carbon_intensity_gco2_kwh']} gCO2/kWh[/{color}]")
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
    console.print(f"  Carbon Saved:     {data['total_carbon_saved_gco2_kwh']} gCO2/kWh")
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
                f"{r['carbon_saved_gco2_kwh']:.1f}",
                r["timestamp"][:19],
            )
        console.print(table)
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
    console.print("[bold]Carbon Mesh CLI Config[/bold]")
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
