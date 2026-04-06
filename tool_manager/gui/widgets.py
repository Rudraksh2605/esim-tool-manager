"""
Reusable Custom Widgets for the eSim Tool Manager GUI.

Provides styled, production-quality components used across all frames:
ToolCard, StatusBadge, AnimatedButton, SectionHeader, StatCard.
"""

import customtkinter as ctk
import webbrowser
from typing import Optional, Callable


# ── Color Palette ────────────────────────────────────────────────────────────

COLORS = {
    "bg_dark": "#0f1117",
    "bg_card": "#1a1d27",
    "bg_card_hover": "#222633",
    "bg_sidebar": "#141620",
    "accent_blue": "#4a9eff",
    "accent_green": "#34d399",
    "accent_red": "#f87171",
    "accent_amber": "#fbbf24",
    "accent_purple": "#a78bfa",
    "accent_cyan": "#22d3ee",
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_dim": "#64748b",
    "border": "#2a2e3d",
    "border_focus": "#4a9eff",
    "success_bg": "#052e16",
    "error_bg": "#450a0a",
    "warning_bg": "#422006",
    "gradient_start": "#4a9eff",
    "gradient_end": "#a78bfa",
}

STATUS_COLORS = {
    "installed": {"bg": "#052e16", "fg": "#34d399", "border": "#166534"},
    "missing": {"bg": "#450a0a", "fg": "#f87171", "border": "#991b1b"},
    "error": {"bg": "#422006", "fg": "#fbbf24", "border": "#92400e"},
}

CATEGORY_COLORS = {
    "simulator": "#4a9eff",
    "eda": "#a78bfa",
    "layout": "#22d3ee",
    "default": "#94a3b8",
}


# ── Status Badge ─────────────────────────────────────────────────────────────


class StatusBadge(ctk.CTkFrame):
    """A small colored badge showing tool status (Installed / Missing / Error)."""

    def __init__(self, master, status: str, **kwargs):
        colors = STATUS_COLORS.get(status, STATUS_COLORS["error"])
        super().__init__(
            master,
            fg_color=colors["bg"],
            corner_radius=12,
            border_width=1,
            border_color=colors["border"],
            **kwargs,
        )

        icon_map = {"installed": "✔", "missing": "✗", "error": "⚠"}
        icon = icon_map.get(status, "?")

        label = ctk.CTkLabel(
            self,
            text=f" {icon}  {status.upper()} ",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=colors["fg"],
            fg_color="transparent",
        )
        label.pack(padx=8, pady=3)


# ── Category Pill ────────────────────────────────────────────────────────────


class CategoryPill(ctk.CTkFrame):
    """A small colored pill showing the tool category."""

    def __init__(self, master, category: str, **kwargs):
        color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["default"])
        super().__init__(
            master,
            fg_color=color,
            corner_radius=10,
            **kwargs,
        )

        label = ctk.CTkLabel(
            self,
            text=f" {category.upper()} ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#0f1117",
            fg_color="transparent",
        )
        label.pack(padx=6, pady=2)


# ── Stat Card ────────────────────────────────────────────────────────────────


class StatCard(ctk.CTkFrame):
    """A dashboard stat card showing a metric with an icon and label."""

    def __init__(
        self,
        master,
        title: str,
        value: str,
        icon: str,
        accent_color: str = COLORS["accent_blue"],
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )

        self._accent = accent_color
        self._value_var = ctk.StringVar(value=value)

        # Icon
        icon_label = ctk.CTkLabel(
            self,
            text=icon,
            font=ctk.CTkFont(size=28),
            text_color=accent_color,
        )
        icon_label.pack(anchor="w", padx=20, pady=(18, 2))

        # Value
        self._value_label = ctk.CTkLabel(
            self,
            textvariable=self._value_var,
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self._value_label.pack(anchor="w", padx=20, pady=(2, 0))

        # Title
        title_label = ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["text_secondary"],
        )
        title_label.pack(anchor="w", padx=20, pady=(0, 16))

        # Hover effect
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        for child in self.winfo_children():
            child.bind("<Enter>", self._on_enter)
            child.bind("<Leave>", self._on_leave)

    def update_value(self, value: str):
        self._value_var.set(value)

    def _on_enter(self, event=None):
        self.configure(fg_color=COLORS["bg_card_hover"], border_color=self._accent)

    def _on_leave(self, event=None):
        self.configure(fg_color=COLORS["bg_card"], border_color=COLORS["border"])


