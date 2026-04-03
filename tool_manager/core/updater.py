"""
Tool Update Manager.

Compares the currently installed version of a tool against its declared
latest version in tools.json and simulates an update workflow.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from packaging.version import Version, InvalidVersion

from tool_manager.core.checker import ToolChecker, ToolStatus
from tool_manager.core.installer import ToolInstaller, InstallResult
from tool_manager.utils.logger import get_logger

logger = get_logger("core.updater")


class UpdateAction(Enum):
    """Result classification for an update check."""
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    UPDATED = "updated"
    NOT_INSTALLED = "not_installed"
    ERROR = "error"


@dataclass
class UpdateResult:
    """Outcome of an update check / update attempt."""
    tool_name: str
    action: UpdateAction
    current_version: Optional[str] = None
    latest_version: Optional[str] = None
    message: str = ""
    install_result: Optional[InstallResult] = None


class ToolUpdater:
    """
    Coordinates version comparison and update execution.

    Attributes:
        tools_config (dict): Tool registry from tools.json.
        checker (ToolChecker): Checker instance for version detection.
        installer (ToolInstaller): Installer instance for reinstallation.
    """

    def __init__(
        self,
        tools_config: dict,
        checker: ToolChecker,
        installer: ToolInstaller,
    ):
        self.tools_config = tools_config
        self.checker = checker
        self.installer = installer

    def check_update(self, tool_name: str) -> UpdateResult:
        """
        Compare installed vs latest version without performing an update.

        Args:
            tool_name: Key from tools.json.

        Returns:
            UpdateResult indicating whether an update is available.
        """
        if tool_name not in self.tools_config:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.ERROR,
                message=f"Tool '{tool_name}' is not registered.",
            )

        tool_cfg = self.tools_config[tool_name]
        latest_version_str = tool_cfg.get("latest_version")

        check_result = self.checker.check_tool(tool_name)

        if check_result.status == ToolStatus.MISSING:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.NOT_INSTALLED,
                latest_version=latest_version_str,
                message=f"'{tool_name}' is not installed.",
            )

        if check_result.status == ToolStatus.ERROR:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.ERROR,
                message=check_result.error_message or "Unknown check error.",
            )

        current = check_result.version
        if not current or not latest_version_str:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.ERROR,
                current_version=current,
                latest_version=latest_version_str,
                message="Unable to compare versions (missing data).",
            )

        needs_update = self._version_less_than(current, latest_version_str)

        if needs_update:
            msg = (
                f"Update available for '{tool_name}': "
                f"{current} → {latest_version_str}"
            )
            logger.info(msg)
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.UPDATE_AVAILABLE,
                current_version=current,
                latest_version=latest_version_str,
                message=msg,
            )

        msg = f"'{tool_name}' is up to date (v{current})."
        logger.info(msg)
        return UpdateResult(
            tool_name=tool_name,
            action=UpdateAction.UP_TO_DATE,
            current_version=current,
            latest_version=latest_version_str,
            message=msg,
        )

    def update_tool(self, tool_name: str) -> UpdateResult:
        """
        Check for an update and, if one is available, reinstall the tool.

        This simulates a real update by re-running the install command.

        Args:
            tool_name: Key from tools.json.

        Returns:
            UpdateResult with install outcome attached.
        """
        check = self.check_update(tool_name)

        if check.action != UpdateAction.UPDATE_AVAILABLE:
            return check

        logger.info("Updating '%s' from %s → %s …", 
                     tool_name, check.current_version, check.latest_version)

        install_result = self.installer.install_tool(tool_name)

        if install_result.success:
            return UpdateResult(
                tool_name=tool_name,
                action=UpdateAction.UPDATED,
                current_version=check.current_version,
                latest_version=check.latest_version,
                message=f"Successfully updated '{tool_name}'.",
                install_result=install_result,
            )

        return UpdateResult(
            tool_name=tool_name,
            action=UpdateAction.ERROR,
            current_version=check.current_version,
            latest_version=check.latest_version,
            message=f"Update failed: {install_result.message}",
            install_result=install_result,
        )

    def check_all_updates(self) -> list[UpdateResult]:
        """Check update status for every registered tool."""
        return [self.check_update(name) for name in self.tools_config]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _version_less_than(current: str, latest: str) -> bool:
        """
        Compare two version strings.

        Uses PEP 440 parsing via ``packaging``. Falls back to naive
        string comparison if versions are non-standard.
        """
        try:
            return Version(current) < Version(latest)
        except InvalidVersion:
            # Fallback: strip non-numeric prefixes and try again
            try:
                cur_clean = current.lstrip("vV")
                lat_clean = latest.lstrip("vV")
                return Version(cur_clean) < Version(lat_clean)
            except InvalidVersion:
                logger.debug(
                    "Could not parse versions ('%s', '%s'); using string comparison.",
                    current,
                    latest,
                )
                return current != latest
