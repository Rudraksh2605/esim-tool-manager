"""
eSim Tool Manager — Entry Point.

This module wires up the CLI and serves as the main executable entry point.
Run with:
    python -m tool_manager          # CLI (default)
    python -m tool_manager --gui    # GUI
    python -m tool_manager --gui --verbose   # GUI with debug logging
    python tool_manager/main.py
"""

import sys


def main() -> None:
    """Launch the CLI or GUI application based on arguments."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    if "--verbose" in sys.argv:
        sys.argv.remove("--verbose")
    if "-v" in sys.argv:
        sys.argv.remove("-v")

    if "--gui" in sys.argv:
        sys.argv.remove("--gui")
        from tool_manager.gui.app import main as gui_main
        gui_main(verbose=verbose)
    else:
        # Re-inject verbose flag so Click picks it up
        if verbose and "--verbose" not in sys.argv:
            sys.argv.insert(1, "--verbose")
        from tool_manager.cli.commands import cli
        cli()


if __name__ == "__main__":
    main()

