"""
Tool installation workflows.
"""

from __future__ import annotations

import glob
import os
import shlex
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from tool_manager.utils.logger import get_logger
from tool_manager.utils.os_utils import Platform, detect_platform, get_platform_key, is_admin

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
    installed_bin_dir: Optional[str] = None


class ToolInstaller:
    """
    Install tools by direct download, package-manager command, or manual fallback.
    """

    def __init__(self, tools_config: dict, dry_run: bool = False, timeout: int = 1800):
        self.tools_config = tools_config
        self.dry_run = dry_run
        self.timeout = timeout

    @staticmethod
    def can_auto_install(tool_cfg: dict, platform_key: str) -> bool:
        """Check whether a tool has any automatic install method."""

        has_command = bool(tool_cfg.get("install", {}).get(platform_key, ""))
        has_download = bool(tool_cfg.get("download", {}).get(platform_key))
        return has_command or has_download

    def install_tool(
        self,
        tool_name: str,
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> InstallResult:
        """Install one tool from the registry."""

        if tool_name not in self.tools_config:
            message = f"Tool '{tool_name}' is not registered in tools.json."
            logger.error(message)
            return InstallResult(tool_name=tool_name, success=False, message=message)

        tool_cfg = self.tools_config[tool_name]
        platform_key = get_platform_key()
        download_cfg = tool_cfg.get("download", {}).get(platform_key)
        command = tool_cfg.get("install", {}).get(platform_key, "").strip()

        if download_cfg:
            self._notify(status_callback, f"Downloading {tool_name}...")
            logger.info("Installing '%s' via direct download.", tool_name)

            if self.dry_run:
                return InstallResult(
                    tool_name=tool_name,
                    success=True,
                    message=f"[DRY RUN] Would download: {download_cfg.get('url', '?')}",
                )

            result = self._install_via_download(
                tool_name,
                tool_cfg,
                download_cfg,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )
            if result.success:
                self._notify(status_callback, f"Verifying {tool_name}...")
                return self._verify_installation(tool_name, result)

            if not command:
                return result

            logger.warning(
                "Direct download install for '%s' failed: %s. Falling back to install command.",
                tool_name,
                result.message,
            )
            self._notify(status_callback, f"Download failed ({result.message}), falling back to command install for {tool_name}...")

        if command:
            logger.info("Installing '%s' via command: %s", tool_name, command)
            self._notify(status_callback, f"Installing {tool_name}...")

            if self.dry_run:
                return InstallResult(
                    tool_name=tool_name,
                    success=True,
                    message=f"[DRY RUN] Would execute: {command}",
                    command_executed=command,
                )

            result = self._execute(tool_name, command)
            if result.success:
                discovered = self._discover_installed_bin_dir(tool_name, tool_cfg)
                if discovered:
                    result.installed_bin_dir = discovered
                self._notify(status_callback, f"Verifying {tool_name}...")
                return self._verify_installation(tool_name, result)
            return result

        manual_url = tool_cfg.get("manual_install_url") or tool_cfg.get("homepage", "")
        message = f"'{tool_name}' cannot be auto-installed on {platform_key}."
        if manual_url:
            message += f" Please install manually from: {manual_url}"
            try:
                webbrowser.open(manual_url)
                message += " (URL opened in browser)"
            except Exception:
                pass

        logger.warning(message)
        return InstallResult(tool_name=tool_name, success=False, message=message)

    def install_all(self, tool_names: Optional[list[str]] = None) -> list[InstallResult]:
        """Install multiple tools."""

        names = tool_names or list(self.tools_config.keys())
        return [self.install_tool(name) for name in names]

    def _install_via_download(
        self,
        tool_name: str,
        tool_cfg: dict,
        download_cfg: dict,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> InstallResult:
        """Download and install a tool from a configured URL."""

        from tool_manager.utils.downloader import (
            DownloadError,
            add_to_user_path,
            cleanup_download,
            download_file,
            extract_archive_and_install,
        )

        url = download_cfg["url"]
        filename = download_cfg["filename"]
        install_type = download_cfg.get("type", "exe_installer")
        binary_names = download_cfg.get("binary_names") or tool_cfg.get("binary_names")

        try:
            file_path = download_file(
                url,
                filename,
                progress_callback=progress_callback,
            )
        except DownloadError as exc:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"Download failed for '{tool_name}': {exc}",
                command_executed=f"download: {url}",
            )

        try:
            if install_type == "exe_installer":
                from tool_manager.utils.downloader import run_exe_installer

                self._notify(status_callback, f"Running installer for {tool_name}...")
                success, message = run_exe_installer(
                    file_path,
                    silent_args=download_cfg.get("silent_args", ""),
                    elevated=True,
                    timeout=self.timeout,
                )
                installed_bin_dir = None

                # Allow filesystem to settle after installer completes
                time.sleep(3)

                # Always try to discover the binary directory, even if the
                # installer reported a non-zero exit code.  Some installers
                # (e.g. KiCad / BitRock) return non-zero for benign
                # conditions like "reboot required".
                configured_path = download_cfg.get("add_to_path")
                if configured_path and Path(os.path.expandvars(configured_path)).exists():
                    installed_bin_dir = os.path.expandvars(configured_path)
                else:
                    installed_bin_dir = self._discover_installed_bin_dir(
                        tool_name,
                        tool_cfg,
                        search_root=download_cfg.get("search_root"),
                        download_cfg=download_cfg,
                    )

                if installed_bin_dir:
                    _, path_message = add_to_user_path(installed_bin_dir)
                    message = f"{message} {path_message}"
                    if not success:
                        logger.info(
                            "Installer for '%s' exited with non-zero code but "
                            "binary found at %s; treating as success.",
                            tool_name,
                            installed_bin_dir,
                        )
                        success = True
                        message = (
                            f"Installer for '{tool_name}' completed "
                            f"(binary found at {installed_bin_dir}). {path_message}"
                        )

                return InstallResult(
                    tool_name=tool_name,
                    success=success,
                    message=message,
                    command_executed=f"download+run: {url}",
                    installed_bin_dir=installed_bin_dir,
                )

            if install_type in {"zip_extract", "archive_extract"}:
                self._notify(status_callback, f"Extracting {tool_name}...")
                success, message, _install_dir, bin_dir = extract_archive_and_install(
                    file_path,
                    tool_name,
                    archive_format=download_cfg.get("archive_format", "zip"),
                    bin_subdir=download_cfg.get("bin_subdir", "bin"),
                    binary_names=binary_names,
                )
                return InstallResult(
                    tool_name=tool_name,
                    success=success,
                    message=message,
                    command_executed=f"download+extract: {url}",
                    installed_bin_dir=str(bin_dir) if bin_dir else None,
                )

            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"Unknown install type: {install_type}",
            )
        finally:
            cleanup_download(filename)

    def _execute(self, tool_name: str, command: str) -> InstallResult:
        """Run an install command, elevating on Windows when needed."""

        current_platform = detect_platform()
        if current_platform == Platform.WINDOWS and not is_admin():
            logger.info("Elevating '%s' via UAC.", tool_name)
            return self._execute_elevated_windows(tool_name, command)
        return self._execute_direct(tool_name, command)

    def _execute_elevated_windows(self, tool_name: str, command: str) -> InstallResult:
        """Run an install command inside an elevated PowerShell process."""

        import base64
        # Wrap the command in a scriptblock that properly propagates the exit code.
        # We base64 encode it to avoid PowerShell's notorious ArgumentList parsing bugs,
        # especially with characters like '='.
        inner_script = f"& {{ {command} }}; $code=$LASTEXITCODE; if (!$code) {{ $code = $(if ($?) {{0}} else {{1}}) }}; exit $code"
        encoded_cmd = base64.b64encode(inner_script.encode('utf-16le')).decode('utf-8')

        ps_script = (
            "$proc = Start-Process powershell.exe "
            f"-ArgumentList '-NoProfile -WindowStyle Hidden -EncodedCommand {encoded_cmd}' "
            "-Verb RunAs -Wait -PassThru; "
            "exit $proc.ExitCode"
        )

        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"Install timed out after {self.timeout}s.",
                command_executed=command,
            )
        except PermissionError:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message="Permission denied. Try running with elevated privileges.",
                command_executed=command,
            )
        except Exception as exc:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"Unexpected error: {exc}",
                command_executed=command,
            )

        success = result.returncode == 0
        if success:
            message = f"Install command for '{tool_name}' completed. Verifying..."
        else:
            hint = f" - {result.stderr.strip()[:200]}" if result.stderr else ""
            message = (
                f"Installation of '{tool_name}' failed (exit code {result.returncode})."
                f"{hint}"
            )

        return InstallResult(
            tool_name=tool_name,
            success=success,
            message=message,
            command_executed=command,
            stdout=result.stdout.strip() if result.stdout else None,
            stderr=result.stderr.strip() if result.stderr else None,
            return_code=result.returncode,
        )

    def _execute_direct(self, tool_name: str, command: str) -> InstallResult:
        """Run an install command directly in the current shell."""

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=True,
            )
        except subprocess.TimeoutExpired:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"Install timed out after {self.timeout}s.",
                command_executed=command,
            )
        except PermissionError:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message="Permission denied. Try running with elevated privileges.",
                command_executed=command,
            )
        except Exception as exc:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"Unexpected error: {exc}",
                command_executed=command,
            )

        success = result.returncode == 0
        if success:
            message = f"Install command for '{tool_name}' completed. Verifying..."
        else:
            hint = ""
            if result.stderr:
                hint = f" - {result.stderr.strip()[:200]}"
            elif result.stdout:
                hint = f" - {result.stdout.strip()[:200]}"
            message = (
                f"Installation of '{tool_name}' failed (exit code {result.returncode})."
                f"{hint}"
            )

        return InstallResult(
            tool_name=tool_name,
            success=success,
            message=message,
            command_executed=command,
            stdout=result.stdout.strip() if result.stdout else None,
            stderr=result.stderr.strip() if result.stderr else None,
            return_code=result.returncode,
        )

    def _discover_installed_bin_dir(
        self,
        tool_name: str,
        tool_cfg: dict,
        search_root: Optional[str] = None,
        download_cfg: Optional[dict] = None,
    ) -> Optional[str]:
        """Discover the directory containing the installed executable."""

        from tool_manager.utils.downloader import find_binary_directory

        binary_names = [name.lower() for name in tool_cfg.get("binary_names", [])]
        bin_subdir = ""
        if download_cfg:
            bin_subdir = download_cfg.get("bin_subdir", "")

        if search_root:
            root_path = Path(os.path.expandvars(search_root))
            if root_path.exists():
                return str(
                    find_binary_directory(
                        root_path,
                        binary_names=tool_cfg.get("binary_names"),
                        preferred_subdir=bin_subdir or "bin",
                    )
                )

        configured_paths = []
        if download_cfg and download_cfg.get("add_to_path"):
            configured_paths.append(download_cfg["add_to_path"])
        configured_paths.extend(tool_cfg.get("path_hints", []))

        for raw_path in configured_paths:
            candidate = Path(os.path.expandvars(raw_path))
            if candidate.is_file():
                return str(candidate.parent)
            if candidate.is_dir():
                if not binary_names or self._directory_has_binary(candidate, binary_names):
                    return str(candidate)

        for raw_pattern in tool_cfg.get("path_globs", []):
            for match in glob.glob(os.path.expandvars(raw_pattern)):
                candidate = Path(match)
                if candidate.is_file():
                    return str(candidate.parent)
                if candidate.is_dir():
                    if not binary_names or self._directory_has_binary(candidate, binary_names):
                        return str(candidate)

        return None

    @staticmethod
    def _directory_has_binary(directory: Path, binary_names: list[str]) -> bool:
        for name in binary_names:
            if (directory / name).exists():
                return True
        return False

    def _verify_installation(
        self,
        tool_name: str,
        install_result: InstallResult,
    ) -> InstallResult:
        """Verify that the tool becomes visible after installation."""

        from tool_manager.utils.downloader import add_to_user_path

        tool_cfg = self.tools_config.get(tool_name, {})
        check_cmd = tool_cfg.get("check")
        if not check_cmd:
            logger.warning("No check command for '%s'; cannot verify install.", tool_name)
            return install_result

        install_env = os.environ.copy()
        installed_bin_dir = install_result.installed_bin_dir

        if not installed_bin_dir:
            installed_bin_dir = self._discover_installed_bin_dir(tool_name, tool_cfg)
            if installed_bin_dir:
                install_result.installed_bin_dir = installed_bin_dir

        if installed_bin_dir:
            add_to_user_path(installed_bin_dir)
            install_env["PATH"] = installed_bin_dir + os.pathsep + install_env.get("PATH", "")

        logger.info("Verifying '%s' with: %s", tool_name, check_cmd)

        if install_result.installed_bin_dir:
            try:
                direct_verify = self._run_check_command_direct(
                    install_result.installed_bin_dir,
                    tool_cfg.get("binary_names", []),
                    check_cmd,
                )
                if direct_verify is not None and direct_verify.returncode == 0:
                    message = f"Successfully installed '{tool_name}' - verified on system."
                    if install_result.installed_bin_dir:
                        message += f" PATH updated with {install_result.installed_bin_dir}."
                    logger.info(message)
                    return InstallResult(
                        tool_name=tool_name,
                        success=True,
                        message=message,
                        command_executed=install_result.command_executed,
                        stdout=install_result.stdout,
                        stderr=install_result.stderr,
                        return_code=install_result.return_code,
                        installed_bin_dir=install_result.installed_bin_dir,
                    )
            except subprocess.TimeoutExpired:
                pass
            except Exception as exc:
                logger.debug("Direct verification failed for '%s': %s", tool_name, exc)

        try:
            verify = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                timeout=15,
                shell=True,
                env=install_env,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("Verification of '%s' was inconclusive; trusting install result.", tool_name)
            return install_result
        except Exception as exc:
            logger.warning("Verification error for '%s': %s", tool_name, exc)
            return install_result

        if verify.returncode == 0:
            message = f"Successfully installed '{tool_name}' - verified on system."
            if install_result.installed_bin_dir:
                message += f" PATH updated with {install_result.installed_bin_dir}."
            logger.info(message)
            return InstallResult(
                tool_name=tool_name,
                success=True,
                message=message,
                command_executed=install_result.command_executed,
                stdout=install_result.stdout,
                stderr=install_result.stderr,
                return_code=install_result.return_code,
                installed_bin_dir=install_result.installed_bin_dir,
            )

        # Verification command returned non-zero.  Before giving up, check
        # whether the binary physically exists on disk.  This handles cases
        # where the tool IS installed but the check command fails (e.g.
        # missing DLLs at first launch, needs system restart, etc.).
        if not installed_bin_dir:
            installed_bin_dir = self._discover_installed_bin_dir(tool_name, tool_cfg)
            if installed_bin_dir:
                install_result.installed_bin_dir = installed_bin_dir
                add_to_user_path(installed_bin_dir)

        if installed_bin_dir:
            binary_names = tool_cfg.get("binary_names", [])
            for name in binary_names:
                if (Path(installed_bin_dir) / name).exists():
                    message = (
                        f"'{tool_name}' installed to {installed_bin_dir}. "
                        "The verification command did not succeed, but the "
                        "binary was found on disk. A system restart may be "
                        "required for full functionality."
                    )
                    logger.info(message)
                    return InstallResult(
                        tool_name=tool_name,
                        success=True,
                        message=message,
                        command_executed=install_result.command_executed,
                        stdout=install_result.stdout,
                        stderr=install_result.stderr,
                        return_code=install_result.return_code,
                        installed_bin_dir=installed_bin_dir,
                    )

        message = (
            f"'{tool_name}' finished running, but the tool is still not detected on the "
            "system. Please check the installer output and the configured binary path."
        )
        logger.warning(message)
        return InstallResult(
            tool_name=tool_name,
            success=False,
            message=message,
            command_executed=install_result.command_executed,
            stdout=install_result.stdout,
            stderr=install_result.stderr or verify.stderr,
            return_code=install_result.return_code,
            installed_bin_dir=install_result.installed_bin_dir,
        )

    @staticmethod
    def _notify(callback: Optional[Callable[[str], None]], message: str) -> None:
        if callback:
            try:
                callback(message)
            except Exception:
                logger.debug("Status callback failed for message: %s", message)

    @staticmethod
    def _run_check_command_direct(
        binary_dir: str,
        binary_names: list[str],
        check_cmd: str,
    ) -> Optional[subprocess.CompletedProcess]:
        directory = Path(binary_dir)
        binary_path = None
        for name in binary_names:
            candidate = directory / name
            if candidate.exists():
                binary_path = candidate
                break

        if binary_path is None:
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
            timeout=30,
            shell=False,
        )
