# eSim Tool Manager

Automated Tool Manager for eSim, built as a Python-based prototype for the eSim Summer Fellowship 2026 submission task.

This project automates the download, installation, verification, and basic management of external EDA tools used by eSim. The current prototype focuses on Windows-first install automation for selected tools, while preserving a modular structure that can be extended for Linux and macOS.

## Submission Summary

This repository is organized to satisfy the submission deliverables requested in the task statement:

- `README.md`: repository overview plus clear execution and testing instructions
- `DESIGN.md`: detailed design document and project report
- `tool_manager/`: prototype implementation in Python
- `docs/`: PDF exports of the submission documents

## Requirements Addressed

The task asked for any two requirements. This project directly addresses the following:

1. Tool Installation Management
   - automatic download and installation for supported tools
   - version-aware registry for tool metadata
   - Windows-aware install logic with direct downloads, archive extraction, and PATH setup

2. Dependency Checker
   - environment readiness checks through the `doctor` command
   - package-manager availability checks
   - reporting for unsupported or manual-install cases

Additional partial coverage:

- User Interface
  - CLI built with Click and Rich
  - GUI built with CustomTkinter
- Version Checking
  - installed tool detection and version parsing through `check`
- Update Workflow
  - update check and reinstall flow for supported tools

## Problem Statement

eSim depends on multiple external tools such as Ngspice, KiCad, GHDL, Verilator, and Magic. Installing and maintaining these tools manually is time-consuming, error-prone, and platform-specific. This project proposes a single automated manager that can:

- maintain tool metadata in one place
- install tools with minimal user effort
- verify whether tools are available and usable
- update the user environment so installed tools can be reused from eSim
- expose the workflow through both CLI and GUI interfaces

## Prototype Features

- Direct download and install support for selected Windows tools
- Archive extraction support for `.zip` and `.7z` payloads
- Automatic user PATH updates after installation
- Local installed-binary discovery for project-managed tools
- Tool registry stored in `tool_manager/config/tools.json`
- Dependency diagnostics through `doctor`
- Version and status checks through `check` and `status`
- GUI-based install flow with background execution and progress feedback
- Rotating logs for diagnostics

## Repository Structure

```text
esim-tool-manager/
|-- README.md
|-- DESIGN.md
|-- requirements.txt
|-- setup.py
|-- docs/
|   |-- eSim_Tool_Manager_README.pdf
|   `-- eSim_Tool_Manager_Project_Documentation.pdf
|-- tests/
|-- tool_manager/
|   |-- cli/
|   |-- config/
|   |-- core/
|   |-- gui/
|   `-- utils/
`-- logs/
```

## Supported Prototype Scope

Current prototype behavior on Windows:

- `ngspice`: direct download, archive extraction, PATH setup, install verification
- `kicad`: direct installer URL configured, plus package-manager fallback
- `ghdl`: archive-based install support configured
- `verilator`: manual install path documented
- `magic`: manual install path documented

This is a proof-of-concept submission prototype, not a full production package manager.

## Installation Instructions

### Prerequisites

- Python 3.10 or higher
- Git
- Windows PowerShell

### Setup

1. Clone the repository:

```bash
git clone <your-private-repository-url>
cd esim-tool-manager
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

3. Install the project in editable mode:

```bash
pip install -e .
```

4. If you want to run tests separately:

```bash
pip install pytest
```

## How To Run

### CLI

Show help:

```bash
python -m tool_manager --help
```

List tools:

```bash
python -m tool_manager list
```

Check installed tools:

```bash
python -m tool_manager check
python -m tool_manager check ngspice
```

Install a tool:

```bash
python -m tool_manager install ngspice
```

Run dependency diagnostics:

```bash
python -m tool_manager doctor
```

Check update status:

```bash
python -m tool_manager update --check-only ngspice
```

### GUI

Launch the graphical interface:

```bash
python -m tool_manager --gui
```

In the GUI, the user can:

- inspect tool metadata
- click `Install` for supported tools
- monitor progress during installation
- re-check installation state after the task completes

## How To Test

Run the automated tests:

```bash
python -m pytest -q
```

The tests cover:

- checker logic
- installer logic
- dependency-check workflows
- downloader helpers
- CLI command behavior

## Generate PDF Documents

The submission PDFs can be regenerated with:

```bash
python docs/generate_pdfs.py
```

If `reportlab` is not already installed in your environment:

```bash
pip install reportlab
```

## Suggested Demo Flow

For a 5-10 minute presentation/demo, use this flow:

1. Introduce the problem: eSim depends on external tools and manual setup is tedious.
2. Show the tool registry in `tools.json`.
3. Run `python -m tool_manager doctor`.
4. Run `python -m tool_manager install ngspice`.
5. Run `python -m tool_manager check ngspice`.
6. Open the GUI and show the same workflow visually.
7. Close by showing modular design and future extensibility.

## Deliverables Mapping

### 1. Design Document

The detailed design document is available in:

- `DESIGN.md`
- `docs/eSim_Tool_Manager_Project_Documentation.pdf`

### 2. Code Implementation

The prototype implementation is available in:

- `tool_manager/`

It demonstrates:

- tool installation
- version/status checking
- dependency analysis
- GUI and CLI management

### 3. Execution Instructions

Execution instructions are included in this README under:

- Installation Instructions
- How To Run
- How To Test

### 4. Presentation

An optional presentation flow is included in this README and expanded in the design document appendix.

## Evaluation Criteria Alignment

- Functionality: installation, diagnostics, checking, and GUI/CLI flows are implemented
- Design: modular service-oriented structure with config-driven tool registry
- Documentation: README plus detailed project document and PDF exports
- Creativity: direct-download handling, archive install support, PATH registration, and dual UI model
- Code Quality: Python package structure, dataclasses, separation of concerns, and test coverage

## Submission Checklist

Before submitting, ensure the following:

1. Push this project to a private GitHub repository.
2. Grant access to the GitHub user:
   - `Eyantra698Sumanto`
3. Share the repository link and report by email to:
   - `contact-esim@fossee.in`
4. Use the email subject line exactly as requested:
   - `eSim Summer Fellowship 2026 Submission Task 5`

## Notes

- The project currently prioritizes Windows automation because that is where the prototype install flow was actively implemented and validated.
- Some tools are still marked as manual-install on native Windows due upstream distribution limitations.
- The architecture is intentionally modular so additional tools and platforms can be added with minimal code changes.
