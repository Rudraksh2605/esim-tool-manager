"""
Tool version and installation checks.
"""

from __future__ import annotations

import glob
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from tool_manager.utils.downloader import TOOLS_DIR, find_binary_directory
from tool_manager.utils.logger import get_logger

logger = get_logger("core.checker")


class ToolStatus(Enum):
    """Possible states for a managed tool."""

    INSTALLED = "installed"
    MISSING = "missing"
    ERROR = "error"


@dataclass
class CheckResult:
    """Result of checking a single tool."""

    tool_name: str
    status: ToolStatus
    version: Optional[str] = None
    raw_output: Optional[str] = None
    error_message: Optional[str] = None


class ToolChecker:
    """Check whether tools are installed and extract their versions."""

    def __init__(self, tools_config: dict, timeout: int = 30):
        self.tools_config = tools_config
        self.timeout = timeout

    def check_tool(self, tool_name: str) -> CheckResult:
        """Check one tool from the registry."""

        if tool_name not in self.tools_config:
            logger.warning("Tool '%s' not found in configuration.", tool_name)
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message=f"Tool '{tool_name}' is not registered in tools.json.",
            )

        tool_cfg = self.tools_config[tool_name]
        check_cmd = tool_cfg.get("check")
        if not check_cmd:
            logger.warning("No check command defined for '%s'.", tool_name)
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message="No 'check' command defined in configuration.",
            )

        logger.info("Checking tool: %s -> %s", tool_name, check_cmd)

        discovered_result = self._run_check_from_discovered_path(tool_name, tool_cfg, check_cmd)
        if discovered_result is not None:
            return discovered_result

        try:
            direct_result = self._run_check_command(check_cmd)
        except subprocess.TimeoutExpired:
            fallback_result = self._run_check_from_discovered_path(tool_name, tool_cfg, check_cmd)
            if fallback_result is not None:
                return fallback_result
            logger.warning("Check command for '%s' timed out.", tool_name)
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message=f"Check command timed out after {self.timeout}s.",
            )
        except Exception as exc:
            logger.exception("Unexpected error while checking '%s'.", tool_name)
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message=str(exc),
            )
        if direct_result is None:
            fallback_result = self._run_check_from_discovered_path(tool_name, tool_cfg, check_cmd)
            if fallback_result is not None:
                return fallback_result
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.MISSING,
                error_message="Command not found on PATH.",
            )

        if direct_result.returncode == 0:
            return self._build_installed_result(tool_name, tool_cfg, direct_result)

        fallback_result = self._run_check_from_discovered_path(tool_name, tool_cfg, check_cmd)
        if fallback_result is not None:
            return fallback_result

        logger.info(
            "Tool '%s' does not appear to be installed (exit code %d).",
            tool_name,
            direct_result.returncode,
        )
        combined_output = ((direct_result.stdout or "") + (direct_result.stderr or "")).strip()
        return CheckResult(
            tool_name=tool_name,
            status=ToolStatus.MISSING,
            raw_output=combined_output,
        )

    def check_all(self) -> list[CheckResult]:
        """Check every tool registered in the configuration."""

        return [self.check_tool(tool_name) for tool_name in self.tools_config]

    def _run_check_command(
        self,
        check_cmd: str,
        env: Optional[dict] = None,
    ) -> Optional[subprocess.CompletedProcess]:
        try:
            return subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=True,
                env=env,
            )
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            raise
        except Exception:
            raise

    def _run_check_from_discovered_path(
        self,
        tool_name: str,
        tool_cfg: dict,
        check_cmd: str,
    ) -> Optional[CheckResult]:
        try:
            binary_dir = self._discover_binary_dir(tool_name, tool_cfg)
        except Exception as exc:
            logger.warning("Binary discovery failed for '%s': %s", tool_name, exc)
            return None

        if not binary_dir:
            return None

        env = os.environ.copy()
        env["PATH"] = binary_dir + os.pathsep + env.get("PATH", "")

        try:
            direct_result = self._run_check_command_direct(binary_dir, tool_cfg, check_cmd)
        except subprocess.TimeoutExpired:
            direct_result = None
        except Exception as exc:
            logger.debug("Direct binary check failed for '%s': %s", tool_name, exc)
            direct_result = None

        if direct_result is not None and direct_result.returncode == 0:
            logger.info("Tool '%s' found via direct binary path: %s", tool_name, binary_dir)
            return self._build_installed_result(tool_name, tool_cfg, direct_result)

        try:
            result = self._run_check_command(check_cmd, env=env)
        except subprocess.TimeoutExpired:
            logger.warning("Check command for '%s' timed out.", tool_name)
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message=f"Check command timed out after {self.timeout}s.",
            )
        except Exception as exc:
            logger.exception("Unexpected error while checking '%s'.", tool_name)
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error_message=str(exc),
            )

        if result is None:
            return None
        if result.returncode != 0:
            return None

        logger.info("Tool '%s' found via discovered path: %s", tool_name, binary_dir)
        return self._build_installed_result(tool_name, tool_cfg, result)

    def _run_check_command_direct(
        self,
        binary_dir: str,
        tool_cfg: dict,
        check_cmd: str,
    ) -> Optional[subprocess.CompletedProcess]:
        binary_path = self._find_binary_path(binary_dir, tool_cfg.get("binary_names", []))
        if not binary_path:
            return None

        try:
            args = shlex.split(check_cmd, posix=False)
        except ValueError:
            args = check_cmd.split()

        if not args:
            return None

        args[0] = str(binary_path)
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            shell=False,
        )

    def _build_installed_result(
        self,
        tool_name: str,
        tool_cfg: dict,
        result: subprocess.CompletedProcess,
    ) -> CheckResult:
        combined_output = ((result.stdout or "") + (result.stderr or "")).strip()
        version = self._extract_version(combined_output, tool_cfg)
        logger.info("Tool '%s' found. Version: %s", tool_name, version or "unknown")
        return CheckResult(
            tool_name=tool_name,
            status=ToolStatus.INSTALLED,
            version=version,
            raw_output=combined_output,
        )

    def _discover_binary_dir(self, tool_name: str, tool_cfg: dict) -> Optional[str]:
        binary_names = tool_cfg.get("binary_names", [])
        if not binary_names:
            return None

        managed_root = TOOLS_DIR / tool_name
        if managed_root.exists():
            return str(
                find_binary_directory(
                    managed_root,
                    binary_names=binary_names,
                    preferred_subdir="bin",
                )
            )

        for raw_pattern in tool_cfg.get("path_globs", []):
            for match in glob.glob(os.path.expandvars(raw_pattern)):
                candidate = Path(match)
                if candidate.is_file():
                    return str(candidate.parent)
                if candidate.is_dir() and any((candidate / name).exists() for name in binary_names):
                    return str(candidate)

        for raw_path in tool_cfg.get("path_hints", []):
            candidate = Path(os.path.expandvars(raw_path))
            if candidate.is_file():
                return str(candidate.parent)
            if candidate.is_dir() and any((candidate / name).exists() for name in binary_names):
                return str(candidate)

        return None

    @staticmethod
    def _find_binary_path(binary_dir: str, binary_names: list[str]) -> Optional[Path]:
        directory = Path(binary_dir)
        for name in binary_names:
            candidate = directory / name
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _extract_version(output: str, tool_cfg: dict) -> Optional[str]:
        """Extract a version string from command output."""

        pattern = tool_cfg.get("version_regex") or r"(\d+\.\d+[\w.-]*)"
        match = re.search(pattern, output)
        return match.group(1) if match else None
