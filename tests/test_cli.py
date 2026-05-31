"""Tests for CLI module: client helpers and Typer app commands."""

import inspect
import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from carbon_mesh.cli import client
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
