from pathlib import Path
import zipfile
from unittest.mock import patch

from tool_manager.utils.downloader import (
    _resolve_sourceforge_download_url,
    extract_archive_and_install,
    find_binary_directory,
)


def test_resolve_sourceforge_download_url_unescapes_real_binary_link():
    page_html = """
    <html>
      <body>
        <a href="https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/old-releases/43/ngspice-43_64.7z?ts=abc&amp;use_mirror=master&amp;r=">
          Download
        </a>
      </body>
    </html>
    """

    resolved = _resolve_sourceforge_download_url(page_html, "ngspice-43_64.7z")

    assert resolved is not None
    assert "ngspice-43_64.7z" in resolved
    assert "&amp;" not in resolved
    assert "use_mirror=master" in resolved


def test_find_binary_directory_prefers_matching_executable(tmp_path):
    install_root = tmp_path / "ngspice"
    bin_dir = install_root / "Spice64" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ngspice.exe").write_bytes(b"MZ")

    result = find_binary_directory(
        install_root,
        binary_names=["ngspice.exe"],
        preferred_subdir="Spice64/bin",
    )

    assert result == bin_dir


def test_extract_archive_and_install_returns_discovered_bin_dir(tmp_path):
    archive_path = tmp_path / "ghdl.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("bin/ghdl.exe", b"MZ")

    fake_tools_dir = tmp_path / "tools"

    with patch("tool_manager.utils.downloader.TOOLS_DIR", fake_tools_dir):
        with patch(
            "tool_manager.utils.downloader.add_to_user_path",
            return_value=(True, "Added to PATH."),
        ):
            success, message, install_dir, bin_dir = extract_archive_and_install(
                archive_path,
                "ghdl",
                archive_format="zip",
                bin_subdir="bin",
                binary_names=["ghdl.exe"],
            )

    assert success is True
    assert "Added to PATH" in message
    assert install_dir == fake_tools_dir / "ghdl"
    assert bin_dir == fake_tools_dir / "ghdl" / "bin"
