"""
Settings Frame — Application preferences.

Provides controls for appearance mode, color theme, command timeouts,
and an About section with version info.
"""

import customtkinter as ctk
from tool_manager.gui.widgets import COLORS, SectionHeader
from tool_manager import __version__, __author__


class SettingsFrame(ctk.CTkFrame):
    """Settings panel with appearance, timeout, and about sections."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_blue"],
        )
        self._scroll.pack(fill="both", expand=True)

        self._build_ui()

    def _build_ui(self):
        container = self._scroll

        # ── Header ───────────────────────────────────────────────────
        SectionHeader(
            container,
            title="Settings",
            subtitle="Customize the application experience",
            icon="⚙️",
        ).pack(anchor="w", padx=24, pady=(20, 16))

        # ═══════════════════════════════════════════════════════════════
        # Appearance Section
        # ═══════════════════════════════════════════════════════════════
        self._section_card(
            container,
            title="🎨  Appearance",
            children_builder=self._build_appearance,
        )

        # ═══════════════════════════════════════════════════════════════
        # Performance Section
        # ═══════════════════════════════════════════════════════════════
        self._section_card(
            container,
            title="⚡  Performance",
            children_builder=self._build_performance,
        )

        # ═══════════════════════════════════════════════════════════════
        # About Section
        # ═══════════════════════════════════════════════════════════════
        self._section_card(
            container,
            title="ℹ️  About",
            children_builder=self._build_about,
        )

    # ── Section Card Builder ─────────────────────────────────────────

    def _section_card(self, parent, title: str, children_builder):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.pack(fill="x", padx=24, pady=(0, 12))

        # Title
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=20, pady=(16, 12))

        # Divider
        ctk.CTkFrame(card, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20
        )

        # Content
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=(12, 16))
        children_builder(content)

    # ── Appearance Controls ──────────────────────────────────────────

    def _build_appearance(self, parent):
        # Mode selector
        row1 = ctk.CTkFrame(parent, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            row1,
            text="Appearance Mode",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        ctk.CTkLabel(
            row1,
            text="Switch between light, dark, and system themes",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(12, 0))

        self._mode_menu = ctk.CTkOptionMenu(
            row1,
            values=["Dark", "Light", "System"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["accent_blue"],
            button_hover_color="#3a85e0",
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=130,
            command=self._on_mode_change,
        )
        self._mode_menu.pack(side="right")
        self._mode_menu.set(ctk.get_appearance_mode())

        # Color theme
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            row2,
            text="Color Theme",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        ctk.CTkLabel(
            row2,
            text="Accent color scheme for the UI",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(12, 0))

        self._theme_menu = ctk.CTkOptionMenu(
            row2,
            values=["blue", "dark-blue", "green"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["accent_blue"],
            button_hover_color="#3a85e0",
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=130,
            command=self._on_theme_change,
        )
        self._theme_menu.pack(side="right")

        # UI Scaling
        row3 = ctk.CTkFrame(parent, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            row3,
            text="UI Scaling",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        self._scale_menu = ctk.CTkOptionMenu(
            row3,
            values=["80%", "90%", "100%", "110%", "120%"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["accent_blue"],
            button_hover_color="#3a85e0",
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=130,
            command=self._on_scale_change,
        )
        self._scale_menu.set("100%")
        self._scale_menu.pack(side="right")

    # ── Performance Controls ─────────────────────────────────────────

    def _build_performance(self, parent):
        # Check timeout
        row1 = ctk.CTkFrame(parent, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            row1,
            text="Check Timeout (seconds)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        ctk.CTkLabel(
            row1,
            text="Maximum wait for version check commands",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(12, 0))

        self._check_timeout_entry = ctk.CTkEntry(
            row1,
            font=ctk.CTkFont(family="Cascadia Code", size=12),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            height=32,
            width=80,
            justify="center",
        )
        self._check_timeout_entry.insert(0, "15")
        self._check_timeout_entry.pack(side="right")

        # Install timeout
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            row2,
            text="Install Timeout (seconds)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        ctk.CTkLabel(
            row2,
            text="Maximum wait for install/uninstall commands",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(12, 0))

        self._install_timeout_entry = ctk.CTkEntry(
            row2,
            font=ctk.CTkFont(family="Cascadia Code", size=12),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            height=32,
            width=80,
            justify="center",
        )
        self._install_timeout_entry.insert(0, "300")
        self._install_timeout_entry.pack(side="right")

    # ── About Section ────────────────────────────────────────────────

    def _build_about(self, parent):
        # App info
        info_frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_dark"],
            corner_radius=10,
        )
        info_frame.pack(fill="x", pady=(0, 8))

        lines = [
            ("Application", "eSim Tool Manager"),
            ("Version", __version__),
            ("Author", __author__),
            ("License", "MIT License"),
            ("Python Framework", "CustomTkinter 5.x"),
            ("Description", "Automated management of external EDA tools"),
        ]

        for key, val in lines:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=3)

            ctk.CTkLabel(
                row,
                text=f"{key}:",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=COLORS["text_secondary"],
                width=140,
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=val,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=COLORS["text_primary"],
                anchor="w",
            ).pack(side="left")

        # Padding
        ctk.CTkFrame(info_frame, fg_color="transparent", height=6).pack()

    # ── Callbacks ────────────────────────────────────────────────────

    @staticmethod
    def _on_mode_change(value: str):
        ctk.set_appearance_mode(value.lower())

    @staticmethod
    def _on_theme_change(value: str):
        ctk.set_default_color_theme(value)

    @staticmethod
    def _on_scale_change(value: str):
        scale = int(value.replace("%", "")) / 100
        ctk.set_widget_scaling(scale)
