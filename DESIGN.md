# eSim Tool Manager — Design Document

## 1. Overview

The eSim Tool Manager is a command-line application built in Python that
automates the lifecycle management of external EDA (Electronic Design
Automation) tools required by the eSim platform. It follows the architectural
patterns of mature package managers (apt, pip, brew) while remaining lightweight
and extensible.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      USER  (Terminal)                        │
└──────────────────────┬───────────────────────────────────────┘
                       │  CLI invocation
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                   CLI Layer  (Click)                         │
│  cli/commands.py                                             │
│  • Parses arguments & flags (--verbose, --dry-run)           │
│  • Dispatches to core modules                                │
│  • Renders Rich output (tables, panels, icons)               │
└──────────────────────┬───────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌──────────────┐ ┌───────────┐ ┌───────────┐
│  Checker     │ │ Installer │ │ Updater   │
│  checker.py  │ │installer. │ │ updater.  │
│              │ │   py      │ │   py      │
│ • Run check  │ │ • Select  │ │ • Compare │
│   commands   │ │   OS cmd  │ │   versions│
│ • Extract    │ │ • Execute │ │ • Trigger │
│   versions   │ │   install │ │   reinstal│
│ • Return     │ │ • Dry-run │ │   -lation │
│   status     │ │   support │ │           │
└──────┬───────┘ └─────┬─────┘ └─────┬─────┘
       │               │             │
       └───────────┬───┘─────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                  Utility Layer                               │
│  utils/os_utils.py     • Platform detection (Enum-based)     │
│                        • Shell prefix selection              │
│                        • Admin privilege check               │
│  utils/logger.py       • Rotating file handler (5 MB × 3)   │
│                        • Console handler (verbose toggle)    │
└──────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                 Configuration Layer                          │
│  config/tools.json                                           │
│  • Declarative tool registry                                 │
│  • Per-platform install/uninstall commands                    │
│  • Version regex & latest version metadata                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Module Responsibilities

### 3.1 CLI Layer (`cli/commands.py`)
- **Framework**: Click with decorators for command/group definitions.
- **Rendering**: Rich Console, Table, Panel, and Text for styled output.
- **Global context**: `--verbose` and `--dry-run` flags propagated via
  `click.Context.obj`.
- **Commands**: `install`, `check`, `list`, `update`, `status`.

### 3.2 Core Layer

#### `core/checker.py` — ToolChecker
- Runs the `check` command for a tool via `subprocess.run()`.
- Captures both stdout and stderr.
- Extracts version strings using configurable regex patterns.
- Returns `CheckResult` dataclass with status enum
  (INSTALLED / MISSING / ERROR).

#### `core/installer.py` — ToolInstaller
- Looks up the OS-specific install command from `tools.json`.
- Supports **dry-run** mode (logs the command, skips execution).
- Handles `subprocess.TimeoutExpired`, `PermissionError`, and generic
  exceptions.
- Returns `InstallResult` dataclass with stdout/stderr/return code.

#### `core/updater.py` — ToolUpdater
- Delegates to `ToolChecker` to obtain the installed version.
- Compares against `latest_version` from config using `packaging.version`.
- Falls back to string comparison for non-PEP 440 versions.
- Optionally triggers `ToolInstaller.install_tool()` for the update.

### 3.3 Utility Layer

#### `utils/os_utils.py`
- `detect_platform()` → `Platform` enum.
- `get_platform_key()` → string key for tools.json lookup.
- `get_shell_command_prefix()` → `["cmd", "/c"]` or `["/bin/sh", "-c"]`.
- `is_admin()` → bool (Windows via ctypes, Unix via os.geteuid).
- `get_platform_info()` → dict for diagnostics.

#### `utils/logger.py`
- Singleton-pattern initialization (idempotent `setup_logging()`).
- `RotatingFileHandler` at `logs/tool_manager.log` (5 MB, 3 backups).
- `StreamHandler` respects `--verbose` flag.
- `get_logger(name)` returns a child logger.

### 3.4 Configuration (`config/tools.json`)
- JSON object keyed by tool name.
- Each entry includes: `description`, `category`, `check`, `version_regex`,
  `latest_version`, `install` (per-OS), `uninstall` (per-OS), `homepage`.
- New tools are added here — no Python code changes needed.

---

## 4. Data Flow

### 4.1 `install <tool>`
1. CLI parses tool name and `--dry-run` flag.
2. `ToolInstaller` loads config, selects OS command.
3. If dry-run: log and return.
4. Otherwise: `subprocess.run(cmd, shell=True)`.
5. Capture return code, stdout, stderr → `InstallResult`.
6. CLI renders success panel or error panel.

### 4.2 `check [tool]`
1. CLI parses optional tool name.
2. `ToolChecker.check_tool()` or `.check_all()`.
3. For each tool: run check command → extract version via regex.
4. Return `CheckResult` with `ToolStatus` enum.
5. CLI prints icon + version + status line.

### 4.3 `update <tool>`
1. CLI parses tool name and `--check-only` flag.
2. `ToolUpdater.check_update()` calls checker, compares versions.
3. If `--check-only`: return comparison result.
4. If update available and not check-only: call
   `ToolInstaller.install_tool()`.
5. Return `UpdateResult` with action enum.

### 4.4 `status`
1. Gather `get_platform_info()` → diagnostics table.
2. `ToolChecker.check_all()` → summary table.
3. Merge with `latest_version` from config.
4. Render two Rich tables.

---

## 5. Error Handling Strategy

| Error Type | Handler | User Impact |
|---|---|---|
| Tool not in config | Early return with message | No crash |
| Command not found | `FileNotFoundError` → MISSING | Clean status |
| Timeout | `TimeoutExpired` → ERROR | Clear message |
| Permission denied | `PermissionError` → ERROR | Suggests elevation |
| Invalid JSON | `JSONDecodeError` → SystemExit(1) | Immediate feedback |
| Unexpected | Generic `Exception` → logged + ERROR | Stack in log file |

---

## 6. Extensibility Points

1. **New tools**: Add entry to `tools.json`.
2. **New platforms**: Add key to each tool's `install`/`uninstall` dict.
3. **New commands**: Add `@cli.command()` in `commands.py`.
4. **Custom check logic**: Subclass `ToolChecker` and override
   `_extract_version()`.
5. **Plugin system (future)**: Tool definitions could be loaded from
   multiple JSON files or a plugin directory.

---

## 7. Testing Strategy

- **Unit tests**: Each core class tested with mocked `subprocess.run`.
- **Integration tests**: `CliRunner` exercises the full CLI pipeline.
- **No side effects**: All tests run without installing real software.
- **Coverage targets**: checker, installer, updater, os_utils, CLI commands.
