"""
CLI Commands for eSim Tool Manager.

Defines all user-facing commands using the Click framework with rich console
output for a polished developer experience.
"""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from tool_manager.core.checker import ToolChecker, ToolStatus
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater, UpdateAction
from tool_manager.utils.logger import setup_logging, get_logger
from tool_manager.utils.os_utils import (
    get_platform_key,
    get_platform_info,
    detect_platform,
)

console = Console()
logger = get_logger("cli.commands")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "tools.json"


def _load_tools_config() -> dict:
    """Load and return the tool registry from tools.json."""
    if not _CONFIG_PATH.exists():
        console.print(
            f"[bold red]✗[/] Configuration file not found: {_CONFIG_PATH}"
        )
        raise SystemExit(1)

    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            console.print(f"[bold red]✗[/] Invalid JSON in tools.json: {exc}")
            raise SystemExit(1)

    logger.debug("Loaded %d tool(s) from %s", len(data), _CONFIG_PATH)
    return data


def _status_icon(status: ToolStatus) -> str:
    """Map a ToolStatus to a rich-formatted icon string."""
    return {
        ToolStatus.INSTALLED: "[bold green]✔[/]",
        ToolStatus.MISSING: "[bold red]✗[/]",
        ToolStatus.ERROR: "[bold yellow]⚠[/]",
    }.get(status, "?")


