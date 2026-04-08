# eSim Tool Manager
## Project Documentation and Design Report

## 1. Introduction

### 1.1 Objective

The goal of this project is to build an Automated Tool Manager for eSim that reduces the manual effort involved in downloading, installing, verifying, and managing external EDA tools. The prototype is implemented in Python and designed to be modular, extensible, and easy to demonstrate.

### 1.2 Motivation

eSim depends on several external tools such as Ngspice, KiCad, GHDL, Verilator, and Magic. Each tool has different installation methods, version-reporting formats, and operating-system specific behavior. Managing these manually creates problems such as:

- inconsistent versions across systems
- broken PATH configuration
- missing dependencies
- repeated setup work for new users
- poor visibility into what is installed and what is missing

This project addresses those issues through a unified management layer.

## 2. Requirements Selected

The task required implementing any two requirements. This project intentionally targets:

### 2.1 Tool Installation Management

- install metadata is stored in a declarative JSON registry
- tools can be installed through direct download, archive extraction, or package-manager commands
- Windows install flow can update the user PATH automatically
- install status is verified after execution

### 2.2 Dependency Checker

- the `doctor` command inspects environment readiness
- the system reports required package managers and missing prerequisites
- unsupported or manual-install cases are clearly surfaced to the user

### 2.3 Bonus Coverage

The prototype also partially addresses:

- Configuration Handling
- Update and Upgrade System
- User Interface

## 3. Scope of the Prototype

This repository is a proof-of-concept submission, not a complete production package manager. The current scope includes:

- tool registry and tool metadata management
- direct install support for selected tools
- version and availability checks
- dependency diagnostics
- CLI workflow
- GUI workflow
- logging and test coverage

The prototype has strongest support on Windows because the install flow was actively implemented and verified there.

## 4. High-Level Architecture

The system follows a layered architecture to keep concerns separate.

```text
User
 |-- CLI (Click + Rich)
 |-- GUI (CustomTkinter)
        |
        v
Core Services
 |-- ToolChecker
 |-- ToolInstaller
 |-- ToolUpdater
 |-- DependencyChecker
        |
        v
Configuration + Utilities
 |-- tools.json
 |-- downloader.py
 |-- os_utils.py
 |-- logger.py
        |
        v
Operating System + External Tools
```

### 4.1 Design Principles

- configuration-driven behavior
- separation of UI from business logic
- platform-aware execution
- safe and explicit error reporting
- minimal change required to add new tools

## 5. Module Breakdown

## 5.1 CLI Layer

Location:

- `tool_manager/cli/commands.py`

Responsibilities:

- parse user commands and flags
- load tool configuration
- call the appropriate core service
- render human-readable output in the terminal

Supported commands include:

- `list`
- `check`
- `install`
- `update`
- `doctor`
- `status`

## 5.2 GUI Layer

Location:

- `tool_manager/gui/`

Responsibilities:

- provide a point-and-click tool management interface
- keep the UI responsive through background threads
- surface install progress and outputs to the user
- mirror core features available in the CLI

Important GUI files:

- `app.py`: application bootstrap and navigation
- `frames/tools.py`: main tool-management workflow
- `widgets.py`: reusable GUI components

## 5.3 ToolChecker

Location:

- `tool_manager/core/checker.py`

Responsibilities:

- determine whether a tool is available
- run tool-specific version commands
- parse version strings with regex
- detect tools from project-managed install directories when shell PATH is not yet refreshed

Outputs:

- `CheckResult`
- status: `installed`, `missing`, or `error`

## 5.4 ToolInstaller

Location:

- `tool_manager/core/installer.py`

Responsibilities:

- select the correct installation strategy for the current platform
- perform direct downloads or command-based installs
- extract archives when required
- update PATH after installation
- verify successful installation

Supported install strategies:

- package-manager command
- direct executable installer
- archive extraction (`.zip`, `.7z`)
- manual-install fallback when automation is not feasible

## 5.5 ToolUpdater

Location:

- `tool_manager/core/updater.py`

Responsibilities:

- compare installed version with target version
- report whether an update is available
- reuse installer logic to perform the update flow

## 5.6 DependencyChecker

Location:

- `tool_manager/core/dependencies.py`

Responsibilities:

- verify platform support
- verify Python runtime compatibility
- verify logs directory availability
- check for package managers such as `winget`, `apt`, or `brew`
- report whether a tool has an automatic install route on the current OS

## 5.7 Downloader and Utility Layer

Locations:

- `tool_manager/utils/downloader.py`
- `tool_manager/utils/os_utils.py`
- `tool_manager/utils/logger.py`

Responsibilities:

- resolve binary URLs from landing pages when providers use redirect-based downloads
- validate that the download is a real binary/archive and not HTML
- extract archives safely
- manage process and user PATH updates
- provide platform-detection helpers
- write logs to rotating log files

## 5.8 Configuration Registry

Location:

- `tool_manager/config/tools.json`

Responsibilities:

- store tool metadata
- define install/check/uninstall behavior
- map platform-specific commands and download sources
- define version regex and binary hints

This config-driven approach keeps tool support extensible without hardcoding every tool into Python logic.

## 6. Detailed Workflow

## 6.1 Installation Flow

1. The user triggers install through CLI or GUI.
2. The installer loads the tool entry from `tools.json`.
3. It chooses a platform-specific strategy:
   - direct download
   - archive extraction
   - package-manager command
   - manual fallback
4. The install action runs in the background.
5. The manager discovers the installed executable location.
6. The PATH is updated.
7. The checker verifies tool availability.
8. The result is shown to the user and written to logs.

