"""
Tools Frame — Detailed tool management view.

Provides a filterable, scrollable list of all tools with expanded
detail panels, individual action buttons, and command output display.
"""

import threading
import customtkinter as ctk
from typing import Optional

from tool_manager.core.checker import ToolChecker, ToolStatus
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater, UpdateAction
from tool_manager.gui.widgets import (
    COLORS,
    CATEGORY_COLORS,
    SectionHeader,
    StatusBadge,
    CategoryPill,
    ProgressOverlay,
)
from tool_manager.utils.os_utils import get_platform_key
import webbrowser
import subprocess


class ToolDetailPanel(ctk.CTkFrame):
    """Expanded detail panel for a single tool with full action suite."""

    def __init__(self, master, tool_name: str, tool_config: dict, parent_frame, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )

        self.tool_name = tool_name
        self.tool_config = tool_config
        self._parent_frame = parent_frame
        self._status = "missing"
        self._version = None
        self._progress_overlay = None

        # ── Header row ───────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        name_label = ctk.CTkLabel(
            header,
            text=tool_name.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        name_label.pack(side="left")

        category = tool_config.get("category", "")
        if category:
            CategoryPill(header, category).pack(side="left", padx=(10, 0))

        self._badge_container = ctk.CTkFrame(header, fg_color="transparent")
        self._badge_container.pack(side="right")
        self._badge = StatusBadge(self._badge_container, "missing")
        self._badge.pack()

        # ── Description ──────────────────────────────────────────────
        desc = tool_config.get("description", "")
        if desc:
            ctk.CTkLabel(
                self,
                text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(fill="x", padx=20, pady=(0, 8))

        # ── Info grid ────────────────────────────────────────────────
        info_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=10)
        info_frame.pack(fill="x", padx=20, pady=(0, 8))

        platform_key = get_platform_key()
        info_items = [
            ("Check Command", tool_config.get("check", "N/A")),
            ("Install Command", tool_config.get("install", {}).get(platform_key, "N/A")),
            ("Uninstall Command", tool_config.get("uninstall", {}).get(platform_key, "N/A")),
            ("Latest Version", f"v{tool_config.get('latest_version', 'N/A')}"),
            ("Homepage", tool_config.get("homepage", "N/A")),
        ]

        for i, (key, val) in enumerate(info_items):
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
                text=str(val),
                font=ctk.CTkFont(family="Cascadia Code", size=11),
                text_color=COLORS["text_dim"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        # Padding at bottom of info grid
        ctk.CTkFrame(info_frame, fg_color="transparent", height=6).pack()

        # ── Version display ──────────────────────────────────────────
        self._version_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._version_frame.pack(fill="x", padx=20, pady=(0, 6))

        self._ver_label = ctk.CTkLabel(
            self._version_frame,
            text="Version: not scanned",
            font=ctk.CTkFont(family="Cascadia Code", size=12),
            text_color=COLORS["text_dim"],
        )
        self._ver_label.pack(side="left")

        # ── Divider ──────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=(4, 10)
        )

        # ── Action buttons ───────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 6))

        btn_font = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")

        # Determine if this tool can be auto-installed on this platform
        platform_key = get_platform_key()
        from tool_manager.core.installer import ToolInstaller as _TI
        self._can_auto_install = _TI.can_auto_install(tool_config, platform_key)
        manual_url = tool_config.get("manual_install_url", tool_config.get("homepage", ""))

        if self._can_auto_install:
            self._install_btn = ctk.CTkButton(
                btn_row,
                text="⬇  Install",
                font=btn_font,
                fg_color=COLORS["accent_blue"],
                hover_color="#3a85e0",
                corner_radius=10,
                height=36,
                width=110,
                command=self._do_install,
            )
            self._install_btn.pack(side="left", padx=(0, 8))
        else:
            # Manual-only tool — show download page button
            self._install_btn = ctk.CTkButton(
                btn_row,
                text="🌐  Download Page",
                font=btn_font,
                fg_color=COLORS["accent_purple"],
                hover_color="#7c3aed",
                corner_radius=10,
                height=36,
                width=140,
                command=lambda: self._open_manual_install(manual_url),
            )
            self._install_btn.pack(side="left", padx=(0, 8))

        self._uninstall_btn = ctk.CTkButton(
            btn_row,
            text="🗑  Uninstall",
            font=btn_font,
            fg_color=COLORS["accent_red"],
            hover_color="#dc2626",
            corner_radius=10,
            height=36,
            width=120,
            command=self._do_uninstall,
        )
        self._uninstall_btn.pack(side="left", padx=(0, 8))

        self._update_btn = ctk.CTkButton(
            btn_row,
            text="⬆  Update",
            font=btn_font,
            fg_color=COLORS["accent_amber"],
            hover_color="#d97706",
            text_color="#0f1117",
            corner_radius=10,
            height=36,
            width=110,
            command=self._do_update,
        )
        self._update_btn.pack(side="left", padx=(0, 8))

        self._check_btn = ctk.CTkButton(
            btn_row,
            text="🔍  Check",
            font=btn_font,
            fg_color="transparent",
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=10,
            height=36,
            width=100,
            command=self._do_check,
        )
        self._check_btn.pack(side="left", padx=(0, 8))

        homepage = tool_config.get("homepage", "")
        if homepage:
            ctk.CTkButton(
                btn_row,
                text="🌐  Open",
                font=btn_font,
                fg_color="transparent",
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["accent_cyan"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=10,
                height=36,
                width=90,
                command=lambda: webbrowser.open(homepage),
            ).pack(side="left")

        # ── Manual install notice ────────────────────────────────────
        if not self._can_auto_install:
            notice = ctk.CTkFrame(self, fg_color=COLORS["warning_bg"], corner_radius=8)
            notice.pack(fill="x", padx=20, pady=(4, 0))
            ctk.CTkLabel(
                notice,
                text=f"⚠  This tool requires manual installation on {platform_key}.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=COLORS["accent_amber"],
            ).pack(padx=12, pady=6)

        # ── Output area ──────────────────────────────────────────────
        self._output_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )

        self._output_text = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Cascadia Code", size=11),
            fg_color=COLORS["bg_dark"],
            text_color=COLORS["text_dim"],
            corner_radius=8,
            height=100,
            border_width=1,
            border_color=COLORS["border"],
            state="disabled",
        )

        # Card hover
        self.bind("<Enter>", lambda e: self.configure(fg_color=COLORS["bg_card_hover"]))
        self.bind("<Leave>", lambda e: self.configure(fg_color=COLORS["bg_card"]))

    def _update_badge(self, status: str):
        self._status = status
        for w in self._badge_container.winfo_children():
            w.destroy()
        StatusBadge(self._badge_container, status).pack()

    def _set_output(self, title: str, text: str):
        self._output_label.configure(text=title)
        self._output_label.pack(fill="x", padx=20, pady=(6, 2))
        self._output_text.pack(fill="x", padx=20, pady=(0, 14))
        self._output_text.configure(state="normal")
        self._output_text.delete("1.0", "end")
        self._output_text.insert("1.0", text)
        self._output_text.configure(state="disabled")

    def _disable_buttons(self):
        for btn in (self._install_btn, self._uninstall_btn, self._update_btn, self._check_btn):
            btn.configure(state="disabled")

    def _enable_buttons(self):
        for btn in (self._install_btn, self._uninstall_btn, self._update_btn, self._check_btn):
            btn.configure(state="normal")

    def _show_progress(self, message: str):
        if self._progress_overlay is None:
            self._progress_overlay = ProgressOverlay(self, message=message)
            self._progress_overlay.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self._progress_overlay.set_message(message)
            self._progress_overlay.lift()

    def _set_progress_message(self, message: str):
        if self._progress_overlay is not None:
            self._progress_overlay.set_message(message)

    def _update_progress(self, fraction: float, message: str):
        """Update the real-time progress bar fill and status text together."""
        if self._progress_overlay is not None:
            self._progress_overlay.set_progress(fraction)
            self._progress_overlay.set_message(message)

    def _hide_progress(self):
        if self._progress_overlay is None:
            return
        self._progress_overlay.stop()
        self._progress_overlay.destroy()
        self._progress_overlay = None

    def _update_download_stats(self, downloaded: int, total: int, speed: float):
        """Push live download metrics to the progress overlay."""
        if self._progress_overlay is not None:
            self._progress_overlay.set_download_stats(downloaded, total, speed)
            self._progress_overlay.set_message(f"Downloading {self.tool_name}…")

    # ── Actions ──────────────────────────────────────────────────────

    def _open_manual_install(self, url: str):
        """Open the manual installation page in the default browser."""
        if url:
            webbrowser.open(url)
            self._set_output(
                "Manual Install:",
                f"Opened download page in your browser:\n{url}\n\n"
                f"Please download and install '{self.tool_name}' manually, "
                f"then click 'Check' to verify the installation."
            )
        else:
            self._set_output(
                "Manual Install:",
                f"No download URL available for '{self.tool_name}'. "
                f"Please search online for installation instructions."
            )

    def _do_check(self):
        self._disable_buttons()

        def worker():
            checker = ToolChecker(self._parent_frame.tools_config)
            return checker.check_tool(self.tool_name)

        def done(result):
            self._enable_buttons()
            self._status = result.status.value
            self._version = result.version
            self._update_badge(result.status.value)
            ver = f"v{result.version}" if result.version else "not found"
            self._ver_label.configure(
                text=f"Version: {ver}",
                text_color=COLORS["accent_green"] if result.version else COLORS["accent_red"],
            )
            output = result.raw_output or result.error_message or "No output."
            self._set_output("Check Output:", output)

        self._run_bg(worker, done)

    def _do_install(self):
        self._disable_buttons()
        self._show_progress(f"Preparing {self.tool_name} install...")

        def worker():
            installer = ToolInstaller(self._parent_frame.tools_config)

            def status_callback(message: str):
                self.after(0, lambda m=message: self._set_progress_message(m))

            def progress_callback(downloaded: int, total: int, speed: float = 0.0):
                self.after(
                    0,
                    lambda d=downloaded, t=total, s=speed: self._update_download_stats(d, t, s),
                )

            return installer.install_tool(
                self.tool_name,
                status_callback=status_callback,
                progress_callback=progress_callback,
            )

        def done(result):
            self._hide_progress()
            self._enable_buttons()
            out = []
            if result.command_executed:
                out.append(f"Command: {result.command_executed}")
            if result.stdout:
                out.append(f"stdout:\n{result.stdout}")
            if result.stderr:
                out.append(f"stderr:\n{result.stderr}")
            if result.installed_bin_dir:
                out.append(f"Installed bin directory:\n{result.installed_bin_dir}")
            out.append(f"\nResult: {result.message}")
            self._set_output("Install Output:", "\n".join(out))
            self._do_check()  # re-check after install

        self._run_bg(worker, done)

    def _do_uninstall(self):
        self._disable_buttons()

        def worker():
            tool_cfg = self._parent_frame.tools_config.get(self.tool_name, {})
            uninstall_cmds = tool_cfg.get("uninstall", {})
            platform_key = get_platform_key()
            cmd = uninstall_cmds.get(platform_key, "")

            if not cmd:
                from tool_manager.core.installer import InstallResult
                return InstallResult(
                    tool_name=self.tool_name, success=False,
                    message=f"No uninstall command for {platform_key}.",
                )

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, shell=True)
                from tool_manager.core.installer import InstallResult
                return InstallResult(
                    tool_name=self.tool_name,
                    success=result.returncode == 0,
                    message=f"Uninstalled '{self.tool_name}'." if result.returncode == 0 else f"Exit {result.returncode}",
                    command_executed=cmd,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                )
            except Exception as exc:
                from tool_manager.core.installer import InstallResult
                return InstallResult(
                    tool_name=self.tool_name, success=False, message=str(exc),
                )

        def done(result):
            self._enable_buttons()
            out = [f"Result: {result.message}"]
            if result.stdout:
                out.append(f"stdout:\n{result.stdout}")
            if result.stderr:
                out.append(f"stderr:\n{result.stderr}")
            self._set_output("Uninstall Output:", "\n".join(out))
            self._do_check()

        self._run_bg(worker, done)

    def _do_update(self):
        self._disable_buttons()

        def worker():
            checker = ToolChecker(self._parent_frame.tools_config)
            installer = ToolInstaller(self._parent_frame.tools_config)
            updater = ToolUpdater(self._parent_frame.tools_config, checker, installer)
            return updater.update_tool(self.tool_name)

        def done(result):
            self._enable_buttons()
            self._set_output("Update Result:", result.message)
            self._do_check()

        self._run_bg(worker, done)

    def _run_bg(self, worker, callback):
        def _thread():
            result = worker()
            self.after(0, lambda: callback(result))
        threading.Thread(target=_thread, daemon=True).start()


