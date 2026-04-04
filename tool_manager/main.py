"""
eSim Tool Manager — Entry Point.

This module wires up the CLI and serves as the main executable entry point.
Run with:
    python -m tool_manager          # CLI (default)
    python -m tool_manager --gui    # GUI
    python tool_manager/main.py
"""

import sys


def main() -> None:
    """Launch the CLI or GUI application based on arguments."""
    if "--gui" in sys.argv:
        sys.argv.remove("--gui")
        from tool_manager.gui.app import main as gui_main
        gui_main()
    else:
        from tool_manager.cli.commands import cli
        cli()


if __name__ == "__main__":
    main()