## 6.2 Version-Check Flow

1. The user runs `check` or opens the GUI status view.
2. The checker resolves the tool metadata.
3. It tries to locate the tool:
   - from the system PATH
   - from a project-managed install directory
   - from configured path hints/globs
4. It runs the configured check command.
5. It parses the output using the configured regex.
6. It returns a structured status result.

## 6.3 Dependency-Check Flow

1. The user runs `doctor`.
2. The dependency checker examines the environment.
3. It reports:
   - supported platform
   - Python baseline
   - package-manager availability
   - automatic-install readiness for each tool
4. The results are summarized in a readable table.

## 6.4 GUI Install Flow

1. The user clicks `Install`.
2. The GUI disables the action buttons.
3. A background thread performs the installation.
4. The progress overlay updates the current stage:
   - preparing
   - downloading
   - extracting or running installer
   - verifying
5. Output is displayed after completion.
6. The GUI triggers a fresh check to refresh status.

## 7. Data Model

Each tool entry in `tools.json` may contain:

- `description`
- `category`
- `binary_names`
- `check`
- `version_regex`
- `latest_version`
- `install`
- `download`
- `uninstall`
- `path_hints`
- `path_globs`
- `homepage`

This data model allows the same codebase to support multiple tools with different install mechanics.

## 8. Current Prototype Capability

### 8.1 Implemented and Validated

- direct archive install for `ngspice`
- direct installer metadata for `kicad`
- archive-based metadata for `ghdl`
- dependency diagnostics through `doctor`
- CLI and GUI integration

### 8.2 Partially Implemented

- update workflow
- cross-platform expansion for all tools
- richer version parsing for every upstream tool

### 8.3 Manual Cases

Some tools still require manual installation on native Windows due upstream distribution limitations or lack of a stable automation source.

## 9. Error Handling Strategy

The project emphasizes graceful failure. Typical failure scenarios include:

- missing tool entry
- invalid configuration
- unsupported platform
- HTML landing page downloaded instead of binary
- archive extraction failure
- installer timeout
- permission problems

The system responds with:

- structured error messages
- non-crashing CLI output
- GUI feedback dialogs/output panels
- logged diagnostic information

## 10. Configuration Handling

The manager updates tool availability through:

- direct executable discovery
- archive-based local install folders
- PATH updates in the current process
- persistent user PATH updates on Windows

This directly supports the requirement that installed tools should work seamlessly with eSim after setup.

## 11. Testing Strategy

Automated tests are provided in `tests/` and cover:

- checker behavior
- installer behavior
- downloader helpers
- dependency diagnostics
- CLI command paths

The tests use mocks wherever possible so the suite stays safe and repeatable.

Execution:

```bash
python -m pytest -q
```

## 12. Instructions for Execution

## 12.1 Setup

```bash
git clone <your-private-repository-url>
cd esim-tool-manager
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## 12.2 Run the Prototype

CLI:

```bash
python -m tool_manager --help
python -m tool_manager doctor
python -m tool_manager install ngspice
python -m tool_manager check ngspice
```

GUI:

```bash
python -m tool_manager --gui
```

## 12.3 Test the Prototype

```bash
python -m pytest -q
```

## 13. Evaluation Criteria Mapping

### 13.1 Functionality

The prototype supports installation, checking, diagnostics, and basic updates. It demonstrates the core value of an automated manager rather than remaining a static registry.

### 13.2 Design

The architecture is modular and layered. UI logic, core services, config, and utilities are separated so the project is easier to maintain and extend.

### 13.3 Documentation

The repository includes:

- a practical README
- a detailed design document
- PDF exports for submission

### 13.4 Creativity

Notable implementation ideas include:

- direct-download resolution from landing pages
- archive-based local installs for Windows tools
- project-managed binary discovery even before a terminal restart
- dual-interface access through CLI and GUI

### 13.5 Code Quality

The codebase is organized as a Python package with:

- dataclass-based result objects
- focused modules
- reusable utility helpers
- automated tests

## 14. Limitations

- the tool coverage is still partial
- Windows support is stronger than Linux/macOS in the current prototype
- some version commands are tool-specific and may need refinement
- update logic currently reuses install logic rather than implementing delta updates

## 15. Future Improvements

- add complete cross-platform support for every tool
- add uninstall manager parity with install manager
- add richer configuration profiles for eSim integration
- add remote metadata updates
- add checksum verification for downloaded binaries
- add package-source mirroring and retry logic
- add scheduled update checks

## 16. Optional Presentation Outline

Suggested 5-10 minute presentation flow:

1. Explain the eSim tool-management problem.
2. State the two primary requirements targeted.
3. Show the architecture diagram and module split.
4. Demonstrate `doctor`.
5. Demonstrate `install ngspice`.
6. Demonstrate `check ngspice`.
7. Show the GUI install flow.
8. Close with future improvements and extensibility.

## 17. Submission Guidelines Checklist

Before final submission:

1. Push the repository to a private GitHub repository.
2. Grant access to `Eyantra698Sumanto`.
3. Email the repository link and report to `contact-esim@fossee.in`.
4. Use the subject line:
   `eSim Summer Fellowship 2026 Submission Task 5`

## 18. Conclusion

This project demonstrates a practical automated tool manager for eSim with a modular Python implementation, direct installation workflows, dependency diagnostics, version checking, and a dual CLI/GUI interface. It satisfies the requested screening-task goals while remaining extensible for future development.
