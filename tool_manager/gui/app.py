"""
eSim Tool Manager — Main GUI Application.

Provides the root window, sidebar navigation, and frame switching logic.
Launch with:
    python -m tool_manager --gui
    esim-tool-manager-gui
"""

import json
import sys
from pathlib import Path

import customtkinter as ctk

from tool_manager.gui.widgets import COLORS
from tool_manager.gui.frames.dashboard import DashboardFrame
from tool_manager.gui.frames.tools import ToolsFrame
from tool_manager.gui.frames.logs import LogsFrame
from tool_manager.gui.frames.settings import SettingsFrame
from tool_manager.utils.logger import setup_logging
from tool_manager.utils.os_utils import get_platform_key, get_platform_info
from tool_manager import __version__


# ── Configuration ────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "tools.json"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _load_tools_config() -> dict:
    """Load the tool registry from tools.json."""
    if not _CONFIG_PATH.exists():
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Sidebar Button ───────────────────────────────────────────────────────────


class SidebarButton(ctk.CTkButton):
    """
    A navigation button for the sidebar with active-state styling
    and smooth hover transitions.
    """

    def __init__(
        self,
        master,
        text: str,
        icon: str,
        command=None,
        is_active: bool = False,
        **kwargs,
    ):
        self._icon = icon
        self._label_text = text
        self._is_active = is_active

        super().__init__(
            master,
            text=f"  {icon}   {text}",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLORS["accent_blue"] if is_active else "transparent",
            hover_color=COLORS["bg_card_hover"],
            text_color="#ffffff" if is_active else COLORS["text_secondary"],
            anchor="w",
            corner_radius=12,
            height=44,
            command=command,
            **kwargs,
        )

    def set_active(self, active: bool):
        self._is_active = active
        if active:
            self.configure(
                fg_color=COLORS["accent_blue"],
                text_color="#ffffff",
            )
        else:
            self.configure(
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
            )


# ── Main Application ────────────────────────────────────────────────────────


