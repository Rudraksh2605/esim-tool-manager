"""
CLI commands for the eSim Tool Manager.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tool_manager.core.checker import CheckResult, ToolChecker, ToolStatus
from tool_manager.core.dependencies import DependencyChecker, DependencyStatus
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater, UpdateAction, UpdateResult
from tool_manager.utils.logger import get_logger, setup_logging
from tool_manager.utils.os_utils import get_platform_info, get_platform_key

console = Console(safe_box=True)
logger = get_logger("cli.commands")

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "tools.json"


def _load_tools_config() -> dict:
    """Load the tool registry from the bundled JSON file."""

    if not _CONFIG_PATH.exists():
        console.print(f"[bold red]X[/] Configuration file not found: {_CONFIG_PATH}")
        raise SystemExit(1)

    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[bold red]X[/] Invalid JSON in tools.json: {exc}")
        raise SystemExit(1) from exc


def _status_badge(status: ToolStatus) -> str:
    """Return a short text badge for a tool status."""

    return {
        ToolStatus.INSTALLED: "[bold green]OK[/]",
        ToolStatus.MISSING: "[bold red]X[/]",
        ToolStatus.ERROR: "[bold yellow]![/]",
    }.get(status, "?")


def _dependency_badge(status: DependencyStatus) -> str:
    """Return a short text badge for a dependency status."""

    return {
        DependencyStatus.OK: "[bold green]OK[/]",
        DependencyStatus.WARNING: "[bold yellow]WARN[/]",
        DependencyStatus.MISSING: "[bold red]MISS[/]",
    }[status]


@click.group()
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output.")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be done without executing commands.",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, dry_run: bool) -> None:
    """
    eSim Tool Manager - manage external EDA tools from the command line.

    Install, check, update, and inspect tools required by the eSim ecosystem.
    """

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run

    setup_logging(verbose=verbose)
    logger.debug("CLI invoked with verbose=%s dry_run=%s", verbose, dry_run)


@cli.command()
@click.argument("tool")
@click.pass_context
def install(ctx: click.Context, tool: str) -> None:
    """Install a managed tool."""

    installer = ToolInstaller(_load_tools_config(), dry_run=ctx.obj["dry_run"])

    console.print()
    with console.status(f"[bold cyan]Installing {tool}...[/]", spinner="dots"):
        result = installer.install_tool(tool)

    if result.success:
        console.print(
            Panel(
                f"[bold green]OK[/]  {result.message}",
                title="Install Successful",
                border_style="green",
                box=box.ASCII,
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]X[/]  {result.message}",
                title="Install Failed",
                border_style="red",
                box=box.ASCII,
            )
        )

    if result.command_executed:
        console.print(f"  [dim]Command:[/] {result.command_executed}")
    if result.installed_bin_dir:
        console.print(f"  [dim]Bin Dir:[/] {result.installed_bin_dir}")
    if result.stderr:
        console.print(f"  [dim]stderr:[/] {result.stderr[:500]}")
    console.print()


@cli.command()
@click.argument("tool", required=False, default=None)
def check(tool: str | None) -> None:
    """Check installation status of one or all tools."""

    checker = ToolChecker(_load_tools_config())
    console.print()

    if tool:
        _print_check_result(checker.check_tool(tool))
        console.print()
        return

    console.print(
        Panel(
            "[bold]Dependency Check[/]",
            subtitle=f"Platform: {get_platform_key()}",
            border_style="cyan",
            box=box.ASCII,
        )
    )
    console.print()

    results = checker.check_all()
    for result in results:
        _print_check_result(result)

    installed = sum(1 for result in results if result.status == ToolStatus.INSTALLED)
    total = len(results)
    console.print()
    console.print(f"  [bold]{installed}/{total}[/] tools installed.\n")


def _print_check_result(result: CheckResult) -> None:
    """Pretty-print a single check result."""

    badge = _status_badge(result.status)
    version = f" [dim](v{result.version})[/]" if result.version else ""

    if result.status == ToolStatus.ERROR and result.error_message:
        console.print(
            f"  {badge} [bold]{result.tool_name}[/]{version}  -  "
            f"[yellow]{result.status.value}[/]: {result.error_message}"
        )
        return

    style = "red" if result.status == ToolStatus.MISSING else "white"
    console.print(
        f"  {badge} [bold]{result.tool_name}[/]{version}  -  "
        f"[{style}]{result.status.value}[/]"
    )


@cli.command("list")
def list_tools() -> None:
    """List all registered tools."""

    config = _load_tools_config()
    platform_key = get_platform_key()

    table = Table(
        title="Registered Tools",
        box=box.ASCII,
        show_lines=True,
        title_style="bold cyan",
        header_style="bold white",
    )
    table.add_column("#", justify="right", width=4, style="dim")
    table.add_column("Tool", style="bold")
    table.add_column("Category")
    table.add_column("Description", max_width=45)
    table.add_column("Install Cmd", max_width=50, style="dim")
    table.add_column("Homepage", style="cyan")

    for index, (name, cfg) in enumerate(config.items(), start=1):
        table.add_row(
            str(index),
            name,
            cfg.get("category", "n/a"),
            cfg.get("description", "n/a"),
            cfg.get("install", {}).get(platform_key, "n/a"),
            cfg.get("homepage", "n/a"),
        )

    console.print()
    console.print(table)
    console.print()


@cli.command()
@click.argument("tool")
@click.option(
    "--check-only",
    is_flag=True,
    default=False,
    help="Only check if an update is available.",
)
@click.pass_context
def update(ctx: click.Context, tool: str, check_only: bool) -> None:
    """Check for and apply updates to a managed tool."""

    config = _load_tools_config()
    updater = ToolUpdater(
        config,
        ToolChecker(config),
        ToolInstaller(config, dry_run=ctx.obj["dry_run"]),
    )

    console.print()
    if check_only:
        result = updater.check_update(tool)
    else:
        with console.status(f"[bold cyan]Updating {tool}...[/]", spinner="dots"):
            result = updater.update_tool(tool)

    _print_update_result(result)
    console.print()


def _print_update_result(result: UpdateResult) -> None:
    """Pretty-print a single update result."""

    action_styles = {
        UpdateAction.UP_TO_DATE: ("green", "OK"),
        UpdateAction.UPDATE_AVAILABLE: ("yellow", "UPD"),
        UpdateAction.UPDATED: ("green", "OK"),
        UpdateAction.NOT_INSTALLED: ("red", "X"),
        UpdateAction.ERROR: ("red", "ERR"),
    }
    color, badge = action_styles.get(result.action, ("white", "?"))

    console.print(
        Panel(
            f"[bold {color}]{badge}[/]  {result.message}",
            title=f"Update - {result.tool_name}",
            border_style=color,
            box=box.ASCII,
        )
    )


@cli.command()
def doctor() -> None:
    """Inspect install prerequisites and local environment dependencies."""

    dependency_checker = DependencyChecker(_load_tools_config())
    results = (
        dependency_checker.check_system_dependencies()
        + dependency_checker.check_tool_dependencies()
    )

    table = Table(
        title="Dependency Doctor",
        box=box.ASCII,
        show_lines=True,
        title_style="bold cyan",
        header_style="bold white",
    )
    table.add_column("Scope", style="bold")
    table.add_column("Check", style="bold")
    table.add_column("Status", width=8)
    table.add_column("Details", max_width=70)

    for result in results:
        table.add_row(
            result.tool_name or "system",
            result.name,
            _dependency_badge(result.status),
            result.message,
        )

    missing = sum(1 for result in results if result.status == DependencyStatus.MISSING)
    warnings = sum(1 for result in results if result.status == DependencyStatus.WARNING)

    console.print()
    console.print(table)
    console.print()
    console.print(
        f"  [bold]{len(results)}[/] checks run, "
        f"[bold red]{missing}[/] missing, "
        f"[bold yellow]{warnings}[/] warnings.\n"
    )


@cli.command()
def status() -> None:
    """Display platform diagnostics and a summary of tool states."""

    info = get_platform_info()
    config = _load_tools_config()
    results = ToolChecker(config).check_all()

    console.print()
    console.print(
        Panel(
            "[bold]eSim Tool Manager - System Status[/]",
            border_style="cyan",
            box=box.ASCII,
        )
    )

    platform_table = Table(box=box.ASCII, show_header=False, padding=(0, 2))
    platform_table.add_column("Key", style="bold")
    platform_table.add_column("Value")
    for key, value in info.items():
        platform_table.add_row(key.replace("_", " ").title(), str(value))

    console.print(platform_table)
    console.print()

    summary_table = Table(
        title="Tool Status Summary",
        box=box.ASCII,
        title_style="bold",
        header_style="bold white",
    )
    summary_table.add_column("Tool", style="bold")
    summary_table.add_column("Status")
    summary_table.add_column("Version")
    summary_table.add_column("Latest")

    for result in results:
        summary_table.add_row(
            result.tool_name,
            f"{_status_badge(result.status)} {result.status.value}",
            result.version or "n/a",
            config.get(result.tool_name, {}).get("latest_version", "n/a"),
        )

    console.print(summary_table)
    console.print()
