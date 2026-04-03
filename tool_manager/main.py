"""
eSim Tool Manager — Entry Point.

This module wires up the CLI and serves as the main executable entry point.
Run with:
    python -m tool_manager
    python tool_manager/main.py
"""

from tool_manager.cli.commands import cli


def main() -> None:
    """Launch the CLI application."""
    cli()


if __name__ == "__main__":
    main()
