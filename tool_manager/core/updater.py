"""
Tool update workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

from packaging.version import InvalidVersion, Version

from tool_manager.core.checker import ToolChecker, ToolStatus
from tool_manager.core.installer import InstallResult, ToolInstaller
from tool_manager.utils.logger import get_logger

logger = get_logger("core.updater")


class UpdateAction(Enum):
    """Possible outcomes of an update check."""

    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    UPDATED = "updated"
    NOT_INSTALLED = "not_installed"
    ERROR = "error"


@dataclass
class UpdateResult:
    """Outcome of an update check or update attempt."""

    tool_name: str
    action: UpdateAction
    current_version: Optional[str] = None
    latest_version: Optional[str] = None
    message: str = ""
    install_result: Optional[InstallResult] = None


class ToolUpdater:
    """Coordinate version comparison and update execution."""

    def __init__(self, tools_config: dict, checker: ToolChecker, installer: ToolInstaller):
        self.tools_config = tools_config
        self.checker = checker
        self.installer = installer

    def check_update(self, tool_name: str) -> UpdateResult:
        """Compare installed and target versions without updating."""

        if tool_name not in self.tools_config:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.ERROR,
                message=f"Tool '{tool_name}' is not registered.",
            )

        tool_cfg = self.tools_config[tool_name]
        latest_version = tool_cfg.get("latest_version")
        check_result = self.checker.check_tool(tool_name)

        if check_result.status == ToolStatus.MISSING:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.NOT_INSTALLED,
                latest_version=latest_version,
                message=f"'{tool_name}' is not installed.",
            )

        if check_result.status == ToolStatus.ERROR:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.ERROR,
                message=check_result.error_message or "Unknown check error.",
            )

        current_version = check_result.version
        if not latest_version:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.ERROR,
                current_version=current_version,
                latest_version=latest_version,
                message="Unable to determine latest version from config.",
            )

        if not current_version:
            # Tool is installed but version parsing failed. Offer update anyway.
            message = (
                f"Update available for '{tool_name}': "
                f"Unknown -> {latest_version}"
            )
            logger.info("Version parsing failed for '%s'. Offering update anyway.", tool_name)
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.UPDATE_AVAILABLE,
                current_version=current_version,
                latest_version=latest_version,
                message=message,
            )

        if self._version_less_than(current_version, latest_version):
            message = (
                f"Update available for '{tool_name}': "
                f"{current_version} -> {latest_version}"
            )
            logger.info(message)
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.UPDATE_AVAILABLE,
                current_version=current_version,
                latest_version=latest_version,
                message=message,
            )

        message = f"'{tool_name}' is up to date (v{current_version})."
        logger.info(message)
        return UpdateResult(
            tool_name=tool_name,
            action=UpdateAction.UP_TO_DATE,
            current_version=current_version,
            latest_version=latest_version,
            message=message,
        )

    def update_tool(
        self,
        tool_name: str,
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> UpdateResult:
        """Install the configured target version if an update is available."""

        check_result = self.check_update(tool_name)
        if check_result.action != UpdateAction.UPDATE_AVAILABLE:
            return check_result

        logger.info(
            "Updating '%s' from %s -> %s ...",
            tool_name,
            check_result.current_version,
            check_result.latest_version,
        )
        install_result = self.installer.install_tool(
            tool_name,
            status_callback=status_callback,
            progress_callback=progress_callback,
        )

        if install_result.success:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.UPDATED,
                current_version=check_result.current_version,
                latest_version=check_result.latest_version,
                message=f"Successfully updated '{tool_name}'.",
                install_result=install_result,
            )

        return UpdateResult(
            tool_name=tool_name,
            action=UpdateAction.ERROR,
            current_version=check_result.current_version,
            latest_version=check_result.latest_version,
            message=f"Update failed: {install_result.message}",
            install_result=install_result,
        )

    def check_all_updates(self) -> list[UpdateResult]:
        """Check update status for every configured tool."""

        return [self.check_update(tool_name) for tool_name in self.tools_config]

    @staticmethod
    def _version_less_than(current: str, latest: str) -> bool:
        """Compare version strings using packaging with a string fallback."""

        try:
            return Version(current) < Version(latest)
        except InvalidVersion:
            try:
                return Version(current.lstrip("vV")) < Version(latest.lstrip("vV"))
            except InvalidVersion:
                logger.debug(
                    "Could not parse versions ('%s', '%s'); using string comparison.",
                    current,
                    latest,
                )
                return current != latest
