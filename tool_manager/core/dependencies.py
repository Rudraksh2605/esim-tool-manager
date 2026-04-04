"""
Dependency checks for install prerequisites and local environment readiness.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from tool_manager.utils.logger import get_logger
from tool_manager.utils.os_utils import get_platform_key, is_admin

logger = get_logger("core.dependencies")

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


class DependencyStatus(Enum):
    """Possible states for an environment dependency."""

    OK = "ok"
    WARNING = "warning"
    MISSING = "missing"


@dataclass
class DependencyResult:
    """Result of checking a single dependency or install prerequisite."""

    name: str
    status: DependencyStatus
    message: str
    tool_name: Optional[str] = None


class DependencyChecker:
    """Inspect the local environment for installer and runtime prerequisites."""

    KNOWN_PACKAGE_MANAGERS = {
        "apt": "APT package manager",
        "apt-get": "APT package manager",
        "brew": "Homebrew",
        "winget": "Windows Package Manager",
        "choco": "Chocolatey",
    }

    def __init__(self, tools_config: dict):
        self.tools_config = tools_config

    def check_system_dependencies(self) -> list[DependencyResult]:
        """Check workspace-level prerequisites."""

        platform_key = get_platform_key()
        results = [
            self._platform_result(platform_key),
            self._python_result(),
            self._logs_directory_result(),
        ]

        for manager in sorted(self._required_package_managers(platform_key)):
            label = self.KNOWN_PACKAGE_MANAGERS.get(manager, manager)
            results.append(
                self._command_result(
                    command_name=manager,
                    name=label,
                    message_prefix="Needed for automatic installs on this platform",
                )
            )

        if platform_key == "windows" and not is_admin():
            results.append(
                DependencyResult(
                    name="Administrator access",
                    status=DependencyStatus.WARNING,
                    message="Some installers may prompt for elevation.",
                )
            )

        if platform_key == "windows" and not os.environ.get("LOCALAPPDATA"):
            results.append(
                DependencyResult(
                    name="LOCALAPPDATA",
                    status=DependencyStatus.WARNING,
                    message="Download installs will fall back to a temp directory.",
                )
            )

        return results

    def check_tool_dependencies(
        self,
        tool_names: Optional[list[str]] = None,
    ) -> list[DependencyResult]:
        """Check install prerequisites for one or more configured tools."""

        platform_key = get_platform_key()
        names = tool_names or list(self.tools_config.keys())
        results: list[DependencyResult] = []

        for tool_name in names:
            tool_cfg = self.tools_config.get(tool_name)
            if not tool_cfg:
                results.append(
                    DependencyResult(
                        name="Tool registration",
                        status=DependencyStatus.MISSING,
                        message=f"Tool '{tool_name}' is not registered in tools.json.",
                        tool_name=tool_name,
                    )
                )
                continue

            install_cmd = tool_cfg.get("install", {}).get(platform_key, "").strip()
            download_cfg = tool_cfg.get("download", {}).get(platform_key)
            explicit_dependencies = tool_cfg.get("dependencies", {}).get(platform_key, [])

            if download_cfg:
                download_type = download_cfg.get("type", "download")
                results.append(
                    DependencyResult(
                        name="Install method",
                        status=DependencyStatus.OK,
                        message=f"Automatic install available via {download_type}.",
                        tool_name=tool_name,
                    )
                )
            elif install_cmd:
                command_name = self._command_name_from_install(install_cmd)
                if command_name:
                    label = self.KNOWN_PACKAGE_MANAGERS.get(command_name, command_name)
                    results.append(
                        self._command_result(
                            command_name=command_name,
                            name="Install method",
                            message_prefix=f"Automatic install uses {label}",
                            tool_name=tool_name,
                        )
                    )
                else:
                    results.append(
                        DependencyResult(
                            name="Install method",
                            status=DependencyStatus.WARNING,
                            message="Automatic install command exists but could not be parsed.",
                            tool_name=tool_name,
                        )
                    )
            else:
                results.append(
                    DependencyResult(
                        name="Install method",
                        status=DependencyStatus.WARNING,
                        message=f"No automatic installer is configured for {platform_key}.",
                        tool_name=tool_name,
                    )
                )

            for dependency_name in explicit_dependencies:
                results.append(
                    self._command_result(
                        command_name=dependency_name,
                        name=f"Dependency: {dependency_name}",
                        message_prefix="Required by this tool",
                        tool_name=tool_name,
                    )
                )

        return results

    def _required_package_managers(self, platform_key: str) -> set[str]:
        managers: set[str] = set()
        for tool_cfg in self.tools_config.values():
            install_cmd = tool_cfg.get("install", {}).get(platform_key, "").strip()
            if not install_cmd:
                continue
            command_name = self._command_name_from_install(install_cmd)
            if command_name in self.KNOWN_PACKAGE_MANAGERS:
                managers.add(command_name)
        return managers

    @staticmethod
    def _command_name_from_install(install_cmd: str) -> Optional[str]:
        if not install_cmd:
            return None
        token = install_cmd.split()[0].strip().strip("\"'")
        return token.lower() or None

    @staticmethod
    def _platform_result(platform_key: str) -> DependencyResult:
        if platform_key == "unsupported":
            return DependencyResult(
                name="Platform support",
                status=DependencyStatus.MISSING,
                message="This operating system is not supported yet.",
            )
        return DependencyResult(
            name="Platform support",
            status=DependencyStatus.OK,
            message=f"Detected supported platform: {platform_key}.",
        )

    @staticmethod
    def _python_result() -> DependencyResult:
        version_label = (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )
        if sys.version_info >= (3, 10):
            return DependencyResult(
                name="Python runtime",
                status=DependencyStatus.OK,
                message=f"Python {version_label} is supported.",
            )
        return DependencyResult(
            name="Python runtime",
            status=DependencyStatus.MISSING,
            message=f"Python {version_label} is below the required 3.10 baseline.",
        )

    @staticmethod
    def _logs_directory_result() -> DependencyResult:
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            test_path = _LOG_DIR / ".write_test"
            test_path.write_text("ok", encoding="utf-8")
            test_path.unlink()
            return DependencyResult(
                name="Logs directory",
                status=DependencyStatus.OK,
                message=f"Writable at {_LOG_DIR}.",
            )
        except OSError as exc:
            return DependencyResult(
                name="Logs directory",
                status=DependencyStatus.WARNING,
                message=f"Could not verify write access to {_LOG_DIR}: {exc}",
            )

    def _command_result(
        self,
        command_name: str,
        name: str,
        message_prefix: str,
        tool_name: Optional[str] = None,
    ) -> DependencyResult:
        command_path = shutil.which(command_name)
        if command_path:
            logger.debug("Dependency '%s' resolved to %s", command_name, command_path)
            return DependencyResult(
                name=name,
                status=DependencyStatus.OK,
                message=f"{message_prefix}. Found at {command_path}.",
                tool_name=tool_name,
            )
        return DependencyResult(
            name=name,
            status=DependencyStatus.MISSING,
            message=f"{message_prefix}, but '{command_name}' is not on PATH.",
            tool_name=tool_name,
        )