class App(ctk.CTk):
    """
    Root application window for the eSim Tool Manager GUI.

    Contains a persistent sidebar for navigation and a dynamic content
    area that swaps between Dashboard, Tools, Logs, and Settings frames.
    """

    def __init__(self):
        super().__init__()

        # ── Window configuration ─────────────────────────────────────
        self.title("eSim Tool Manager")
        self.geometry("1160x750")
        self.minsize(900, 600)
        self.configure(fg_color=COLORS["bg_dark"])

        # Load tools config
        self.tools_config = _load_tools_config()

        # ── Layout grid ──────────────────────────────────────────────
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────────────
        self._build_sidebar()

        # ── Content area ─────────────────────────────────────────────
        self._content_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_dark"],
            corner_radius=0,
        )
        self._content_frame.grid(row=0, column=1, sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # ── Status bar ───────────────────────────────────────────────
        self._build_status_bar()

        # ── Frames registry ──────────────────────────────────────────
        self._frames = {}
        self._active_frame_name = None

        # Show dashboard by default
        self._show_frame("dashboard")

    # ──────────────────────────────────────────────────────────────────
    # Sidebar
    # ──────────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=0,
            width=230,
        )
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_propagate(False)

        # ── Brand / Logo ─────────────────────────────────────────────
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(24, 4))

        ctk.CTkLabel(
            brand_frame,
            text="⚡",
            font=ctk.CTkFont(size=30),
        ).pack(side="left", padx=(0, 8))

        name_frame = ctk.CTkFrame(brand_frame, fg_color="transparent")
        name_frame.pack(side="left")

        ctk.CTkLabel(
            name_frame,
            text="eSim",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLORS["accent_blue"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            name_frame,
            text="Tool Manager",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_dim"],
        ).pack(anchor="w")

        # Version badge
        ver_badge = ctk.CTkFrame(
            sidebar,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
        )
        ver_badge.pack(padx=16, pady=(4, 20), anchor="w")
        ctk.CTkLabel(
            ver_badge,
            text=f"  v{__version__}  ",
            font=ctk.CTkFont(family="Cascadia Code", size=10),
            text_color=COLORS["text_dim"],
        ).pack(padx=4, pady=2)

        # Divider
        ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 16)
        )

        # ── Navigation label ─────────────────────────────────────────
        ctk.CTkLabel(
            sidebar,
            text="   NAVIGATION",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=COLORS["text_dim"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 6))

        # ── Nav buttons ──────────────────────────────────────────────
        nav_items = [
            ("dashboard", "📊", "Dashboard"),
            ("tools", "🛠️", "Tools"),
            ("logs", "📋", "Logs"),
            ("settings", "⚙️", "Settings"),
        ]

        self._nav_buttons = {}
        for key, icon, label in nav_items:
            btn = SidebarButton(
                sidebar,
                text=label,
                icon=icon,
                is_active=(key == "dashboard"),
                command=lambda k=key: self._show_frame(k),
            )
            btn.pack(fill="x", padx=12, pady=3)
            self._nav_buttons[key] = btn

        # ── Bottom spacer + quit ─────────────────────────────────────
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Divider
        ctk.CTkFrame(sidebar, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 8)
        )

        quit_btn = ctk.CTkButton(
            sidebar,
            text="  🚪   Quit",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color="transparent",
            hover_color=COLORS["accent_red"],
            text_color=COLORS["text_dim"],
            anchor="w",
            corner_radius=10,
            height=38,
            command=self._on_quit,
        )
        quit_btn.pack(fill="x", padx=12, pady=(0, 20))

    # ──────────────────────────────────────────────────────────────────
    # Status Bar
    # ──────────────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=0,
            height=32,
        )
        bar.grid(row=1, column=1, sticky="ew")
        bar.grid_propagate(False)

        info = get_platform_info()
        status_text = (
            f"  🖥 {info['system']} {info['release']}   •   "
            f"🐍 Python {info['python_version']}   •   "
            f"⚙ {info['machine']}   •   "
            f"🎯 {get_platform_key()}   •   "
            f"📦 {len(self.tools_config)} tools registered"
        )

        ctk.CTkLabel(
            bar,
            text=status_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=12, pady=4)

        ctk.CTkLabel(
            bar,
            text=f"eSim Tool Manager v{__version__}  ",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="right", padx=12, pady=4)

    # ──────────────────────────────────────────────────────────────────
    # Frame Switching
    # ──────────────────────────────────────────────────────────────────

    def _show_frame(self, name: str):
        """Switch the content area to the named frame."""
        if name == self._active_frame_name:
            return

        # Update nav button states
        for key, btn in self._nav_buttons.items():
            btn.set_active(key == name)

        # Hide current frame
        if self._active_frame_name and self._active_frame_name in self._frames:
            self._frames[self._active_frame_name].grid_forget()

        # Create frame if not yet instantiated
        if name not in self._frames:
            self._frames[name] = self._create_frame(name)

        # Show target frame
        self._frames[name].grid(row=0, column=0, sticky="nsew")
        self._active_frame_name = name

    def _create_frame(self, name: str) -> ctk.CTkFrame:
        """Lazily create and return the frame for the given name."""
        frame_map = {
            "dashboard": lambda: DashboardFrame(self._content_frame, self.tools_config),
            "tools": lambda: ToolsFrame(self._content_frame, self.tools_config),
            "logs": lambda: LogsFrame(self._content_frame),
            "settings": lambda: SettingsFrame(self._content_frame),
        }

        factory = frame_map.get(name)
        if factory:
            return factory()

        # Fallback empty frame
        fallback = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        ctk.CTkLabel(
            fallback,
            text=f"Frame '{name}' not implemented.",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_secondary"],
        ).pack(expand=True)
        return fallback

    def _on_quit(self):
        self.destroy()


# ── Entry Point ──────────────────────────────────────────────────────────────


def main():
    """Launch the eSim Tool Manager GUI."""
    setup_logging(verbose=False)
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
