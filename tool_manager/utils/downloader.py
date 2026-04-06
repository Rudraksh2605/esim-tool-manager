"""
Download, extraction, and PATH-management helpers.

Supports **multi-threaded parallel downloads** (like IDM / aria2) when the
remote server advertises ``Accept-Ranges: bytes``.  Falls back to a single
connection transparently.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional, Tuple

from tool_manager.utils.logger import get_logger

logger = get_logger("utils.downloader")

_APP_DATA = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
DOWNLOAD_DIR = _APP_DATA / "esim-tool-manager" / "downloads"
TOOLS_DIR = _APP_DATA / "esim-tool-manager" / "tools"
_SOURCEFORGE_PREFIX = "https://downloads.sourceforge.net/project/"
_CHUNK_SIZE = 1024 * 256

# ── Parallel download tunables ───────────────────────────────────────────────
_NUM_SEGMENTS = 8            # Number of parallel connections
_MIN_SIZE_FOR_PARALLEL = 2 * 1024 * 1024   # Only parallelise files > 2 MB


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


def _build_request(url: str, extra_headers: Optional[dict] = None) -> urllib.request.Request:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "eSim-Tool-Manager/1.0",
        "Accept": "*/*",
    }
    if extra_headers:
        headers.update(extra_headers)
    return urllib.request.Request(url, headers=headers)


def _looks_like_html(content_type: Optional[str], first_bytes: bytes) -> bool:
    content_type = (content_type or "").lower()
    if "text/html" in content_type:
        return True

    sample = first_bytes.lstrip().lower()
    return sample.startswith(b"<!doctype html") or sample.startswith(b"<html")


def _extract_meta_refresh_url(page_html: str) -> Optional[str]:
    """Extract the redirect URL from an HTML meta-refresh tag."""
    pattern = re.compile(
        r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?\d+;\s*url=([^"\'\>\s]+)',
        re.IGNORECASE,
    )
    match = pattern.search(page_html)
    if match:
        return html.unescape(match.group(1).strip("'\""))
    # Also try reversed attribute order
    pattern2 = re.compile(
        r'content=["\']?\d+;\s*url=([^"\'\>\s]+)[^>]*http-equiv=["\']?refresh',
        re.IGNORECASE,
    )
    match2 = pattern2.search(page_html)
    if match2:
        return html.unescape(match2.group(1).strip("'\""))
    return None


def _resolve_sourceforge_download_url(page_html: str, expected_filename: str) -> Optional[str]:
    """
    SourceForge uses meta-refresh to redirect to a CDN mirror.
    Also matches direct CDN links in the page HTML.
    """
    # Pattern 1: meta-refresh redirect (most reliable for SourceForge)
    refresh_url = _extract_meta_refresh_url(page_html)
    if refresh_url and expected_filename.lower() in refresh_url.lower():
        return refresh_url

    # Pattern 2: any *.dl.sourceforge.net or downloads.sourceforge.net CDN link
    cdn_pattern = re.compile(
        rf"https://[a-z0-9.-]*sourceforge\.net[^\"'\s<>]*{re.escape(expected_filename)}[^\"'\s<>]*",
        re.IGNORECASE,
    )
    for match in cdn_pattern.finditer(page_html):
        candidate = html.unescape(match.group(0))
        if "/download" not in candidate or "/files/" in candidate:
            return candidate

    # Pattern 3: any direct link to the filename (last resort)
    direct_pattern = re.compile(
        rf"https?://[^\"'\s<>]*/{re.escape(expected_filename)}[^\"'\s<>]*",
        re.IGNORECASE,
    )
    match = direct_pattern.search(page_html)
    if match:
        return html.unescape(match.group(0))

    return None


def _resolve_kicad_download_url(page_html: str, expected_filename: str) -> Optional[str]:
    """
    Look for a direct downloads.kicad.org link or CERN S3 CDN link.
    """
    patterns = [
        re.compile(
            rf"https://downloads\.kicad\.org/[^\"'\s<>]*{re.escape(expected_filename)}",
            re.IGNORECASE,
        ),
        re.compile(
            rf"https://kicad-downloads\.s3\.cern\.ch/[^\"'\s<>]*{re.escape(expected_filename)}",
            re.IGNORECASE,
        ),
        re.compile(
            rf"https?://[^\"'\s<>]*/{re.escape(expected_filename)}",
            re.IGNORECASE,
        ),
    ]
    for pat in patterns:
        match = pat.search(page_html)
        if match:
            return html.unescape(match.group(0))
    return None


def _follow_url_to_binary(
    opener: urllib.request.OpenerDirector,
    url: str,
    expected_filename: str,
    max_redirects: int = 3,
) -> str:
    """
    Follow a URL, resolving HTML meta-refresh redirects, until we reach a
    binary file or exhaust our redirect budget.
    """
    current_url = url
    for hop in range(max_redirects):
        logger.info("Resolving hop %d: %s", hop + 1, current_url)
        try:
            with opener.open(_build_request(current_url), timeout=60) as response:
                content_type = response.headers.get("Content-Type", "")
                final_url = response.geturl()
                first_bytes = response.read(8192)

                if not _looks_like_html(content_type, first_bytes):
                    logger.info("Reached binary URL: %s", final_url)
                    return final_url

                page_html = (first_bytes + response.read()).decode("utf-8", "ignore")
        except Exception as exc:
            logger.warning("Hop %d failed (%s); stopping at: %s", hop + 1, exc, current_url)
            return current_url

        # Try meta-refresh redirect
        next_url = _extract_meta_refresh_url(page_html)
        if next_url:
            logger.info("Following meta-refresh to: %s", next_url)
            current_url = next_url
            continue

        # Try SourceForge-specific patterns
        if "sourceforge.net" in current_url or "sourceforge.net" in final_url:
            resolved = _resolve_sourceforge_download_url(page_html, expected_filename)
            if resolved:
                current_url = resolved
                continue

        # Try KiCad-specific patterns
        if "kicad.org" in current_url or "kicad.org" in final_url:
            resolved = _resolve_kicad_download_url(page_html, expected_filename)
            if resolved:
                return resolved

        # No further redirect found
        logger.warning("Could not find binary URL in HTML page; using: %s", final_url)
        return final_url

    return current_url


def _resolve_download_url(url: str, expected_filename: str) -> str:
    """
    Resolve landing pages to a real binary URL.
    Follows HTTP redirects AND HTML meta-refresh chains.
    """
    logger.info("Resolving download URL: %s", url)
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    return _follow_url_to_binary(opener, url, expected_filename)


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


# ── Server probing ──────────────────────────────────────────────────────────


def _probe_download(url: str) -> Tuple[int, bool]:
    """
    Send a HEAD-like request to discover the file size and whether the server
    supports byte-range requests.

    Returns (total_size, supports_ranges).
    """
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    req = _build_request(url)
    req.method = "HEAD"  # type: ignore[attr-defined]
    try:
        with opener.open(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            accept = (resp.headers.get("Accept-Ranges") or "").lower()
            supports = accept == "bytes" and total > 0
            logger.debug(
                "Probe: Content-Length=%s  Accept-Ranges=%s  supports_parallel=%s",
                total, accept, supports,
            )
            return total, supports
    except Exception as exc:
        logger.debug("HEAD probe failed (%s); falling back to single-thread.", exc)
        return 0, False


# ── Single-segment download (original) ──────────────────────────────────────


def _download_single(
    resolved_url: str,
    destination: Path,
    progress_callback: Optional[Callable[[int, int, float], None]] = None,
) -> Path:
    """Download an entire file using one connection (fallback path)."""
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    downloaded = 0
    start_time = time.monotonic()
    last_log_time = start_time

    with opener.open(_build_request(resolved_url), timeout=300) as response:
        total_size = int(response.headers.get("Content-Length") or 0)
        logger.debug(
            "Single-thread — Content-Length: %s, Content-Type: %s",
            total_size or "unknown",
            response.headers.get("Content-Type", "unknown"),
        )
        first_chunk = response.read(_CHUNK_SIZE)
        if not first_chunk:
            raise DownloadError("Download produced an empty response.")

        _validate_download_signature(destination, first_chunk)

        with destination.open("wb") as handle:
            handle.write(first_chunk)
            downloaded += len(first_chunk)
            elapsed = max(time.monotonic() - start_time, 0.001)
            speed = downloaded / elapsed
            if progress_callback:
                progress_callback(downloaded, total_size, speed)

            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                elapsed = max(now - start_time, 0.001)
                speed = downloaded / elapsed

                if progress_callback:
                    progress_callback(downloaded, total_size, speed)

                if now - last_log_time >= 2.0:
                    pct = (downloaded / total_size * 100) if total_size else 0
                    logger.debug(
                        "Progress: %s / %s (%.1f%%) — %.2f MB/s",
                        _format_size(downloaded),
                        _format_size(total_size) if total_size else "?",
                        pct,
                        speed / (1024 * 1024),
                    )
                    last_log_time = now

    return destination


# ── Multi-segment parallel download ─────────────────────────────────────────


def _download_segment(
    url: str,
    segment_path: Path,
    start_byte: int,
    end_byte: int,
    segment_id: int,
    progress_array: list,
    progress_lock: threading.Lock,
) -> None:
    """
    Download a single byte-range segment to *segment_path*.

    Updates ``progress_array[segment_id]`` with the number of bytes this
    segment has downloaded so far (thread-safe via *progress_lock*).
    """
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    req = _build_request(url, extra_headers={
        "Range": f"bytes={start_byte}-{end_byte}",
    })

    seg_downloaded = 0
    with opener.open(req, timeout=300) as resp:
        with segment_path.open("wb") as fh:
            while True:
                chunk = resp.read(_CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                seg_downloaded += len(chunk)
                with progress_lock:
                    progress_array[segment_id] = seg_downloaded

    expected = end_byte - start_byte + 1
    if seg_downloaded < expected:
        raise DownloadError(
            f"Segment {segment_id} incomplete: got {seg_downloaded}, "
            f"expected {expected}"
        )
    logger.debug("Segment %d done: %s", segment_id, _format_size(seg_downloaded))


def _download_parallel(
    resolved_url: str,
    destination: Path,
    total_size: int,
    num_segments: int = _NUM_SEGMENTS,
    progress_callback: Optional[Callable[[int, int, float], None]] = None,
) -> Path:
    """
    Download a file using *num_segments* concurrent HTTP Range requests,
    then stitch the parts together.
    """
    logger.info(
        "Parallel download: %d segments for %s (%s)",
        num_segments, destination.name, _format_size(total_size),
    )

    # ── Compute byte ranges ──────────────────────────────────────────
    segment_size = total_size // num_segments
    ranges: list[Tuple[int, int]] = []
    for i in range(num_segments):
        start = i * segment_size
        end = (start + segment_size - 1) if i < num_segments - 1 else (total_size - 1)
        ranges.append((start, end))

    # Shared progress tracking
    progress_lock = threading.Lock()
    progress_array = [0] * num_segments   # bytes downloaded per segment
    start_time = time.monotonic()
    last_log_time = start_time
    error_holder: list[Optional[Exception]] = [None]

    # Background thread that fires the progress_callback periodically
    stop_event = threading.Event()

    def _progress_reporter():
        nonlocal last_log_time
        while not stop_event.is_set():
            with progress_lock:
                total_dl = sum(progress_array)
            elapsed = max(time.monotonic() - start_time, 0.001)
            speed = total_dl / elapsed
            if progress_callback:
                progress_callback(total_dl, total_size, speed)

            now = time.monotonic()
            if now - last_log_time >= 2.0:
                pct = total_dl / total_size * 100 if total_size else 0
                logger.debug(
                    "Parallel progress: %s / %s (%.1f%%) — %.2f MB/s  [%d segments]",
                    _format_size(total_dl),
                    _format_size(total_size),
                    pct,
                    speed / (1024 * 1024),
                    num_segments,
                )
                last_log_time = now
            stop_event.wait(0.25)

    reporter = threading.Thread(target=_progress_reporter, daemon=True)
    reporter.start()

    # ── Download segments concurrently ───────────────────────────────
    segment_paths = [
        DOWNLOAD_DIR / f"{destination.stem}.part{i}{destination.suffix}"
        for i in range(num_segments)
    ]

    try:
        with ThreadPoolExecutor(max_workers=num_segments) as pool:
            futures = {}
            for i, (s, e) in enumerate(ranges):
                f = pool.submit(
                    _download_segment,
                    resolved_url, segment_paths[i], s, e, i,
                    progress_array, progress_lock,
                )
                futures[f] = i

            for future in as_completed(futures):
                seg_id = futures[future]
                exc = future.exception()
                if exc:
                    error_holder[0] = exc
                    logger.error("Segment %d failed: %s", seg_id, exc)
                    # Cancel remaining futures
                    for other in futures:
                        other.cancel()
                    break
    finally:
        stop_event.set()
        reporter.join(timeout=2)

    if error_holder[0]:
        # Cleanup partial segment files
        for sp in segment_paths:
            if sp.exists():
                sp.unlink(missing_ok=True)
        raise DownloadError(f"Parallel download failed: {error_holder[0]}")

    # ── Validate first segment signature ─────────────────────────────
    with segment_paths[0].open("rb") as fh:
        first_bytes = fh.read(_CHUNK_SIZE)
    _validate_download_signature(destination, first_bytes)

    # ── Stitch segments into the final file ──────────────────────────
    logger.debug("Stitching %d segments into %s", num_segments, destination)
    with destination.open("wb") as out:
        for sp in segment_paths:
            with sp.open("rb") as inp:
                shutil.copyfileobj(inp, out)
            sp.unlink(missing_ok=True)

    # Fire final progress callback
    total_elapsed = max(time.monotonic() - start_time, 0.001)
    avg_speed = total_size / total_elapsed
    if progress_callback:
        progress_callback(total_size, total_size, avg_speed)

    return destination


# ── Public download entry point ──────────────────────────────────────────────


def download_file(
    url: str,
    filename: str,
    progress_callback: Optional[Callable[[int, int, float], None]] = None,
) -> Path:
    """
    Download a file and return the local path.

    Automatically uses **multi-threaded parallel downloads** when the server
    supports HTTP Range requests.  Falls back to a single connection otherwise.

    The optional *progress_callback* receives three positional arguments::

        downloaded_bytes, total_bytes, speed_bytes_per_sec
    """

    _ensure_dirs()
    destination = DOWNLOAD_DIR / filename
    if destination.exists():
        destination.unlink()

    resolved_url = _resolve_download_url(url, filename)
    logger.info("Downloading: %s", resolved_url)
    logger.info("Destination: %s", destination)

    # ── Decide single vs. parallel ───────────────────────────────────
    total_size, supports_ranges = _probe_download(resolved_url)

    start_time = time.monotonic()

    if supports_ranges and total_size >= _MIN_SIZE_FOR_PARALLEL:
        logger.info(
            "Server supports Range requests — using %d parallel segments.",
            _NUM_SEGMENTS,
        )
        _download_parallel(
            resolved_url, destination, total_size,
            num_segments=_NUM_SEGMENTS,
            progress_callback=progress_callback,
        )
    else:
        if total_size and not supports_ranges:
            logger.info("Server does NOT support Range requests — single-thread download.")
        _download_single(resolved_url, destination, progress_callback=progress_callback)

    # ── Final validation ─────────────────────────────────────────────
    if not destination.exists() or destination.stat().st_size == 0:
        if destination.exists():
            destination.unlink()
        raise DownloadError("Downloaded file is empty or missing.")

    total_elapsed = max(time.monotonic() - start_time, 0.001)
    final_size = destination.stat().st_size
    avg_speed = final_size / total_elapsed
    logger.info(
        "Download complete: %s (%s) in %.1fs — avg %.2f MB/s",
        destination,
        _format_size(final_size),
        total_elapsed,
        avg_speed / (1024 * 1024),
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


def remove_from_user_path(directory: str) -> Tuple[bool, str]:
    """Remove a directory from the user's PATH."""
    normalized_dir = str(Path(directory).expanduser())
    
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
        if not current_path:
            return True, "PATH is empty, nothing to remove"

        dir_lower = normalized_dir.lower().rstrip("\\")
        entries = [
            part.strip()
            for part in current_path.split(";")
            if part.strip()
        ]
        
        # Filter out the matching directory (case-insensitive)
        new_entries = [
            part for part in entries
            if part.rstrip("\\").lower() != dir_lower
        ]
        
        if len(new_entries) == len(entries):
            return True, f"'{normalized_dir}' was not in PATH."

        new_path = ";".join(new_entries)
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
            return True, f"Removed '{normalized_dir}' from user PATH."

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
