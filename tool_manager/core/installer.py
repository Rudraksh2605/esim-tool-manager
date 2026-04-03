"""
Tool Installer Module.

Handles the execution of OS-specific installation commands for managed tools.
Supports dry-run mode and provides structured feedback on success/failure.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional

from tool_manager.utils.logger import get_logger
from tool_manager.utils.os_utils import get_platform_key, detect_platform, Platform

logger = get_logger("core.installer")


@dataclass
class InstallResult:
    """Outcome of an installation attempt."""
    tool_name: str
    success: bool
    message: str
    command_executed: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    return_code: Optional[int] = None


class ToolInstaller:
    """
    Executes platform-specific install commands for registered tools.

    Attributes:
        tools_config (dict): The tool registry from tools.json.
        dry_run (bool): If True, print commands without executing them.
        timeout (int): Maximum seconds to wait for an install command.
    """

    def __init__(
        self,
        tools_config: dict,
        dry_run: bool = False,
        timeout: int = 300,
    ):
        self.tools_config = tools_config
        self.dry_run = dry_run
        self.timeout = timeout

    def install_tool(self, tool_name: str) -> InstallResult:
        """
        Install a single tool using its platform-specific command.

        Args:
            tool_name: Key from tools.json.

        Returns:
            InstallResult with execution details.
        """
        if tool_name not in self.tools_config:
            msg = f"Tool '{tool_name}' is not registered in tools.json."
            logger.error(msg)
            return InstallResult(tool_name=tool_name, success=False, message=msg)

        tool_cfg = self.tools_config[tool_name]
        install_cmds = tool_cfg.get("install", {})
        platform_key = get_platform_key()
        cmd = install_cmds.get(platform_key)

        if not cmd:
            msg = (
                f"No install command defined for '{tool_name}' "
                f"on platform '{platform_key}'."
            )
            logger.warning(msg)
            return InstallResult(tool_name=tool_name, success=False, message=msg)

        logger.info(
            "Installing '%s' on %s  →  %s",
            tool_name,
            platform_key,
            cmd,
        )

        if self.dry_run:
            msg = f"[DRY RUN] Would execute: {cmd}"
            logger.info(msg)
            return InstallResult(
                tool_name=tool_name,
                success=True,
                message=msg,
                command_executed=cmd,
            )

        return self._execute(tool_name, cmd)

    def install_all(self, tool_names: Optional[list[str]] = None) -> list[InstallResult]:
        """
        Install multiple tools. Defaults to all registered tools.

        Args:
            tool_names: Optional list of tool keys. If None, install everything.

        Returns:
            List of InstallResult objects.
        """
        names = tool_names or list(self.tools_config.keys())
        results = []
        for name in names:
            results.append(self.install_tool(name))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute(self, tool_name: str, cmd: str) -> InstallResult:
        """Run an install command and capture its outcome."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=True,
            )

            if result.returncode == 0:
                msg = f"Successfully installed '{tool_name}'."
                logger.info(msg)
            else:
                msg = (
                    f"Installation of '{tool_name}' exited with code "
                    f"{result.returncode}."
                )
                logger.warning(msg)

            return InstallResult(
                tool_name=tool_name,
                success=result.returncode == 0,
                message=msg,
                command_executed=cmd,
                stdout=result.stdout.strip() if result.stdout else None,
                stderr=result.stderr.strip() if result.stderr else None,
                return_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            msg = f"Install command for '{tool_name}' timed out after {self.timeout}s."
            logger.error(msg)
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=msg,
                command_executed=cmd,
            )
        except PermissionError:
            msg = (
                f"Permission denied while installing '{tool_name}'. "
                f"Try running with elevated privileges."
            )
            logger.error(msg)
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=msg,
                command_executed=cmd,
            )
        except Exception as exc:
            msg = f"Unexpected error installing '{tool_name}': {exc}"
            logger.exception(msg)
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=msg,
                command_executed=cmd,
            )