# ── Section Header ───────────────────────────────────────────────────────────


class SectionHeader(ctk.CTkFrame):
    """Styled section header with a title and optional subtitle."""

    def __init__(
        self,
        master,
        title: str,
        subtitle: str = "",
        icon: str = "",
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=0)

        if icon:
            icon_label = ctk.CTkLabel(
                row,
                text=icon,
                font=ctk.CTkFont(size=22),
                text_color=COLORS["accent_blue"],
            )
            icon_label.pack(side="left", padx=(0, 8))

        title_label = ctk.CTkLabel(
            row,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        title_label.pack(side="left")

        if subtitle:
            sub_label = ctk.CTkLabel(
                self,
                text=subtitle,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORS["text_secondary"],
            )
            sub_label.pack(anchor="w", pady=(2, 0))


# ── Tool Card ────────────────────────────────────────────────────────────────


class ToolCard(ctk.CTkFrame):
    """
    A richly styled card displaying a single tool with its status,
    version, description, and action buttons.
    """

    def __init__(
        self,
        master,
        tool_name: str,
        tool_config: dict,
        status: str = "missing",
        version: Optional[str] = None,
        on_install: Optional[Callable] = None,
        on_uninstall: Optional[Callable] = None,
        on_update: Optional[Callable] = None,
        on_check: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )

        self.tool_name = tool_name
        self._status = status
        self._on_install = on_install
        self._on_uninstall = on_uninstall
        self._on_update = on_update
        self._on_check = on_check

        # ── Top row: name + status badge ──
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=18, pady=(16, 6))

        # Left: name + category
        left_frame = ctk.CTkFrame(top_row, fg_color="transparent")
        left_frame.pack(side="left", fill="x", expand=True)

        name_label = ctk.CTkLabel(
            left_frame,
            text=tool_name.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        name_label.pack(side="left", padx=(0, 10))

        category = tool_config.get("category", "")
        if category:
            pill = CategoryPill(left_frame, category)
            pill.pack(side="left", padx=(0, 6))

        # Right: badge
        self._badge_frame = ctk.CTkFrame(top_row, fg_color="transparent")
        self._badge_frame.pack(side="right")
        self._badge = StatusBadge(self._badge_frame, status)
        self._badge.pack()

        # ── Description ──
        desc = tool_config.get("description", "No description available.")
        desc_label = ctk.CTkLabel(
            self,
            text=desc,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        desc_label.pack(fill="x", padx=18, pady=(0, 4))

        # ── Version + latest ──
        ver_frame = ctk.CTkFrame(self, fg_color="transparent")
        ver_frame.pack(fill="x", padx=18, pady=(0, 8))

        ver_text = f"Installed: v{version}" if version else "Not installed"
        self._ver_label = ctk.CTkLabel(
            ver_frame,
            text=ver_text,
            font=ctk.CTkFont(family="Cascadia Code", size=12),
            text_color=COLORS["accent_green"] if version else COLORS["text_dim"],
        )
        self._ver_label.pack(side="left")

        latest = tool_config.get("latest_version", "")
        if latest:
            latest_label = ctk.CTkLabel(
                ver_frame,
                text=f"  •  Latest: v{latest}",
                font=ctk.CTkFont(family="Cascadia Code", size=12),
                text_color=COLORS["text_dim"],
            )
            latest_label.pack(side="left")

        # ── Divider ──
        divider = ctk.CTkFrame(self, fg_color=COLORS["border"], height=1)
        divider.pack(fill="x", padx=18, pady=(4, 8))

        # ── Action buttons row ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 14))

        btn_font = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")

        # Determine if this tool supports auto-install on this platform
        from tool_manager.utils.os_utils import get_platform_key as _get_pk
        from tool_manager.core.installer import ToolInstaller as _TI
        _platform_key = _get_pk()
        _can_auto = _TI.can_auto_install(tool_config, _platform_key)
        _manual_url = tool_config.get("manual_install_url", tool_config.get("homepage", ""))

        if status != "installed":
            if _can_auto:
                install_btn = ctk.CTkButton(
                    btn_row,
                    text="⬇  Install",
                    font=btn_font,
                    fg_color=COLORS["accent_blue"],
                    hover_color="#3a85e0",
                    text_color="#ffffff",
                    corner_radius=10,
                    height=34,
                    width=110,
                    command=lambda: self._fire(on_install),
                )
                install_btn.pack(side="left", padx=(0, 8))
            elif _manual_url:
                manual_btn = ctk.CTkButton(
                    btn_row,
                    text="🌐  Download Page",
                    font=btn_font,
                    fg_color=COLORS["accent_purple"],
                    hover_color="#7c3aed",
                    text_color="#ffffff",
                    corner_radius=10,
                    height=34,
                    width=140,
                    command=lambda url=_manual_url: webbrowser.open(url),
                )
                manual_btn.pack(side="left", padx=(0, 8))
            else:
                no_install_label = ctk.CTkLabel(
                    btn_row,
                    text="⚠  Manual install required",
                    font=btn_font,
                    text_color=COLORS["accent_amber"],
                )
                no_install_label.pack(side="left", padx=(0, 8))
        else:
            uninstall_btn = ctk.CTkButton(
                btn_row,
                text="🗑  Uninstall",
                font=btn_font,
                fg_color=COLORS["accent_red"],
                hover_color="#dc2626",
                text_color="#ffffff",
                corner_radius=10,
                height=34,
                width=120,
                command=lambda: self._fire(on_uninstall),
            )
            uninstall_btn.pack(side="left", padx=(0, 8))

            update_btn = ctk.CTkButton(
                btn_row,
                text="⬆  Update",
                font=btn_font,
                fg_color=COLORS["accent_amber"],
                hover_color="#d97706",
                text_color="#0f1117",
                corner_radius=10,
                height=34,
                width=110,
                command=lambda: self._fire(on_update),
            )
            update_btn.pack(side="left", padx=(0, 8))

        check_btn = ctk.CTkButton(
            btn_row,
            text="🔍  Check",
            font=btn_font,
            fg_color="transparent",
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=10,
            height=34,
            width=100,
            command=lambda: self._fire(on_check),
        )
        check_btn.pack(side="left", padx=(0, 8))

        # Homepage link
        homepage = tool_config.get("homepage", "")
        if homepage:
            link_btn = ctk.CTkButton(
                btn_row,
                text="🌐  Homepage",
                font=btn_font,
                fg_color="transparent",
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["accent_cyan"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=10,
                height=34,
                width=120,
                command=lambda: webbrowser.open(homepage),
            )
            link_btn.pack(side="left")

        # Hover on entire card
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _fire(self, callback):
        if callback:
            callback(self.tool_name)

    def update_status(self, status: str, version: Optional[str] = None):
        """Update the card's status badge and version display."""
        self._status = status
        # Rebuild badge
        for child in self._badge_frame.winfo_children():
            child.destroy()
        self._badge = StatusBadge(self._badge_frame, status)
        self._badge.pack()
        # Update version
        ver_text = f"Installed: v{version}" if version else "Not installed"
        self._ver_label.configure(
            text=ver_text,
            text_color=COLORS["accent_green"] if version else COLORS["text_dim"],
        )

    def _on_enter(self, event=None):
        self.configure(fg_color=COLORS["bg_card_hover"])

    def _on_leave(self, event=None):
        self.configure(fg_color=COLORS["bg_card"])


# ── Progress Overlay ─────────────────────────────────────────────────────────


class ProgressOverlay(ctk.CTkFrame):
    """
    A rich download-progress panel with real-time percentage, speed,
    downloaded/total size, and a determinate progress bar.
    """

    def __init__(self, master, message: str = "Working…", **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=18,
            border_width=2,
            border_color=COLORS["accent_blue"],
            **kwargs,
        )

        self._is_determinate = False

        # ── Inner container ──────────────────────────────────────────
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=28, pady=20)

        # ── Row 1: Large percentage + speed ──────────────────────────
        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 6))

        # Big percentage number
        self._pct_var = ctk.StringVar(value="0%")
        self._pct_label = ctk.CTkLabel(
            top_row,
            textvariable=self._pct_var,
            font=ctk.CTkFont(family="Segoe UI", size=36, weight="bold"),
            text_color=COLORS["accent_blue"],
        )
        self._pct_label.pack(side="left")

        # Speed + size column on the right
        stats_col = ctk.CTkFrame(top_row, fg_color="transparent")
        stats_col.pack(side="right", anchor="e")

        # Speed
        self._speed_var = ctk.StringVar(value="⚡ 0.00 MB/s")
        self._speed_label = ctk.CTkLabel(
            stats_col,
            textvariable=self._speed_var,
            font=ctk.CTkFont(family="Cascadia Code", size=14, weight="bold"),
            text_color=COLORS["accent_green"],
        )
        self._speed_label.pack(anchor="e")

        # Downloaded / Total
        self._size_var = ctk.StringVar(value="0.0 / 0.0 MB")
        self._size_label = ctk.CTkLabel(
            stats_col,
            textvariable=self._size_var,
            font=ctk.CTkFont(family="Cascadia Code", size=12),
            text_color=COLORS["text_secondary"],
        )
        self._size_label.pack(anchor="e")

        # ── Row 2: Progress bar ──────────────────────────────────────
        self._progress = ctk.CTkProgressBar(
            inner,
            mode="indeterminate",
            progress_color=COLORS["accent_blue"],
            fg_color=COLORS["border"],
            width=340,
            height=12,
            corner_radius=6,
        )
        self._progress.pack(fill="x", pady=(4, 8))
        self._progress.start()

        # ── Row 3: Status message ────────────────────────────────────
        self._msg_var = ctk.StringVar(value=message)
        self._label = ctk.CTkLabel(
            inner,
            textvariable=self._msg_var,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_dim"],
            wraplength=340,
        )
        self._label.pack(fill="x")

    # ── Public API ───────────────────────────────────────────────────

    def set_message(self, message: str):
        """Update the bottom status text."""
        self._msg_var.set(message)

    def set_progress(self, value: float):
        """Set progress bar to a value (0.0–1.0). Auto-switches to determinate."""
        if not self._is_determinate:
            self._is_determinate = True
            self._progress.stop()
            self._progress.configure(mode="determinate")
        clamped = max(0.0, min(1.0, value))
        self._progress.set(clamped)
        self._pct_var.set(f"{int(clamped * 100)}%")

    def set_speed(self, speed_bytes_per_sec: float):
        """Update the speed display."""
        speed_mb = speed_bytes_per_sec / (1024 * 1024)
        if speed_mb >= 1.0:
            self._speed_var.set(f"⚡ {speed_mb:.2f} MB/s")
        else:
            speed_kb = speed_bytes_per_sec / 1024
            self._speed_var.set(f"⚡ {speed_kb:.0f} KB/s")

    def set_size(self, downloaded: int, total: int):
        """Update the downloaded / total display."""
        dl_mb = downloaded / (1024 * 1024)
        if total > 0:
            total_mb = total / (1024 * 1024)
            self._size_var.set(f"{dl_mb:.1f} / {total_mb:.1f} MB")
        else:
            self._size_var.set(f"{dl_mb:.1f} MB")

    def set_download_stats(self, downloaded: int, total: int, speed: float):
        """Convenience: update progress bar, speed, and size in one call."""
        if total > 0:
            self.set_progress(downloaded / total)
        self.set_speed(speed)
        self.set_size(downloaded, total)

    def reset_to_indeterminate(self):
        """Switch back to spinning indeterminate mode."""
        self._is_determinate = False
        self._pct_var.set("0%")
        self._speed_var.set("⚡ 0.00 MB/s")
        self._size_var.set("0.0 / 0.0 MB")
        self._progress.configure(mode="indeterminate")
        self._progress.start()

    def stop(self):
        self._progress.stop()

