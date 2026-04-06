# eSim Tool Manager

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Production-grade CLI and GUI tool manager for the eSim electronic circuit simulation ecosystem.**

Automate the installation, version checking, dependency auditing, updating, and removal of external EDA tools such as **Ngspice**, **KiCad**, **GHDL**, **Verilator**, and **Magic** — from one unified command-line interface or dark-themed desktop dashboard.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Multi-tool management** | Install, check, update, and list tools from a single CLI or GUI |
| **Modern GUI Dashboard** | Sleek CustomTkinter-based interface for intuitive point-and-click management |
| **Robust Downloads** | Advanced download engine with SourceForge redirect handling and real-time progress |
| **Complete Uninstallation**| Safely remove tools and automatically clean up system PATH variables |
| **Cross-platform** | Windows, Linux, and macOS with OS-specific commands |
| **Rich CLI output** | Colored tables, panels, and status icons via [Rich](https://github.com/Textualize/rich) |
| **Extensible registry** | Add new tools by editing `tools.json` — zero code changes |
| **Dry-run mode** | Preview commands before execution (`--dry-run`) |
| **Verbose logging** | Dual-output logging (console + rotating file) with `-v` |
| **Version comparison** | PEP 440–aware update detection via `packaging` |
| **Graceful errors** | No crashes — every failure produces a clear, actionable message |

---

## 📦 Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/esim-tool-manager.git
cd esim-tool-manager

# 2. Create a virtual environment (recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. Install in editable mode
pip install -e .
```

After installation the `esim-tool-manager` command is available globally in the activated environment.

---

## 🖼️ Desktop GUI

The eSim Tool Manager comes with a fully-featured, modern Desktop GUI built with [CustomTkinter](https://customtkinter.tomschimansky.com/). It provides an interactive dashboard for managing your EDA tools without needing the command line.

**Key GUI Features:**
- **Real-Time Status Dashboard:** View which tools are installed and their current versions at a glance.
- **Asynchronous Operations:** Installations, uninstalls, and updates run on background threads, ensuring the UI remains highly responsive.
- **Smart Download Engine:** Experience true progress bars showing download percentage and megabytes transferred, natively bypassing complex SourceForge redirects.
- **Clean Uninstallation:** One-click removal of tools that automatically cleans up their associated system `PATH` environment variables.
- **Integrated Diagnostics:** Inspect system dependencies and view detailed application logs directly inside the app interface.

You can launch the GUI dashboard at any time using:
```bash
esim-tool-manager-gui
```

---

## 🚀 Command-Line Interface (CLI) Usage

### Global flags

| Flag | Effect |
|---|---|
| `-v` / `--verbose` | Show DEBUG-level output on console |
| `--dry-run` | Print commands without executing |

### CLI Commands

```bash
# List all registered tools
esim-tool-manager list

# Check if all tools are installed
esim-tool-manager check

# Check a specific tool
esim-tool-manager check ngspice

# Install a tool
esim-tool-manager install ngspice

# Dry-run install (preview only)
esim-tool-manager --dry-run install kicad

# Check for updates
esim-tool-manager update --check-only ngspice

# Apply an update
esim-tool-manager update ngspice

# Inspect install prerequisites and local dependencies
esim-tool-manager doctor

# System status & diagnostics
esim-tool-manager status
```

### Example output

```
╔════════════════════════════════════════╗
║           Dependency Check             ║
║         Platform: windows              ║
╚════════════════════════════════════════╝

  ✔ ngspice (v39.3)  —  installed
  ✗ kicad  —  missing
  ✗ ghdl   —  missing
  ✗ verilator — missing
  ✗ magic  —  missing

  1/5 tools installed.
```

---

## 🏗️ Architecture

```
esim-tool-manager/
│
├── tool_manager/                # Main package
│   ├── __init__.py              # Package metadata & version
│   ├── __main__.py              # `python -m tool_manager` support
│   ├── main.py                  # Entry point
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py          # Click CLI group & commands
│   │
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── app.py               # CustomTkinter GUI main application
│   │   ├── widgets.py           # Custom UI components & dialogs
│   │   └── frames/              # Dashboard views and screens
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── checker.py           # Version checking & status detection
│   │   ├── installer.py         # OS-aware install execution
│   │   └── updater.py           # Version comparison & update workflow
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── os_utils.py          # Platform detection & shell helpers
│   │   └── logger.py            # Centralized rotating-file logging
│   │
│   └── config/
│       ├── __init__.py
│       └── tools.json           # Tool registry (extensible)
│
├── tests/
│   └── test_tool_manager.py     # pytest suite with mocked subprocess
│
├── logs/
│   └── tool_manager.log         # Auto-created rotating log
│
├── setup.py                     # Package installer with console_scripts
├── requirements.txt
└── README.md
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `gui/app.py` & `widgets.py` | Desktop dashboard with async progress handling and tool management screens |
| `cli/commands.py` | Parses user commands, delegates to core modules, renders output |
| `core/checker.py` | Runs check commands, extracts versions, returns structured results |
| `core/installer.py` | Selects OS-specific install command, executes via subprocess |
| `core/updater.py` | Compares installed vs latest version, orchestrates re-install |
| `utils/os_utils.py` | Detects platform, provides shell prefix, checks admin privileges |
| `utils/logger.py` | Configures dual-handler logging with rotation |
| `config/tools.json` | Declarative tool registry — add tools here without code changes |

### CLI Execution Flow

```
User CLI Input
     │
     ▼
┌─────────────┐
│ Click CLI    │  ← parses args, flags
│ commands.py  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│ ToolChecker │ ──► │ os_utils.py  │  ← detects platform
│ checker.py  │     └──────────────┘
└──────┬──────┘
       │
       ▼
┌──────────────┐    ┌──────────────┐
│ToolInstaller │ ─► │ subprocess   │  ← runs OS commands
│ installer.py │    └──────────────┘
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ ToolUpdater  │  ← compares versions, triggers re-install
│ updater.py   │
└──────────────┘
       │
       ▼
   Rich Output + Log File
```

---

## 🔧 Adding a New Tool

Edit `tool_manager/config/tools.json`:

```json
{
  "mytool": {
    "description": "My custom EDA tool",
    "category": "simulator",
    "check": "mytool --version",
    "version_regex": "\\b(\\d+\\.\\d+[\\w.-]*)\\b",
    "latest_version": "2.0.0",
    "install": {
      "linux": "sudo apt install mytool -y",
      "windows": "winget install mytool",
      "macos": "brew install mytool"
    },
    "homepage": "https://mytool.dev"
  }
}
```

**No code changes required.** The tool will automatically appear in `list`, `check`, `install`, `update`, and `status`.

---

## 🧪 Running Tests

```bash
pip install pytest
python -m pytest -q
```

All tests use mocked `subprocess.run` calls — no real installations occur during testing.

---

## 📝 Logging

Logs are written to `logs/tool_manager.log` with automatic rotation (5 MB max, 3 backups).

Enable verbose console output:

```bash
esim-tool-manager -v check
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