# ---------------------------------------------------------------------------
# Click group
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable verbose output."
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be done without executing.",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, dry_run: bool) -> None:
    """
    eSim Tool Manager — manage external EDA tools from the command line.

    Install, check, update, and inspect tools required by the eSim
    electronic circuit simulation platform.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run

    setup_logging(verbose=verbose)
    logger.debug("CLI invoked: verbose=%s, dry_run=%s", verbose, dry_run)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("tool")
@click.pass_context
def install(ctx: click.Context, tool: str) -> None:
    """Install a managed tool (e.g. ngspice, kicad)."""
    config = _load_tools_config()
    dry_run = ctx.obj["dry_run"]

    installer = ToolInstaller(config, dry_run=dry_run)

    console.print()
    with console.status(f"[bold cyan]Installing {tool}…[/]", spinner="dots"):
        result = installer.install_tool(tool)

    if result.success:
        console.print(
            Panel(
                f"[bold green]✔[/]  {result.message}",
                title="Install Successful",
                border_style="green",
                box=box.ROUNDED,
            )
        )
        if result.command_executed:
            console.print(f"  [dim]Command:[/] {result.command_executed}")
    else:
        console.print(
            Panel(
                f"[bold red]✗[/]  {result.message}",
                title="Install Failed",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        if result.stderr:
            console.print(f"  [dim]stderr:[/] {result.stderr[:500]}")

    console.print()


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("tool", required=False, default=None)
@click.pass_context
def check(ctx: click.Context, tool: str | None) -> None:
    """Check installation status of one or all tools."""
    config = _load_tools_config()
    checker = ToolChecker(config)

    console.print()

    if tool:
        result = checker.check_tool(tool)
        _print_check_result(result)
    else:
        console.print(
            Panel(
                "[bold]Dependency Check[/]",
                subtitle=f"Platform: {get_platform_key()}",
                border_style="cyan",
                box=box.DOUBLE,
            )
        )
        console.print()
        results = checker.check_all()
        for r in results:
            _print_check_result(r)

        installed = sum(1 for r in results if r.status == ToolStatus.INSTALLED)
        total = len(results)
        console.print()
        console.print(
            f"  [bold]{installed}/{total}[/] tools installed.\n"
        )


def _print_check_result(result) -> None:
    """Pretty-print a single CheckResult."""
    icon = _status_icon(result.status)
    version_str = f" [dim](v{result.version})[/]" if result.version else ""
    status_label = result.status.value

    if result.status == ToolStatus.INSTALLED:
        console.print(f"  {icon} [bold]{result.tool_name}[/]{version_str}  —  {status_label}")
    elif result.status == ToolStatus.MISSING:
        console.print(f"  {icon} [bold]{result.tool_name}[/]  —  [red]{status_label}[/]")
    else:
        err = result.error_message or "unknown error"
        console.print(
            f"  {icon} [bold]{result.tool_name}[/]  —  [yellow]{status_label}[/]: {err}"
        )


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@cli.command("list")
@click.pass_context
def list_tools(ctx: click.Context) -> None:
    """List all registered tools and their metadata."""
    config = _load_tools_config()
    platform_key = get_platform_key()

    table = Table(
        title="Registered Tools",
        box=box.SIMPLE_HEAVY,
        show_lines=True,
        title_style="bold cyan",
        header_style="bold white",
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Tool", style="bold")
    table.add_column("Category")
    table.add_column("Description", max_width=45)
    table.add_column("Install Cmd", max_width=50, style="dim")
    table.add_column("Homepage", style="cyan")

    for idx, (name, cfg) in enumerate(config.items(), start=1):
        install_cmd = cfg.get("install", {}).get(platform_key, "N/A")
        table.add_row(
            str(idx),
            name,
            cfg.get("category", "—"),
            cfg.get("description", "—"),
            install_cmd,
            cfg.get("homepage", "—"),
        )

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("tool")
@click.option(
    "--check-only",
    is_flag=True,
    default=False,
    help="Only check if an update is available; don't install it.",
)
@click.pass_context
def update(ctx: click.Context, tool: str, check_only: bool) -> None:
    """Check for and apply updates to a managed tool."""
    config = _load_tools_config()
    dry_run = ctx.obj["dry_run"]

    checker = ToolChecker(config)
    installer = ToolInstaller(config, dry_run=dry_run)
    updater = ToolUpdater(config, checker, installer)

    console.print()

    if check_only:
        result = updater.check_update(tool)
    else:
        with console.status(f"[bold cyan]Updating {tool}…[/]", spinner="dots"):
            result = updater.update_tool(tool)

    _print_update_result(result)
    console.print()


def _print_update_result(result) -> None:
    """Pretty-print an UpdateResult."""
    action_styles = {
        UpdateAction.UP_TO_DATE: ("green", "✔"),
        UpdateAction.UPDATE_AVAILABLE: ("yellow", "⬆"),
        UpdateAction.UPDATED: ("green", "✔"),
        UpdateAction.NOT_INSTALLED: ("red", "✗"),
        UpdateAction.ERROR: ("red", "⚠"),
    }
    color, icon = action_styles.get(result.action, ("white", "?"))

    console.print(
        Panel(
            f"[bold {color}]{icon}[/]  {result.message}",
            title=f"Update — {result.tool_name}",
            border_style=color,
            box=box.ROUNDED,
        )
    )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Display system status and platform diagnostics."""
    info = get_platform_info()
    config = _load_tools_config()
    checker = ToolChecker(config)

    console.print()
    console.print(
        Panel(
            "[bold]eSim Tool Manager — System Status[/]",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )

    # Platform table
    plat_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    plat_table.add_column("Key", style="bold")
    plat_table.add_column("Value")
    for k, v in info.items():
        plat_table.add_row(k.replace("_", " ").title(), str(v))
    console.print(plat_table)
    console.print()

    # Tool summary
    results = checker.check_all()

    summary_table = Table(
        title="Tool Status Summary",
        box=box.ROUNDED,
        title_style="bold",
        header_style="bold white",
    )
    summary_table.add_column("Tool", style="bold")
    summary_table.add_column("Status")
    summary_table.add_column("Version")
    summary_table.add_column("Latest")

    for r in results:
        icon = _status_icon(r.status)
        ver = r.version or "—"
        latest = config[r.tool_name].get("latest_version", "—") if r.tool_name in config else "—"
        summary_table.add_row(r.tool_name, f"{icon} {r.status.value}", ver, latest)

    console.print(summary_table)
    console.print()
