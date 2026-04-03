"""
Tool Version Checker.

Runs tool-specific check commands, captures output, extracts version strings,
and determines the installation status of each registered tool.
"""

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from tool_manager.utils.logger import get_logger
from tool_manager.utils.os_utils import get_shell_command_prefix, detect_platform, Platform

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
    """
    Checks whether managed tools are installed and extracts their versions.

    Attributes:
        tools_config (dict): The full tool registry loaded from tools.json.
        timeout (int): Maximum seconds to wait for a check command.
    """

    def __init__(self, tools_config: dict, timeout: int = 15):
        self.tools_config = tools_config
        self.timeout = timeout

    def check_tool(self, tool_name: str) -> CheckResult:
        """
        Check a single tool's installation status.

        Args:
            tool_name: Name of the tool (key in tools.json).

        Returns:
            CheckResult with status, version, and diagnostic info.
        """
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

        logger.info("Checking tool: %s  →  %s", tool_name, check_cmd)

        try:
            current = detect_platform()
            if current == Platform.WINDOWS:
                result = subprocess.run(
                    check_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=True,
                )
            else:
                result = subprocess.run(
                    check_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=True,
                )

            combined_output = (result.stdout or "") + (result.stderr or "")
            combined_output = combined_output.strip()

            if result.returncode == 0 or combined_output:
                version = self._extract_version(combined_output, tool_cfg)
                logger.info(
                    "Tool '%s' found. Version: %s", tool_name, version or "unknown"
                )
                return CheckResult(
                    tool_name=tool_name,
                    status=ToolStatus.INSTALLED,
                    version=version,
                    raw_output=combined_output,
                )
            else:
                logger.info("Tool '%s' does not appear to be installed.", tool_name)
                return CheckResult(
                    tool_name=tool_name,
                    status=ToolStatus.MISSING,
                    raw_output=combined_output,
                )

        except FileNotFoundError:
            logger.info("Tool '%s' binary not found on PATH.", tool_name)
            return CheckResult(
                tool_name=tool_name,
                status=ToolStatus.MISSING,
                error_message="Command not found on PATH.",
            )
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

    def check_all(self) -> list[CheckResult]:
        """
        Check every tool registered in the configuration.

        Returns:
            List of CheckResult objects, one per tool.
        """
        results = []
        for tool_name in self.tools_config:
            results.append(self.check_tool(tool_name))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_version(output: str, tool_cfg: dict) -> Optional[str]:
        """
        Extract version string from command output using the configured regex.

        Falls back to a generic semver-like pattern if no regex is configured.
        """
        pattern = tool_cfg.get("version_regex")
        if not pattern:
            pattern = r"(\d+\.\d+[\w.-]*)"

        match = re.search(pattern, output)
        if match:
            return match.group(1)
        return None
