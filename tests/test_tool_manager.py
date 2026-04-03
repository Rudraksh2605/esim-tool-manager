"""
Tests for eSim Tool Manager.

Covers core modules (checker, installer, updater), CLI commands via CliRunner,
and utility helpers. Uses mocked subprocess calls to avoid real installations.
"""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from tool_manager.cli.commands import cli
from tool_manager.core.checker import ToolChecker, ToolStatus
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater, UpdateAction
from tool_manager.utils.os_utils import detect_platform, Platform, get_platform_key


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_config():
    """A minimal tool config for tests."""
    return {
        "ngspice": {
            "description": "Circuit simulator",
            "category": "simulator",
            "check": "ngspice -v",
            "version_regex": r"\b(\d+\.\d+[\w.-]*)\b",
            "latest_version": "43",
            "install": {
                "linux": "sudo apt install ngspice -y",
                "windows": "echo installed ngspice",
                "macos": "brew install ngspice",
            },
        },
        "kicad": {
            "description": "EDA suite",
            "category": "eda",
            "check": "kicad-cli version",
            "version_regex": r"\b(\d+\.\d+[\w.-]*)\b",
            "latest_version": "8.0",
            "install": {
                "linux": "sudo apt install kicad -y",
                "windows": "echo installed kicad",
                "macos": "brew install --cask kicad",
            },
        },
    }


@pytest.fixture
def runner():
    return CliRunner()


# ── Checker Tests ─────────────────────────────────────────────────────────

class TestToolChecker:
    """Tests for core.checker.ToolChecker."""

    def test_check_tool_installed(self, sample_config):
        checker = ToolChecker(sample_config)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ngspice 39.3"
        mock_result.stderr = ""

        with patch("tool_manager.core.checker.subprocess.run", return_value=mock_result):
            result = checker.check_tool("ngspice")

        assert result.status == ToolStatus.INSTALLED
        assert result.version is not None
        assert "39" in result.version

    def test_check_tool_missing(self, sample_config):
        checker = ToolChecker(sample_config)

        with patch(
            "tool_manager.core.checker.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = checker.check_tool("ngspice")

        assert result.status == ToolStatus.MISSING

    def test_check_tool_not_registered(self, sample_config):
        checker = ToolChecker(sample_config)
        result = checker.check_tool("nonexistent")
        assert result.status == ToolStatus.ERROR

    def test_check_tool_timeout(self, sample_config):
        checker = ToolChecker(sample_config, timeout=1)

        with patch(
            "tool_manager.core.checker.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="test", timeout=1),
        ):
            result = checker.check_tool("ngspice")

        assert result.status == ToolStatus.ERROR
        assert "timed out" in result.error_message

    def test_check_all(self, sample_config):
        checker = ToolChecker(sample_config)

        with patch(
            "tool_manager.core.checker.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            results = checker.check_all()

        assert len(results) == 2
        assert all(r.status == ToolStatus.MISSING for r in results)


# ── Installer Tests ───────────────────────────────────────────────────────

class TestToolInstaller:
    """Tests for core.installer.ToolInstaller."""

    def test_install_tool_success(self, sample_config):
        installer = ToolInstaller(sample_config)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "done"
        mock_result.stderr = ""

        with patch("tool_manager.core.installer.subprocess.run", return_value=mock_result):
            result = installer.install_tool("ngspice")

        assert result.success is True

    def test_install_tool_failure(self, sample_config):
        installer = ToolInstaller(sample_config)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"

        with patch("tool_manager.core.installer.subprocess.run", return_value=mock_result):
            result = installer.install_tool("ngspice")

        assert result.success is False

    def test_install_tool_not_registered(self, sample_config):
        installer = ToolInstaller(sample_config)
        result = installer.install_tool("foobar")
        assert result.success is False

    def test_dry_run_mode(self, sample_config):
        installer = ToolInstaller(sample_config, dry_run=True)
        result = installer.install_tool("ngspice")
        assert result.success is True
        assert "DRY RUN" in result.message

    def test_install_permission_error(self, sample_config):
        installer = ToolInstaller(sample_config)

        with patch(
            "tool_manager.core.installer.subprocess.run",
            side_effect=PermissionError("access denied"),
        ):
            result = installer.install_tool("ngspice")

        assert result.success is False
        assert "Permission" in result.message


# ── Updater Tests ─────────────────────────────────────────────────────────

class TestToolUpdater:
    """Tests for core.updater.ToolUpdater."""

    def test_up_to_date(self, sample_config):
        checker = ToolChecker(sample_config)
        installer = ToolInstaller(sample_config)
        updater = ToolUpdater(sample_config, checker, installer)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ngspice 43.0"
        mock_result.stderr = ""

        with patch("tool_manager.core.checker.subprocess.run", return_value=mock_result):
            result = updater.check_update("ngspice")

        assert result.action == UpdateAction.UP_TO_DATE

    def test_update_available(self, sample_config):
        checker = ToolChecker(sample_config)
        installer = ToolInstaller(sample_config)
        updater = ToolUpdater(sample_config, checker, installer)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ngspice 30.0"
        mock_result.stderr = ""

        with patch("tool_manager.core.checker.subprocess.run", return_value=mock_result):
            result = updater.check_update("ngspice")

        assert result.action == UpdateAction.UPDATE_AVAILABLE

    def test_not_installed(self, sample_config):
        checker = ToolChecker(sample_config)
        installer = ToolInstaller(sample_config)
        updater = ToolUpdater(sample_config, checker, installer)

        with patch(
            "tool_manager.core.checker.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = updater.check_update("ngspice")

        assert result.action == UpdateAction.NOT_INSTALLED

    def test_unregistered_tool(self, sample_config):
        checker = ToolChecker(sample_config)
        installer = ToolInstaller(sample_config)
        updater = ToolUpdater(sample_config, checker, installer)
        result = updater.check_update("xyz")
        assert result.action == UpdateAction.ERROR


# ── OS Utility Tests ──────────────────────────────────────────────────────

class TestOsUtils:
    """Tests for utils.os_utils."""

    def test_detect_platform_returns_enum(self):
        plat = detect_platform()
        assert isinstance(plat, Platform)

    def test_get_platform_key_returns_string(self):
        key = get_platform_key()
        assert key in ("linux", "windows", "macos", "unsupported")


# ── CLI Integration Tests ────────────────────────────────────────────────

class TestCLI:
    """End-to-end CLI tests using Click's test runner."""

    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "eSim Tool Manager" in result.output

    def test_list_command(self, runner):
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "ngspice" in result.output.lower()

    def test_check_command(self, runner):
        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0

    def test_status_command(self, runner):
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_install_dry_run(self, runner):
        result = runner.invoke(cli, ["--dry-run", "install", "ngspice"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    def test_install_unknown_tool(self, runner):
        result = runner.invoke(cli, ["install", "nonexistent_tool_xyz"])
        assert result.exit_code == 0  # graceful failure, no crash
        assert "not registered" in result.output.lower()

    def test_update_check_only(self, runner):
        result = runner.invoke(cli, ["update", "--check-only", "ngspice"])
        assert result.exit_code == 0

    def test_verbose_flag(self, runner):
        result = runner.invoke(cli, ["-v", "check"])
        assert result.exit_code == 0