class ToolsFrame(ctk.CTkFrame):
    """
    Detailed tool management view with category filter tabs
    and expandable tool panels.
    """

    def __init__(self, master, tools_config: dict, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.tools_config = tools_config
        self._active_filter = "all"

        # ── Header ───────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 8))

        SectionHeader(
            header_frame,
            title="Tool Management",
            subtitle="Detailed view with full control over each tool",
            icon="🛠️",
        ).pack(side="left")

        # ── Filter tabs ──────────────────────────────────────────────
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=24, pady=(0, 10))

        categories = ["all"] + sorted(
            set(cfg.get("category", "other") for cfg in tools_config.values())
        )
        self._filter_buttons = {}

        for cat in categories:
            btn = ctk.CTkButton(
                filter_frame,
                text=cat.upper(),
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color=COLORS["accent_blue"] if cat == "all" else "transparent",
                hover_color=COLORS["bg_card_hover"],
                text_color=(
                    "#ffffff" if cat == "all" else COLORS["text_secondary"]
                ),
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=10,
                height=32,
                width=90,
                command=lambda c=cat: self._set_filter(c),
            )
            btn.pack(side="left", padx=(0, 6))
            self._filter_buttons[cat] = btn

        # ── Scrollable tool list ─────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_blue"],
        )
        self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._panels = {}
        self._build_panels()

    def _set_filter(self, category: str):
        self._active_filter = category
        for cat, btn in self._filter_buttons.items():
            if cat == category:
                btn.configure(fg_color=COLORS["accent_blue"], text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
        self._build_panels()

    def _build_panels(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._panels.clear()

        for tool_name, tool_cfg in self.tools_config.items():
            cat = tool_cfg.get("category", "other")
            if self._active_filter != "all" and cat != self._active_filter:
                continue

            panel = ToolDetailPanel(
                self._scroll,
                tool_name=tool_name,
                tool_config=tool_cfg,
                parent_frame=self,
            )
            panel.pack(fill="x", pady=6)
            self._panels[tool_name] = panel
