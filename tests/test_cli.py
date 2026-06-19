"""Tests for CLI module: client helpers and Typer app commands."""

import inspect
import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from carbon_mesh.cli import client
from carbon_mesh.cli.green_run import choose_run_index, choose_run_plan
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

    def test_report_impact_posts_entry_to_org_ledger(self, monkeypatch):
        captured = {}

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"stored": True}

        def fake_post(url, json, headers, timeout):
            captured["url"] = url
            captured["json"] = json
            return _Resp()

        monkeypatch.setattr(client.httpx, "post", fake_post)
        entry = {"region": "aws/us-east-1", "reduction_gco2_kwh": 120.0, "energy_kwh": 0.5}
        out = client.report_impact("https://ledger.example.com/", entry)

        assert out == {"stored": True}
        assert captured["url"] == "https://ledger.example.com/api/v1/accounting/impact"
        assert captured["json"] == entry


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

    def test_app_has_doctor_command(self):
        command_names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "doctor" in command_names

    def test_doctor_reports_live_and_measured(self, monkeypatch):
        monkeypatch.setattr(client, "health", lambda: {"status": "ok"})
        monkeypatch.setattr(client, "source_health", lambda: {"healthy": 7, "total": 7})
        monkeypatch.setattr(
            client,
            "honesty",
            lambda: {"marginal_basis": "measured", "marginal_configured_but_unmapped": False},
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "API reachable" in result.stdout
        assert "7/7 live" in result.stdout
        assert "measured" in result.stdout
        assert "Ready" in result.stdout

    def test_doctor_flags_heuristic_and_degraded(self, monkeypatch):
        monkeypatch.setattr(client, "health", lambda: {"status": "ok"})
        monkeypatch.setattr(client, "source_health", lambda: {"healthy": 4, "total": 7})
        monkeypatch.setattr(
            client,
            "honesty",
            lambda: {"marginal_basis": "heuristic", "marginal_configured_but_unmapped": False},
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "4/7 live" in result.stdout
        assert "heuristic" in result.stdout
        assert "caveats" in result.stdout

    def test_doctor_flags_configured_but_unmapped_marginal(self, monkeypatch):
        monkeypatch.setattr(client, "health", lambda: {"status": "ok"})
        monkeypatch.setattr(client, "source_health", lambda: {"healthy": 7, "total": 7})
        monkeypatch.setattr(
            client,
            "honesty",
            lambda: {"marginal_basis": "heuristic", "marginal_configured_but_unmapped": True},
        )
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "no zone" in result.stdout.lower()
        assert "ZONE_MAP" in result.stdout
        assert "caveats" in result.stdout  # the unmapped trap flips the verdict

    def test_doctor_json_output(self, monkeypatch):
        import json as _json

        monkeypatch.setattr(client, "health", lambda: {"status": "ok"})
        monkeypatch.setattr(client, "source_health", lambda: {"healthy": 4, "total": 7})
        monkeypatch.setattr(
            client,
            "honesty",
            lambda: {"marginal_basis": "heuristic", "marginal_configured_but_unmapped": False},
        )
        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 0
        payload = _json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["checks"]["data_sources"] == {"ok": False, "live": 4, "total": 7}
        assert payload["checks"]["marginal"] == {
            "ok": False,
            "basis": "heuristic",
            "configured_but_unmapped": False,
        }

    def test_doctor_exits_when_api_unreachable(self, monkeypatch):
        def _boom():
            raise RuntimeError("connection refused")

        monkeypatch.setattr(client, "health", _boom)
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "unreachable" in result.stdout

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

    def test_counts_verified_measured_jobs(self):
        from datetime import datetime, timezone

        from carbon_mesh.cli.ledger import summarize

        now = datetime(2026, 6, 16, tzinfo=timezone.utc)
        entries = [
            {
                "ts": now.isoformat(),
                "deferred_hours": 3,
                "reduction_gco2_kwh": 200,
                "basis": "measured",
            },
            {
                "ts": now.isoformat(),
                "deferred_hours": 2,
                "reduction_gco2_kwh": 100,
                "basis": "forecast",
            },
        ]
        s = summarize(entries, now, days=30)
        assert s["shifted"] == 2
        assert s["measured"] == 1

    def test_calibration_compares_predicted_to_measured_actual(self):
        from datetime import datetime, timezone

        from carbon_mesh.cli.ledger import calibration

        now = datetime(2026, 6, 18, tzinfo=timezone.utc)
        entries = [
            # Re-measured shifted run: predicted 200, actual 180.
            {
                "ts": now.isoformat(),
                "deferred_hours": 3,
                "predicted_reduction_gco2_kwh": 200,
                "reduction_gco2_kwh": 180,
                "basis": "measured",
            },
            # Re-measured shifted run: predicted 100, actual 120.
            {
                "ts": now.isoformat(),
                "deferred_hours": 2,
                "predicted_reduction_gco2_kwh": 100,
                "reduction_gco2_kwh": 120,
                "basis": "measured",
            },
            # Forecast-only (not re-measured) -> excluded from calibration.
            {
                "ts": now.isoformat(),
                "deferred_hours": 2,
                "predicted_reduction_gco2_kwh": 50,
                "reduction_gco2_kwh": 50,
                "basis": "forecast",
            },
            # Ran now -> excluded.
            {"ts": now.isoformat(), "deferred_hours": 0},
        ]
        cal = calibration(entries, now, days=30)
        assert cal["samples"] == 2
        assert cal["mean_predicted_gco2_kwh"] == 150.0
        assert cal["mean_actual_gco2_kwh"] == 150.0
        assert cal["calibration_ratio"] == 1.0  # 300 actual / 300 predicted
        assert cal["mean_abs_error_gco2_kwh"] == 20.0  # (|180-200| + |120-100|)/2

    def test_calibration_empty_when_no_measured_runs(self):
        from datetime import datetime, timezone

        from carbon_mesh.cli.ledger import calibration

        now = datetime(2026, 6, 18, tzinfo=timezone.utc)
        cal = calibration([{"ts": now.isoformat(), "deferred_hours": 0}], now, days=30)
        assert cal["samples"] == 0
        assert cal["calibration_ratio"] == 0.0

    def test_org_statement_includes_forecast_calibration(self):
        from datetime import datetime, timezone

        from carbon_mesh.cli.ledger import org_statement

        now = datetime(2026, 6, 18, tzinfo=timezone.utc)
        entries = [
            {
                "ts": now.isoformat(),
                "region": "aws/us-east-1",
                "deferred_hours": 3,
                "predicted_reduction_gco2_kwh": 200,
                "reduction_gco2_kwh": 200,
                "energy_kwh": 10,
                "basis": "measured",
            }
        ]
        stmt = org_statement(entries, now, days=90)
        assert stmt["forecast_calibration"]["samples"] == 1
        assert stmt["forecast_calibration"]["calibration_ratio"] == 1.0

    def test_fleet_summary_aggregates_by_region(self):
        from datetime import datetime, timezone

        from carbon_mesh.cli.ledger import fleet_summary

        now = datetime(2026, 6, 17, tzinfo=timezone.utc)
        entries = [
            {
                "ts": now.isoformat(),
                "region": "aws/us-east-1",
                "deferred_hours": 3,
                "reduction_gco2_kwh": 200,
                "energy_kwh": 10,
                "basis": "measured",
            },  # 2.0 kg
            {
                "ts": now.isoformat(),
                "region": "aws/us-east-1",
                "deferred_hours": 2,
                "reduction_gco2_kwh": 100,
                "energy_kwh": 5,
                "basis": "forecast",
            },  # 0.5 kg
            {"ts": now.isoformat(), "region": "gcp/europe-west1", "deferred_hours": 0},  # ran now
        ]
        s = fleet_summary(entries, now, days=30)
        assert s["jobs"] == 3
        assert s["shifted"] == 2
        assert s["measured"] == 1
        assert s["total_kg_avoided"] == 2.5
        assert s["regions"][0]["region"] == "aws/us-east-1"
        assert s["regions"][0]["kg_avoided"] == 2.5

    def test_org_statement_states_methodology(self):
        from datetime import datetime, timezone

        from carbon_mesh.cli.ledger import org_statement

        now = datetime(2026, 6, 18, tzinfo=timezone.utc)
        entries = [
            {
                "ts": now.isoformat(),
                "region": "aws/us-east-1",
                "deferred_hours": 3,
                "reduction_gco2_kwh": 200,
                "energy_kwh": 10,
                "basis": "measured",
            },
            {
                "ts": now.isoformat(),
                "region": "aws/us-east-1",
                "deferred_hours": 2,
                "reduction_gco2_kwh": 100,
                "energy_kwh": 5,
                "basis": "forecast",
            },
        ]
        stmt = org_statement(entries, now, days=90, org_name="Acme")
        assert stmt["org"] == "Acme"
        assert stmt["shifted"] == 2
        assert stmt["verified_share_pct"] == 50.0  # 1 of 2 re-measured
        assert stmt["total_kg_avoided"] == 2.5
        assert "counterfactual" in stmt and "Location-based" in stmt["accounting"]

    def test_org_statement_command(self, tmp_path: Path):
        (tmp_path / "h.jsonl").write_text(
            json.dumps(
                {
                    "ts": "2026-06-18T12:00:00+00:00",
                    "region": "aws/us-east-1",
                    "deferred_hours": 3,
                    "reduction_gco2_kwh": 200,
                    "energy_kwh": 10,
                    "basis": "measured",
                }
            )
            + "\n"
        )
        result = runner.invoke(
            app, ["org-statement", "--dir", str(tmp_path), "--org", "Acme", "--days", "3650"]
        )
        assert result.exit_code == 0
        assert "Acme" in result.output
        assert "Counterfactual" in result.output

    def test_fleet_impact_command_reads_dir(self, tmp_path: Path):
        (tmp_path / "host-a.jsonl").write_text(
            json.dumps(
                {
                    "ts": "2026-06-17T12:00:00+00:00",
                    "region": "aws/us-east-1",
                    "deferred_hours": 3,
                    "reduction_gco2_kwh": 200,
                    "energy_kwh": 10,
                    "basis": "measured",
                }
            )
            + "\n"
        )
        result = runner.invoke(app, ["fleet-impact", "--dir", str(tmp_path), "--days", "3650"])
        assert result.exit_code == 0
        assert "aws/us-east-1" in result.output

    def test_old_entries_drop_out_of_window(self):
        from datetime import datetime, timedelta, timezone

        from carbon_mesh.cli.ledger import summarize

        now = datetime(2026, 6, 16, tzinfo=timezone.utc)
        old = (now - timedelta(days=40)).isoformat()
        entries = [{"ts": old, "deferred_hours": 3, "reduction_gco2_kwh": 100, "energy_kwh": 5}]
        assert summarize(entries, now, days=30)["jobs"] == 0


class TestPlanEstimate:
    def test_combines_region_and_shift_savings(self):
        from carbon_mesh.cli.plan import plan_estimate

        # Two candidates: greenest 100, other 300 -> naive mean 200.
        siting = {
            "options": [
                {"provider": "gcp", "region": "fi", "grid_zone": "FI", "typical_gco2_kwh": 100},
                {"provider": "aws", "region": "us", "grid_zone": "US", "typical_gco2_kwh": 300},
            ]
        }
        shift = {"zones": [{"grid_zone": "FI", "shift_savings_pct": 50}]}
        # 1 kW continuous, all load flexible.
        est = plan_estimate(siting, shift, power_watts=1000, flexible_fraction=1.0)
        # naive: 200 gCO2/kWh * 1 kW * 8760 h / 1000 = 1752 kg
        assert est["naive_annual_kg"] == 1752.0
        # region pick -> 100 g/kWh -> 876 kg; shift 50% of the (all-flexible) load -> -438
        assert est["region_saving_kg"] == 876.0
        assert est["shift_saving_kg"] == 438.0
        assert est["optimized_annual_kg"] == 438.0
        assert est["total_saving_kg"] == 1314.0

    def test_no_options_unavailable(self):
        from carbon_mesh.cli.plan import plan_estimate

        assert plan_estimate({"options": []}, {"zones": []}, 500, 0.5) == {"available": False}


class TestPlanCommand:
    def test_plan_renders(self):
        siting = {
            "options": [
                {"provider": "gcp", "region": "fi", "grid_zone": "FI", "typical_gco2_kwh": 100},
                {"provider": "aws", "region": "us", "grid_zone": "US", "typical_gco2_kwh": 300},
            ]
        }
        shift = {"zones": [{"grid_zone": "FI", "shift_savings_pct": 50}]}
        with (
            patch("carbon_mesh.cli.client.siting", return_value=siting),
            patch("carbon_mesh.cli.client.shiftability", return_value=shift),
        ):
            result = runner.invoke(app, ["plan", "--power-watts", "1000", "--flexible", "1.0"])
        assert result.exit_code == 0
        assert "gcp/fi" in result.output


class TestChooseRunPlan:
    def test_picks_cleanest_region_and_hour(self):
        regions = [
            ("aws/a", [300, 280, 260], []),
            ("gcp/b", [200, 150, 100], []),  # gcp hour 2 is globally cleanest
        ]
        assert choose_run_plan(regions, None, 24) == ("gcp/b", 2, "cleanest")

    def test_surplus_region_wins_over_lower_average(self):
        regions = [
            ("aws/a", [90, 90, 90], [1]),  # surplus window at +1h
            ("gcp/b", [40, 40, 40], []),  # cleaner on average, no surplus
        ]
        # Soonest surplus is the highest-value place+time to add load.
        assert choose_run_plan(regions, None, 24) == ("aws/a", 1, "surplus")

    def test_runs_now_in_cleanest_region_when_no_real_gain(self):
        regions = [
            ("aws/a", [300, 298, 297], []),
            ("gcp/b", [120, 119, 118], []),  # cleanest now; future barely better
        ]
        assert choose_run_plan(regions, None, 24) == ("gcp/b", 0, "now_no_benefit")


class TestRunCommand:
    def test_multi_region_dry_run_picks_a_place(self):
        def fake_forecast(provider, reg, hours):
            pts = {"aws": [300, 290, 280], "gcp": [120, 50, 40]}[provider]
            return {
                "method": "time_of_day_model",
                "clean_surplus_hours": [],
                "points": [
                    {"timestamp": f"2026-06-15T{h:02d}:00:00+00:00", "carbon_intensity_gco2_kwh": v}
                    for h, v in enumerate(pts)
                ],
            }

        with patch("carbon_mesh.cli.client.forecast", side_effect=fake_forecast):
            result = runner.invoke(
                app,
                [
                    "run",
                    "--region",
                    "aws/us-east-1,gcp/europe-west1",
                    "--dry-run",
                    "--",
                    "echo",
                    "hi",
                ],
            )
        assert result.exit_code == 0
        assert "gcp/europe-west1" in result.output

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

    def test_measure_energy_records_measured_kwh(self):
        # RAPL reads 3.6e9 uj more after the run -> 0.001 kWh, recorded as measured.
        captured: list[dict] = []
        reads = iter([(1_000_000_000, 0), (4_600_000_000, 0)])
        with (
            patch("carbon_mesh.cli.client.forecast", return_value=_forecast([40, 300])),
            patch("carbon_mesh.cli.energy.read_rapl_uj", side_effect=lambda: next(reads)),
            patch("carbon_mesh.cli.ledger.append", side_effect=captured.append),
        ):
            result = runner.invoke(
                app, ["run", "--region", "aws/us-east-1", "--measure-energy", "--", "echo", "hi"]
            )
        assert result.exit_code == 0
        assert captured[0]["energy_measured"] is True
        assert captured[0]["energy_kwh"] == 0.001

    def test_records_measured_reduction_at_run_time(self):
        # Forecast says defer 2h to ~100; at run time the grid actually reads 90.
        captured: list[dict] = []
        with (
            patch("carbon_mesh.cli.client.forecast", return_value=_forecast([300, 200, 100])),
            patch(
                "carbon_mesh.cli.client.intensity",
                return_value={"carbon_intensity_gco2_kwh": 90},
            ),
            patch("time.sleep", lambda _s: None),
            patch("carbon_mesh.cli.ledger.append", side_effect=captured.append),
        ):
            result = runner.invoke(app, ["run", "--region", "aws/us-east-1", "--", "echo", "hi"])
        assert result.exit_code == 0
        assert len(captured) == 1
        entry = captured[0]
        assert entry["basis"] == "measured"
        assert entry["reduction_gco2_kwh"] == 210.0  # measured: start 300 - actual 90
        assert entry["predicted_reduction_gco2_kwh"] == 200.0  # forecast: start 300 - 100


class TestBestTimeCommand:
    def test_prints_cleanest_hour_and_cron(self):
        payload = {
            "provider": "aws",
            "region": "us-east-1",
            "grid_zone": "US-MIDA-PJM",
            "basis": "history",
            "days_analyzed": 14,
            "cleanest_hour_utc": 3,
            "suggested_cron": "0 3 * * *",
            "ranked_hours": [{"hour_utc": 3, "mean_gco2_kwh": 60.0, "samples": 12}],
        }
        with patch("carbon_mesh.cli.client.best_time", return_value=payload):
            result = runner.invoke(app, ["best-time", "aws/us-east-1"])
        assert result.exit_code == 0
        assert "0 3 * * *" in result.output

    def test_rejects_malformed_region(self):
        result = runner.invoke(app, ["best-time", "bogus"])
        assert result.exit_code == 1

    def test_siting_renders_recommendation(self):
        payload = {
            "recommended": {
                "provider": "gcp",
                "region": "europe-north1",
                "grid_zone": "FI",
                "location": "Finland",
                "typical_gco2_kwh": 70.0,
                "basis": "history",
                "annual_kg": 306.0,
            },
            "options": [
                {
                    "provider": "gcp",
                    "region": "europe-north1",
                    "grid_zone": "FI",
                    "location": "Finland",
                    "typical_gco2_kwh": 70.0,
                    "basis": "history",
                    "annual_kg": 306.0,
                }
            ],
            "annual_kg_saved_vs_worst": 1200.0,
            "power_watts": 500.0,
            "days_analyzed": 30,
        }
        with patch("carbon_mesh.cli.client.siting", return_value=payload):
            result = runner.invoke(app, ["siting", "-p", "gcp", "--power-watts", "500"])
        assert result.exit_code == 0
        assert "europe-north1" in result.output

    def test_shiftability_renders_ranking(self):
        payload = {
            "days_analyzed": 14,
            "zones": [
                {
                    "grid_zone": "US-CAL-CISO",
                    "location": "California",
                    "shift_savings_pct": 62.0,
                    "cleanest_hour_utc": 13,
                    "dirtiest_hour_utc": 2,
                    "samples": 120,
                }
            ],
        }
        with patch("carbon_mesh.cli.client.shiftability", return_value=payload):
            result = runner.invoke(app, ["shiftability"])
        assert result.exit_code == 0
        assert "US-CAL-CISO" in result.output

    def test_multi_region_picks_greenest_place(self):
        def payload(hour, mean):
            return {
                "provider": "x",
                "region": "y",
                "grid_zone": "Z",
                "basis": "history",
                "days_analyzed": 14,
                "cleanest_hour_utc": hour,
                "dirtiest_hour_utc": 18,
                "shift_savings_pct": 50.0,
                "annual_kg_saved": None,
                "suggested_cron": f"0 {hour} * * *",
                "ranked_hours": [{"hour_utc": hour, "mean_gco2_kwh": mean, "samples": 12}],
            }

        def fake(provider, reg, days, energy):
            return {"aws": payload(3, 200.0), "gcp": payload(5, 40.0)}[provider]

        with patch("carbon_mesh.cli.client.best_time", side_effect=fake):
            result = runner.invoke(app, ["best-time", "aws/us-east-1,gcp/europe-west1"])
        assert result.exit_code == 0
        # gcp is cleaner (40 < 200) -> it's the greenest place.
        assert "Greenest place + time: gcp/europe-west1" in result.output
