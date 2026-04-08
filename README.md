# eSim Tool Manager

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Production-grade CLI and GUI tool manager for the eSim electronic circuit simulation ecosystem.**

The **eSim Tool Manager** streamlines the lifecycle management of external EDA (Electronic Design Automation) tools required by the eSim platform. Whether you prefer a sleek graphical interface or a powerful terminal environment, this manager automates the installation, version auditing, updating, and removal of core tools like **Ngspice**, **KiCad**, **GHDL**, **Verilator**, and **Magic**.

---

## 🚀 Quick Start Workflow

Getting started and setting up your eSim environment has never been easier. Just follow this straightforward workflow:

1. **Check Status**: `esim-tool-manager status` (See what's missing)
2. **Install Tools**: `esim-tool-manager install <tool_name>` (e.g., `kicad`)
3. **Verify Setup**: `esim-tool-manager check` (Confirm everything is ready)
4. **Launch Dashboard**: `esim-tool-manager-gui` (Manage visually from now on)

---

## ✨ Key Features

- **Modern GUI Dashboard**: A sleek, dark-themed CustomTkinter-based interface for intuitive point-and-click management.
- **Unified Command-Line**: Manage everything via a single extensible command (`esim-tool-manager`) with rich, colored terminal output.
- **Robust Download Engine**: Directly streams files, bypassing complexSourceForge redirects and displaying real-time progress bars.
- **Automated Configuration**: Safely manages `PATH` environment variables and dependency cleanup automatically behind the scenes.
- **Cross-Platform Compatibility**: Fully compatible with Windows, macOS, and Linux out of the box with OS-aware execution.
- **Data-Driven Registry**: Add or modify supported tools simply by editing a JSON file (`tools.json`)—zero Python code changes required.

---

## 📦 Getting Started / Installation

### Prerequisites
- Python 3.10 or higher
- Git (for cloning the repository)

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/esim-tool-manager.git
   cd esim-tool-manager
   ```

2. **Create a virtual environment (Recommended):**
   This keeps the application's dependencies isolated from your system.
   ```bash
   python -m venv .venv
   ```

3. **Activate the environment:**
   - **Windows:**
     ```cmd
     .venv\Scripts\activate
     ```
   - **Linux/macOS:**
     ```bash
     source .venv/bin/activate
     ```

4. **Install the package:**
   Install the package in editable mode so it registers the global commands.
   ```bash
   pip install -e .
   ```

Check that the installation was successful by running:
```bash
esim-tool-manager --help
```

---

## 💻 Usage Guide

### 1. Graphical User Interface (GUI)

The included Desktop application provides an interactive dashboard, eliminating the need to use the command line for day-to-day tasks.

**Launch the GUI:**
```bash
esim-tool-manager-gui
```

**GUI Highlights:**
- real-time tracking of tool statuses.
- Asynchronous installation/uninstallation to keep the interface responsive.
- Integrated diagnostics to quickly spot missing system packages.

### 2. Command-Line Interface (CLI)

The CLI acts as the core backbone of the tool manager.

**Global Flags:**
- `-v` / `--verbose` : Show DEBUG-level output on console.
- `--dry-run` : Print the intended commands without actually executing them.

**Common Commands:**
```bash
# Display system status & diagnostics
esim-tool-manager status

# List all registered tools in the system
esim-tool-manager list

# Check if tools are correctly installed
esim-tool-manager check
esim-tool-manager check ngspice

# Install a required tool
esim-tool-manager install kicad

# Check for updates and apply them
esim-tool-manager update --check-only ngspice
esim-tool-manager update ngspice

# Inspect prerequisites and local dependencies
esim-tool-manager doctor
```

---

## 🏗️ Architecture Under the Hood

The Tool Manager employs a heavily modular architecture to ensure stability:

- **CLI / GUI Layers**: Separates the presentation logic (Click for CLI, CustomTkinter for GUI) from the core functionality.
- **Core Engine Modules**:
  - `checker.py` tracks versions and installations.
  - `installer.py` maps and executes OS-specific download/install steps.
  - `updater.py` handles PEP 440–aware updates.
- **Configuration Registry (`tools.json`)**: Acts as a decoupled declarative database mapping abstract tool names to concrete terminal commands and download links.

---

## 🔧 Extending tools.json

Adding a new tool is incredibly easy. Open `tool_manager/config/tools.json` and add a new block. **No Python code modification is needed.**

```json
{
  "newtool": {
    "description": "My hardware tool",
    "category": "synthesizer",
    "check": "newtool --version",
    "version_regex": "\\b(\\d+\\.\\d+[\\w.-]*)\\b",
    "latest_version": "1.0.5",
    "install": {
      "windows": "winget install newtool",
      "linux": "sudo apt install newtool",
      "macos": "brew install newtool"
    }
  }
}
```

---

## 🧪 Troubleshooting & Development

### Logs
Having issues? The manager keeps a rotating log for diagnostic purposes.
Check the logs located at: `logs/tool_manager.log`

You can also run commands with the verbose flag to immediately spot errors:
```bash
esim-tool-manager -v install kicad
```

### Running Tests
If you intend to contribute to the project, make sure all tests pass:
```bash
pip install pytest
pytest tests/
```
*(All tests heavily use mocked subprocess calls—no real software is downloaded during testing.)*

---

## 📄 License
This system is provided under the **MIT License**. See the [LICENSE](LICENSE) file for more information.
