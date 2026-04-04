"""
Dashboard Frame — Main overview panel.

Shows summary statistics, platform info, and color-coded tool cards
with real-time status from ToolChecker.
"""

import threading
import customtkinter as ctk
from typing import Optional

from tool_manager.core.checker import ToolChecker, ToolStatus
from tool_manager.core.installer import ToolInstaller
from tool_manager.core.updater import ToolUpdater
from tool_manager.gui.widgets import (
    COLORS,
    StatCard,
    SectionHeader,
    ToolCard,
    ProgressOverlay,
)
from tool_manager.utils.os_utils import get_platform_key, get_platform_info


class DashboardFrame(ctk.CTkFrame):
    """
    Dashboard overview frame – the landing page of the GUI.

    Displays aggregate tool statistics, platform diagnostics, and
    a grid of ToolCards for every registered tool.
    """

    def __init__(self, master, tools_config: dict, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.tools_config = tools_config
        self._check_results = {}
        self._tool_cards = {}
        self._is_scanning = False

        # ── Scrollable container ─────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_blue"],
        )
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)
        self._scroll.columnconfigure(0, weight=1)

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        container = self._scroll

        # ── Header ───────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 10))

        SectionHeader(
            header_frame,
            title="Dashboard",
            subtitle="Monitor and manage your eSim EDA tools at a glance",
            icon="📊",
        ).pack(side="left", fill="x", expand=True)

        self._scan_btn = ctk.CTkButton(
            header_frame,
            text="🔄  Scan All Tools",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLORS["accent_blue"],
            hover_color="#3a85e0",
            text_color="#ffffff",
            corner_radius=12,
            height=42,
            width=180,
            command=self._start_scan,
        )
        self._scan_btn.pack(side="right", padx=(16, 0))

        # ── Stats row ────────────────────────────────────────────────
        stats_frame = ctk.CTkFrame(container, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=(10, 6))
        stats_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="stat")

        total = len(self.tools_config)

        self._stat_total = StatCard(
            stats_frame,
            title="Total Tools",
            value=str(total),
            icon="📦",
            accent_color=COLORS["accent_blue"],
        )
        self._stat_total.grid(row=0, column=0, padx=(0, 8), pady=6, sticky="nsew")

        self._stat_installed = StatCard(
            stats_frame,
            title="Installed",
            value="—",
            icon="✅",
            accent_color=COLORS["accent_green"],
        )
        self._stat_installed.grid(row=0, column=1, padx=8, pady=6, sticky="nsew")

        self._stat_missing = StatCard(
            stats_frame,
            title="Missing",
            value="—",
            icon="❌",
            accent_color=COLORS["accent_red"],
        )
        self._stat_missing.grid(row=0, column=2, padx=8, pady=6, sticky="nsew")

        self._stat_errors = StatCard(
            stats_frame,
            title="Errors",
            value="—",
            icon="⚠️",
            accent_color=COLORS["accent_amber"],
        )
        self._stat_errors.grid(row=0, column=3, padx=(8, 0), pady=6, sticky="nsew")

        # ── Platform info ────────────────────────────────────────────
        platform_frame = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
        )
        platform_frame.pack(fill="x", padx=24, pady=(6, 10))

        info = get_platform_info()
        platform_text = (
            f"🖥  {info['system']} {info['release']}  •  "
            f"🐍  Python {info['python_version']}  •  "
            f"⚙  {info['machine']}  •  "
            f"🎯  Platform key: {get_platform_key()}"
        )
        ctk.CTkLabel(
            platform_frame,
            text=platform_text,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"],
        ).pack(padx=18, pady=10)

        # ── Tools section header ─────────────────────────────────────
        SectionHeader(
            container,
            title="Tools",
            subtitle="Click 'Scan All Tools' to detect installation status",
            icon="🔧",
        ).pack(anchor="w", padx=24, pady=(10, 8))

        # ── Tool cards container ─────────────────────────────────────
        self._cards_frame = ctk.CTkFrame(container, fg_color="transparent")
        self._cards_frame.pack(fill="x", padx=24, pady=(0, 20))

        self._build_tool_cards()

    def _build_tool_cards(self):
        """Create a ToolCard for every registered tool."""
        for widget in self._cards_frame.winfo_children():
            widget.destroy()
        self._tool_cards.clear()

        for tool_name, tool_cfg in self.tools_config.items():
            status = "missing"
            version = None
            if tool_name in self._check_results:
                r = self._check_results[tool_name]
                status = r.status.value
                version = r.version

            card = ToolCard(
                self._cards_frame,
                tool_name=tool_name,
                tool_config=tool_cfg,
                status=status,
                version=version,
                on_install=self._handle_install,
                on_uninstall=self._handle_uninstall,
                on_update=self._handle_update,
                on_check=self._handle_check,
            )
            card.pack(fill="x", pady=5)
            self._tool_cards[tool_name] = card

    # ──────────────────────────────────────────────────────────────────
    # Scanning
    # ──────────────────────────────────────────────────────────────────

    def _start_scan(self):
        if self._is_scanning:
            return
        self._is_scanning = True
        self._scan_btn.configure(text="⏳  Scanning…", state="disabled")

        thread = threading.Thread(target=self._scan_worker, daemon=True)
        thread.start()

    def _scan_worker(self):
        checker = ToolChecker(self.tools_config)
        results = checker.check_all()
        self._check_results = {r.tool_name: r for r in results}
        self.after(0, self._scan_complete)

    def _scan_complete(self):
        self._is_scanning = False
        self._scan_btn.configure(text="🔄  Scan All Tools", state="normal")

        installed = sum(
            1 for r in self._check_results.values()
            if r.status == ToolStatus.INSTALLED
        )
        missing = sum(
            1 for r in self._check_results.values()
            if r.status == ToolStatus.MISSING
        )
        errors = sum(
            1 for r in self._check_results.values()
            if r.status == ToolStatus.ERROR
        )

        self._stat_installed.update_value(str(installed))
        self._stat_missing.update_value(str(missing))
        self._stat_errors.update_value(str(errors))

        # Rebuild cards with updated statuses
        self._build_tool_cards()

    # ──────────────────────────────────────────────────────────────────
    # Tool actions
    # ──────────────────────────────────────────────────────────────────

    def _handle_install(self, tool_name: str):
        self._run_in_thread(
            f"Installing {tool_name}…",
            lambda: ToolInstaller(self.tools_config).install_tool(tool_name),
            lambda result: self._show_action_result(
                tool_name,
                "Install Successful" if result.success else "Install Failed",
                result.message,
                result.success,
            ),
        )

    def _handle_uninstall(self, tool_name: str):
        self._run_in_thread(
            f"Uninstalling {tool_name}…",
            lambda: self._do_uninstall(tool_name),
            lambda result: self._show_action_result(
                tool_name,
                "Uninstall Successful" if result.success else "Uninstall Failed",
                result.message,
                result.success,
            ),
        )

    def _do_uninstall(self, tool_name: str):
        """Execute the platform-specific uninstall command."""
        import subprocess
        from tool_manager.utils.os_utils import get_platform_key
        from tool_manager.core.installer import InstallResult

        tool_cfg = self.tools_config.get(tool_name, {})
        uninstall_cmds = tool_cfg.get("uninstall", {})
        platform_key = get_platform_key()
        cmd = uninstall_cmds.get(platform_key, "")

        if not cmd:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=f"No uninstall command for '{tool_name}' on {platform_key}.",
            )

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, shell=True
            )
            success = result.returncode == 0
            return InstallResult(
                tool_name=tool_name,
                success=success,
                message=(
                    f"Uninstalled '{tool_name}'."
                    if success
                    else f"Uninstall may have failed (exit {result.returncode})."
                ),
                command_executed=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        except Exception as exc:
            return InstallResult(
                tool_name=tool_name,
                success=False,
                message=str(exc),
            )

    def _handle_update(self, tool_name: str):
        self._run_in_thread(
            f"Updating {tool_name}…",
            lambda: ToolUpdater(
                self.tools_config,
                ToolChecker(self.tools_config),
                ToolInstaller(self.tools_config),
            ).update_tool(tool_name),
            lambda result: self._show_action_result(
                tool_name,
                result.action.value.replace("_", " ").title(),
                result.message,
                result.action.value in ("updated", "up_to_date"),
            ),
        )

    def _handle_check(self, tool_name: str):
        self._run_in_thread(
            f"Checking {tool_name}…",
            lambda: ToolChecker(self.tools_config).check_tool(tool_name),
            lambda result: self._on_single_check_done(result),
        )

    def _on_single_check_done(self, result):
        self._check_results[result.tool_name] = result
        # Refresh stats
        installed = sum(
            1 for r in self._check_results.values()
            if r.status == ToolStatus.INSTALLED
        )
        missing = sum(
            1 for r in self._check_results.values()
            if r.status == ToolStatus.MISSING
        )
        errors = sum(
            1 for r in self._check_results.values()
            if r.status == ToolStatus.ERROR
        )
        self._stat_installed.update_value(str(installed))
        self._stat_missing.update_value(str(missing))
        self._stat_errors.update_value(str(errors))

        self._build_tool_cards()

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    def _run_in_thread(self, message, worker_fn, callback_fn):
        """Run a backend operation in a thread, showing overlay, then callback on main thread."""
        overlay = ProgressOverlay(self, message=message)
        overlay.place(relx=0.5, rely=0.5, anchor="center")

        def _worker():
            result = worker_fn()
            self.after(0, lambda: _done(result))

        def _done(result):
            overlay.stop()
            overlay.destroy()
            callback_fn(result)
            # Trigger a re-scan after action
            self._start_scan()

        threading.Thread(target=_worker, daemon=True).start()

    def _show_action_result(self, tool_name, title, message, success):
        """Show a brief result dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("420x180")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        color = COLORS["accent_green"] if success else COLORS["accent_red"]
        icon = "✅" if success else "❌"

        ctk.CTkLabel(
            dialog,
            text=f"{icon}  {title}",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=color,
        ).pack(pady=(24, 8))

        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["text_secondary"],
            wraplength=360,
        ).pack(padx=20, pady=(0, 16))

        ctk.CTkButton(
            dialog,
            text="OK",
            width=100,
            corner_radius=10,
            fg_color=color,
            hover_color=COLORS["accent_blue"],
            command=dialog.destroy,
        ).pack(pady=(0, 16))
