"""
Download, extraction, and PATH-management helpers.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional, Tuple

from tool_manager.utils.logger import get_logger

logger = get_logger("utils.downloader")

_APP_DATA = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
DOWNLOAD_DIR = _APP_DATA / "esim-tool-manager" / "downloads"
TOOLS_DIR = _APP_DATA / "esim-tool-manager" / "tools"
_SOURCEFORGE_PREFIX = "https://downloads.sourceforge.net/project/"
_CHUNK_SIZE = 1024 * 256


class DownloadError(Exception):
    """Raised when a binary or archive cannot be downloaded successfully."""


def _ensure_dirs() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _build_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "eSim-Tool-Manager/1.0",
            "Accept": "*/*",
        },
    )


def _looks_like_html(content_type: Optional[str], first_bytes: bytes) -> bool:
    content_type = (content_type or "").lower()
    if "text/html" in content_type:
        return True

    sample = first_bytes.lstrip().lower()
    return sample.startswith(b"<!doctype html") or sample.startswith(b"<html")


def _resolve_sourceforge_download_url(page_html: str, expected_filename: str) -> Optional[str]:
    pattern = re.compile(
        rf"{re.escape(_SOURCEFORGE_PREFIX)}[^\"'\s<>]*{re.escape(expected_filename)}\?[^\"'\s<>]+",
        re.IGNORECASE,
    )
    match = pattern.search(page_html)
    if not match:
        return None
    return html.unescape(match.group(0))


def _resolve_kicad_download_url(page_html: str, expected_filename: str) -> Optional[str]:
    pattern = re.compile(
        rf"https://downloads\.kicad\.org/[^\"'\s<>]*/download/{re.escape(expected_filename)}",
        re.IGNORECASE,
    )
    match = pattern.search(page_html)
    if not match:
        return None
    return html.unescape(match.group(0))


def _resolve_download_url(url: str, expected_filename: str) -> str:
    """
    Resolve landing pages to a real binary URL when providers gate downloads
    behind an HTML page.
    """

    logger.info("Resolving download URL: %s", url)

    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    with opener.open(_build_request(url), timeout=30) as response:
        content_type = response.headers.get("Content-Type")
        final_url = response.geturl()
        first_bytes = response.read(4096)

        if not _looks_like_html(content_type, first_bytes):
            logger.info("Resolved direct binary URL: %s", final_url)
            return final_url

        page_html = (first_bytes + response.read()).decode("utf-8", "ignore")

    if "sourceforge.net" in url or "sourceforge.net" in final_url:
        resolved = _resolve_sourceforge_download_url(page_html, expected_filename)
        if resolved:
            logger.info("Resolved SourceForge binary URL: %s", resolved)
            return resolved

    if "downloads.kicad.org" in url or "downloads.kicad.org" in final_url:
        resolved = _resolve_kicad_download_url(page_html, expected_filename)
        if resolved:
            logger.info("Resolved KiCad binary URL: %s", resolved)
            return resolved

    return final_url


def _validate_download_signature(destination: Path, first_bytes: bytes) -> None:
    if _looks_like_html(None, first_bytes):
        raise DownloadError(
            f"{destination.name} resolved to an HTML page instead of a downloadable file."
        )

    suffix = destination.suffix.lower()
    if suffix == ".exe" and not first_bytes.startswith(b"MZ"):
        raise DownloadError(f"{destination.name} is not a valid Windows executable.")
    if suffix == ".zip" and not first_bytes.startswith(b"PK"):
        raise DownloadError(f"{destination.name} is not a valid ZIP archive.")
    if suffix == ".7z" and not first_bytes.startswith(b"7z\xbc\xaf'\x1c"):
        raise DownloadError(f"{destination.name} is not a valid 7z archive.")


def download_file(
    url: str,
    filename: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """Download a file and return the downloaded path."""

    _ensure_dirs()
    destination = DOWNLOAD_DIR / filename
    if destination.exists():
        destination.unlink()

    resolved_url = _resolve_download_url(url, filename)
    logger.info("Downloading: %s", resolved_url)
    logger.info("Destination: %s", destination)

    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    downloaded = 0
    with opener.open(_build_request(resolved_url), timeout=120) as response:
        total_size = int(response.headers.get("Content-Length") or 0)
        first_chunk = response.read(_CHUNK_SIZE)
        if not first_chunk:
            raise DownloadError("Download produced an empty response.")

        _validate_download_signature(destination, first_chunk)

        with destination.open("wb") as handle:
            handle.write(first_chunk)
            downloaded += len(first_chunk)
            if progress_callback:
                progress_callback(downloaded, total_size)

            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)

    if not destination.exists() or destination.stat().st_size == 0:
        if destination.exists():
            destination.unlink()
        raise DownloadError("Downloaded file is empty or missing.")

    logger.info(
        "Download complete: %s (%s)",
        destination,
        _format_size(destination.stat().st_size),
    )
    return destination


def run_exe_installer(
    installer_path: Path,
    silent_args: str = "",
    elevated: bool = True,
    timeout: int = 600,
) -> Tuple[bool, str]:
    """Run a Windows .exe installer, optionally with elevation."""

    if not installer_path.exists():
        return False, f"Installer not found: {installer_path}"

    logger.info(
        "Running installer: %s %s (elevated=%s)",
        installer_path,
        silent_args,
        elevated,
    )

    try:
        if elevated:
            inst = str(installer_path).replace("'", "''")
            ps_command = (
                f"$proc = Start-Process '{inst}' "
                + (f"-ArgumentList '{silent_args}' " if silent_args else "")
                + "-Verb RunAs -Wait -PassThru; "
                "exit $proc.ExitCode"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        else:
            command = f'"{installer_path}"'
            if silent_args:
                command += f" {silent_args}"
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return False, f"Installer timed out after {timeout}s."
    except Exception as exc:
        return False, f"Error running installer: {exc}"

    if result.returncode == 0:
        return True, "Installer completed successfully."

    error_hint = result.stderr.strip()[:300] if result.stderr else ""
    return False, f"Installer exited with code {result.returncode}. {error_hint}"


def find_binary_directory(
    install_root: Path,
    binary_names: Optional[list[str]] = None,
    preferred_subdir: str = "bin",
) -> Path:
    """Find the directory that contains the installed executable(s)."""

    if preferred_subdir:
        direct_candidate = install_root / preferred_subdir
        if direct_candidate.is_file():
            return direct_candidate.parent
        if direct_candidate.is_dir():
            return direct_candidate

    normalized_names = {name.lower() for name in (binary_names or [])}
    if normalized_names:
        for entry in install_root.rglob("*"):
            if entry.is_file() and entry.name.lower() in normalized_names:
                return entry.parent

    preferred_name = Path(preferred_subdir).name.lower()
    for entry in install_root.rglob("*"):
        if entry.is_dir() and entry.name.lower() == preferred_name:
            return entry

    return install_root


def extract_archive_and_install(
    archive_path: Path,
    tool_name: str,
    archive_format: str = "zip",
    bin_subdir: str = "bin",
    binary_names: Optional[list[str]] = None,
) -> Tuple[bool, str, Optional[Path], Optional[Path]]:
    """Extract an archive locally and add its binary directory to PATH."""

    if not archive_path.exists():
        return False, f"Archive not found: {archive_path}", None, None

    destination = TOOLS_DIR / tool_name
    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)

    logger.info("Extracting %s -> %s", archive_path, destination)

    try:
        archive_format = archive_format.lower()
        if archive_format == "zip":
            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(destination)
        elif archive_format == "7z":
            try:
                import py7zr
            except ImportError as exc:
                return (
                    False,
                    "py7zr is required to extract .7z archives. Install it with 'pip install py7zr'.",
                    None,
                    None,
                )

            with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                archive.extractall(path=destination)
        else:
            return False, f"Unsupported archive format: {archive_format}", None, None
    except zipfile.BadZipFile:
        return False, f"Invalid zip file: {archive_path}", None, None
    except Exception as exc:
        return False, f"Extraction failed: {exc}", None, None

    bin_path = find_binary_directory(
        destination,
        binary_names=binary_names,
        preferred_subdir=bin_subdir,
    )
    _, path_message = add_to_user_path(str(bin_path))
    message = f"Installed '{tool_name}' to {destination}. {path_message}"
    logger.info(message)
    return True, message, destination, bin_path


def _prepend_to_process_path(directory: str) -> None:
    normalized = directory.rstrip("\\/")
    current_entries = [
        entry.rstrip("\\/")
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry.strip()
    ]
    if normalized not in current_entries:
        os.environ["PATH"] = normalized + os.pathsep + os.environ.get("PATH", "")


def _broadcast_environment_change() -> None:
    try:
        import ctypes

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            None,
        )
    except Exception:
        pass


def add_to_user_path(directory: str) -> Tuple[bool, str]:
    """Persist a directory in the user's PATH and update the current process."""

    normalized_dir = str(Path(directory).expanduser())
    _prepend_to_process_path(normalized_dir)

    try:
        get_result = subprocess.run(
            [
                "powershell",
                "-Command",
                '[Environment]::GetEnvironmentVariable("Path", "User")',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        current_path = get_result.stdout.strip() or ""

        dir_lower = normalized_dir.lower().rstrip("\\")
        entries = [
            part.strip().rstrip("\\").lower()
            for part in current_path.split(";")
            if part.strip()
        ]
        if dir_lower in entries:
            return True, f"'{normalized_dir}' is already in PATH."

        new_path = f"{current_path};{normalized_dir}" if current_path else normalized_dir
        escaped_path = new_path.replace("'", "''")
        set_result = subprocess.run(
            [
                "powershell",
                "-Command",
                f"[Environment]::SetEnvironmentVariable('Path', '{escaped_path}', 'User')",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if set_result.returncode == 0:
            _broadcast_environment_change()
            return True, f"Added '{normalized_dir}' to user PATH."

        return False, f"Failed to update PATH: {set_result.stderr.strip()}"
    except Exception as exc:
        return False, f"Error updating PATH: {exc}"


def cleanup_download(filename: str) -> None:
    """Remove a downloaded file if it still exists."""

    path = DOWNLOAD_DIR / filename
    if not path.exists():
        return

    try:
        path.unlink()
    except Exception:
        pass
