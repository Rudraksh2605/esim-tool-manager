"""
OS Detection and Platform Utilities.

Provides platform-aware functionality for determining the current operating
system and selecting the correct tool commands for that platform.
"""

import platform
from enum import Enum
from typing import Optional


class Platform(Enum):
    """Supported operating system platforms."""
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"
    UNSUPPORTED = "unsupported"


def detect_platform() -> Platform:
    """
    Detect the current operating system.

    Returns:
        Platform: The detected platform enum value.
    """
    system = platform.system().lower()
    mapping = {
        "linux": Platform.LINUX,
        "windows": Platform.WINDOWS,
        "darwin": Platform.MACOS,
    }
    return mapping.get(system, Platform.UNSUPPORTED)


def get_platform_key() -> str:
    """
    Get the platform key string used in tools.json configuration.

    Returns:
        str: Platform key ('linux', 'windows', or 'macos').
    """
    return detect_platform().value


def get_platform_info() -> dict:
    """
    Gather detailed platform information for diagnostics.

    Returns:
        dict: Dictionary containing system, node, release, version,
              machine, and processor information.
    """
    return {
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }


def get_shell_command_prefix() -> list:
    """
    Get the shell prefix for executing commands on the current platform.

    On Windows, commands run through cmd.exe /c.
    On Unix-like systems, commands run through /bin/sh -c.

    Returns:
        list: Shell prefix as a list of strings.
    """
    current_platform = detect_platform()
    if current_platform == Platform.WINDOWS:
        return ["cmd", "/c"]
    return ["/bin/sh", "-c"]


def is_admin() -> bool:
    """
    Check whether the current process has administrator/root privileges.

    Returns:
        bool: True if running with elevated privileges.
    """
    current_platform = detect_platform()
    if current_platform == Platform.WINDOWS:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        import os
        return os.geteuid() == 0
