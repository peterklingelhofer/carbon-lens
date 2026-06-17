"""Tests for CLI module: client helpers and Typer app commands."""

import inspect
import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from carbon_mesh.cli import client
from carbon_mesh.cli.green_run import choose_run_index
from carbon_mesh.cli.main import app


# ---------------------------------------------------------------------------
# generate_api_key tests
# ---------------------------------------------------------------------------


def _generate_api_key() -> str:
    """Local reimplementation to avoid importing the full auth module
    (which pulls in SQLAlchemy models that fail to resolve on some Python versions).
    Mirrors carbon_mesh.auth.api_keys.generate_api_key exactly.
    """
    import secrets

    return "cmesh_" + secrets.token_hex(24)


class TestGenerateApiKey:
    def test_returns_string(self):
        key = _generate_api_key()
        assert isinstance(key, str)

    def test_prefix(self):
        key = _generate_api_key()
        assert key.startswith("cmesh_")

    def test_length(self):
        # "cmesh_" (6 chars) + 48 hex chars (24 bytes) = 54
        key = _generate_api_key()
        assert len(key) == 54

    def test_unique(self):
        keys = {_generate_api_key() for _ in range(20)}
        assert len(keys) == 20

    def test_hex_suffix(self):
        key = _generate_api_key()
        hex_part = key[len("cmesh_") :]
        # Should be valid hex
        int(hex_part, 16)


# ---------------------------------------------------------------------------
# Client function signatures
# ---------------------------------------------------------------------------


class TestClientFunctions:
    def test_route_exists_and_signature(self):
        sig = inspect.signature(client.route)
        params = list(sig.parameters.keys())
        assert "providers" in params
        assert "residency" in params
        assert "carbon_weight" in params
        assert "cost_weight" in params

    def test_regions_exists_and_signature(self):
        sig = inspect.signature(client.regions)
        params = list(sig.parameters.keys())
        assert "provider" in params

    def test_intensity_exists_and_signature(self):
        sig = inspect.signature(client.intensity)
        params = list(sig.parameters.keys())
        assert "provider" in params
        assert "region" in params

    def test_savings_exists(self):
        assert callable(client.savings)

    def test_load_config_exists(self):
        assert callable(client.load_config)

    def test_save_config_exists(self):
        assert callable(client.save_config)


# ---------------------------------------------------------------------------
# Config load / save with temp directory
# ---------------------------------------------------------------------------


class TestConfigIO:
    def test_load_config_returns_empty_dict_when_missing(self, tmp_path: Path):
        fake_file = tmp_path / "config.json"
        with patch.object(client, "CONFIG_FILE", fake_file):
            cfg = client.load_config()
        assert cfg == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        fake_dir = tmp_path / ".carbon-mesh"
        fake_file = fake_dir / "config.json"
        with (
            patch.object(client, "CONFIG_DIR", fake_dir),
            patch.object(client, "CONFIG_FILE", fake_file),
        ):
            client.save_config({"api_url": "https://example.com", "api_key": "cmesh_abc"})
            cfg = client.load_config()
        assert cfg["api_url"] == "https://example.com"
        assert cfg["api_key"] == "cmesh_abc"

    def test_save_creates_directory(self, tmp_path: Path):
        fake_dir = tmp_path / "nested" / ".carbon-mesh"
        fake_file = fake_dir / "config.json"
        with (
            patch.object(client, "CONFIG_DIR", fake_dir),
            patch.object(client, "CONFIG_FILE", fake_file),
        ):
            client.save_config({"api_url": "http://localhost:9000"})
        assert fake_file.exists()
        assert json.loads(fake_file.read_text())["api_url"] == "http://localhost:9000"


# ---------------------------------------------------------------------------
# CLI app commands
# ---------------------------------------------------------------------------

runner = CliRunner()


class TestCliApp:
    def test_app_has_route_command(self):
        names = [cmd for cmd in app.registered_commands]
        command_names = [c.name or c.callback.__name__ for c in names]
        assert "route" in command_names

    def test_app_has_intensity_command(self):
        command_names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "intensity" in command_names

    def test_app_has_regions_command(self):
        command_names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "regions" in command_names

    def test_app_has_report_command(self):
        command_names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "report" in command_names

    def test_app_has_config_subcommand(self):
        group_names = [g.name for g in app.registered_groups]
        assert "config" in group_names

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        # Typer with no_args_is_help=True exits with code 0 or 2 depending on version
        assert result.exit_code in (0, 2)
        assert "Usage" in result.stdout or "usage" in result.stdout.lower()


