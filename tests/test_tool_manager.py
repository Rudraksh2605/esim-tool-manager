"""
Tests for the eSim Tool Manager.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tool_manager.cli.commands import cli
from tool_manager.core.checker import ToolChecker, ToolStatus
from tool_manager.core.dependencies import DependencyChecker, DependencyStatus
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater, UpdateAction
from tool_manager.utils.os_utils import Platform, detect_platform, get_platform_key


@pytest.fixture
def sample_config():
    """A minimal tool registry used across tests."""

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
                "windows": "winget install kicad",
                "macos": "brew install --cask kicad",
            },
        },
    }


@pytest.fixture
def runner():
    return CliRunner()


class TestToolChecker:
    """Tests for core.checker.ToolChecker."""

    def test_check_tool_installed(self, sample_config):
        checker = ToolChecker(sample_config)
        mock_result = MagicMock(returncode=0, stdout="ngspice 39.3", stderr="")

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
        assert all(result.status == ToolStatus.MISSING for result in results)


class TestToolInstaller:
    """Tests for core.installer.ToolInstaller."""

    def test_install_tool_success(self, sample_config):
        installer = ToolInstaller(sample_config)
        mock_result = MagicMock(returncode=0, stdout="done", stderr="")

        with patch("tool_manager.core.installer.subprocess.run", return_value=mock_result):
            result = installer.install_tool("ngspice")

        assert result.success is True

    def test_install_tool_failure(self, sample_config):
        installer = ToolInstaller(sample_config)
        mock_result = MagicMock(returncode=1, stdout="", stderr="error")

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

    def test_install_tool_download_extract_success(self, sample_config):
        sample_config["ngspice"]["install"]["windows"] = ""
        sample_config["ngspice"]["download"] = {
            "windows": {
                "url": "https://example.com/ngspice.7z",
                "filename": "ngspice.7z",
                "type": "archive_extract",
                "archive_format": "7z",
                "bin_subdir": "bin",
            }
        }
        installer = ToolInstaller(sample_config)
        verify_result = MagicMock(returncode=0, stdout="ngspice 43", stderr="")

        with patch("tool_manager.core.installer.get_platform_key", return_value="windows"):
            with patch("tool_manager.utils.downloader.download_file", return_value=Path("C:/fake/ngspice.7z")):
                with patch(
                    "tool_manager.utils.downloader.extract_archive_and_install",
                    return_value=(True, "Installed ok.", Path("C:/fake/install"), Path("C:/fake/install/bin")),
                ):
                    with patch(
                        "tool_manager.utils.downloader.add_to_user_path",
                        return_value=(True, "Added to PATH."),
                    ):
                        with patch("tool_manager.core.installer.subprocess.run", return_value=verify_result):
                            result = installer.install_tool("ngspice")

        assert result.success is True
        assert result.installed_bin_dir is not None
        assert "bin" in result.installed_bin_dir


class TestDependencyChecker:
    """Tests for core.dependencies.DependencyChecker."""

    def test_tool_dependency_uses_download_config(self, sample_config):
        sample_config["ngspice"]["download"] = {
            "windows": {
                "url": "https://example.com/ngspice.exe",
                "filename": "ngspice.exe",
                "type": "exe_installer",
            }
        }
        checker = DependencyChecker(sample_config)

        with patch("tool_manager.core.dependencies.get_platform_key", return_value="windows"):
            results = checker.check_tool_dependencies(["ngspice"])

        assert any(
            result.tool_name == "ngspice"
            and result.status == DependencyStatus.OK
            and "Automatic install available" in result.message
            for result in results
        )

    def test_tool_dependency_reports_missing_package_manager(self, sample_config):
        checker = DependencyChecker(sample_config)

        with patch("tool_manager.core.dependencies.get_platform_key", return_value="windows"):
            with patch("tool_manager.core.dependencies.shutil.which", return_value=None):
                results = checker.check_tool_dependencies(["kicad"])

        assert any(
            result.tool_name == "kicad"
            and result.status == DependencyStatus.MISSING
            and "winget" in result.message
            for result in results
        )


class TestToolUpdater:
    """Tests for core.updater.ToolUpdater."""

    def test_up_to_date(self, sample_config):
        updater = ToolUpdater(
            sample_config,
            ToolChecker(sample_config),
            ToolInstaller(sample_config),
        )
        mock_result = MagicMock(returncode=0, stdout="ngspice 43.0", stderr="")

        with patch("tool_manager.core.checker.subprocess.run", return_value=mock_result):
            result = updater.check_update("ngspice")

        assert result.action == UpdateAction.UP_TO_DATE

    def test_update_available(self, sample_config):
        updater = ToolUpdater(
            sample_config,
            ToolChecker(sample_config),
            ToolInstaller(sample_config),
        )
        mock_result = MagicMock(returncode=0, stdout="ngspice 30.0", stderr="")

        with patch("tool_manager.core.checker.subprocess.run", return_value=mock_result):
            result = updater.check_update("ngspice")

        assert result.action == UpdateAction.UPDATE_AVAILABLE

    def test_not_installed(self, sample_config):
        updater = ToolUpdater(
            sample_config,
            ToolChecker(sample_config),
            ToolInstaller(sample_config),
        )

        with patch(
            "tool_manager.core.checker.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = updater.check_update("ngspice")

        assert result.action == UpdateAction.NOT_INSTALLED

    def test_unregistered_tool(self, sample_config):
        updater = ToolUpdater(
            sample_config,
            ToolChecker(sample_config),
            ToolInstaller(sample_config),
        )
        result = updater.check_update("xyz")
        assert result.action == UpdateAction.ERROR


class TestOsUtils:
    """Tests for utils.os_utils."""

    def test_detect_platform_returns_enum(self):
        assert isinstance(detect_platform(), Platform)

    def test_get_platform_key_returns_string(self):
        assert get_platform_key() in ("linux", "windows", "macos", "unsupported")


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

    def test_doctor_command(self, runner):
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        assert "Dependency Doctor" in result.output

    def test_install_dry_run(self, runner):
        result = runner.invoke(cli, ["--dry-run", "install", "ngspice"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    def test_install_unknown_tool(self, runner):
        result = runner.invoke(cli, ["install", "nonexistent_tool_xyz"])
        assert result.exit_code == 0
        assert "not registered" in result.output.lower()

    def test_update_check_only(self, runner):
        result = runner.invoke(cli, ["update", "--check-only", "ngspice"])
        assert result.exit_code == 0

    def test_verbose_flag(self, runner):
        result = runner.invoke(cli, ["-v", "check"])
        assert result.exit_code == 0