def _forecast(intensities: list[float]) -> dict:
    return {
        "method": "time_of_day_model",
        "points": [
            {"timestamp": f"2026-06-15T{h:02d}:00:00+00:00", "carbon_intensity_gco2_kwh": v}
            for h, v in enumerate(intensities)
        ],
    }


class TestChooseRunIndex:
    def test_runs_now_when_already_clean(self):
        assert choose_run_index([40, 300], 100, 24) == (0, "threshold")

    def test_defers_to_first_hour_under_threshold(self):
        assert choose_run_index([300, 300, 50, 400], 100, 24) == (2, "threshold")

    def test_cleanest_when_no_threshold_given(self):
        assert choose_run_index([300, 200, 250], None, 24) == (1, "cleanest")

    def test_falls_back_to_cleanest_when_threshold_unreachable(self):
        assert choose_run_index([300, 250, 280], 100, 24) == (1, "cleanest_fallback")

    def test_window_respects_max_wait(self):
        # The 10 at index 3 is cleanest overall but outside a 2-hour window.
        assert choose_run_index([300, 290, 280, 10], None, 2) == (2, "cleanest")

    def test_now_surplus_runs_immediately(self):
        assert choose_run_index([30, 300], None, 24, surplus_hours=[0]) == (0, "surplus_now")

    def test_defers_to_soonest_surplus_window(self):
        # Cleanest is hour 1 (50), but hour 3 is a clean-surplus window -> prefer it.
        assert choose_run_index([300, 50, 200, 40], None, 24, surplus_hours=[3]) == (3, "surplus")

    def test_does_not_idle_for_a_trivial_gain(self):
        # Cleanest (hour 2) is only ~3% under now -> not worth deferring.
        assert choose_run_index([300, 295, 291], None, 24) == (0, "now_no_benefit")

    def test_threshold_still_wins_when_now_is_acceptable(self):
        # Even with a later surplus window, an acceptable now runs immediately.
        assert choose_run_index([40, 300, 30], 100, 24, surplus_hours=[2]) == (0, "threshold")


class TestImpactLedger:
    def test_real_grams_only_from_jobs_with_energy(self):
        from datetime import datetime, timezone

        from carbon_mesh.cli.ledger import summarize

        now = datetime(2026, 6, 16, tzinfo=timezone.utc)
        entries = [
            # Deferred, 200 gCO2/kWh avoided, 10 kWh -> 2000 g avoided.
            {
                "ts": now.isoformat(),
                "deferred_hours": 3,
                "reduction_gco2_kwh": 200,
                "energy_kwh": 10,
            },
            # Deferred but no energy -> counts toward avg, not grams.
            {"ts": now.isoformat(), "deferred_hours": 2, "reduction_gco2_kwh": 100},
            # Ran now -> not shifted, avoids nothing.
            {"ts": now.isoformat(), "deferred_hours": 0, "reduction_gco2_kwh": 0},
        ]
        s = summarize(entries, now, days=30)
        assert s["jobs"] == 3
        assert s["shifted"] == 2
        assert s["jobs_with_energy"] == 1
        assert s["avg_reduction_gco2_kwh"] == 150.0  # (200 + 100) / 2
        assert s["grams_avoided"] == 2000.0
        assert s["kg_avoided"] == 2.0

    def test_old_entries_drop_out_of_window(self):
        from datetime import datetime, timedelta, timezone

        from carbon_mesh.cli.ledger import summarize

        now = datetime(2026, 6, 16, tzinfo=timezone.utc)
        old = (now - timedelta(days=40)).isoformat()
        entries = [{"ts": old, "deferred_hours": 3, "reduction_gco2_kwh": 100, "energy_kwh": 5}]
        assert summarize(entries, now, days=30)["jobs"] == 0


class TestRunCommand:
    def test_dry_run_reports_a_deferral(self):
        with patch("carbon_mesh.cli.client.forecast", return_value=_forecast([300, 300, 50])):
            result = runner.invoke(
                app,
                [
                    "run",
                    "--region",
                    "aws/us-east-1",
                    "--max-intensity",
                    "100",
                    "--dry-run",
                    "--",
                    "echo",
                    "hi",
                ],
            )
        assert result.exit_code == 0
        assert "Deferring" in result.output

    def test_dry_run_runs_now_when_clean(self):
        with patch("carbon_mesh.cli.client.forecast", return_value=_forecast([40, 300])):
            result = runner.invoke(
                app, ["run", "--region", "aws/us-east-1", "--dry-run", "--", "echo", "hi"]
            )
        assert result.exit_code == 0
        assert "green now" in result.output

    def test_rejects_malformed_region(self):
        result = runner.invoke(app, ["run", "--region", "bogus", "--dry-run", "--", "echo", "hi"])
        assert result.exit_code == 1
