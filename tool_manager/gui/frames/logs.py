"""
Logs Frame — Live log viewer.

Tails the tool_manager.log file and displays entries with severity-based
color coding, search/filter, and export capabilities.
"""

import os
import threading
import time
import customtkinter as ctk
from pathlib import Path
from typing import Optional

from tool_manager.gui.widgets import COLORS, SectionHeader


_LOG_FILE = Path(__file__).resolve().parent.parent.parent / "logs" / "tool_manager.log"

# Color map for log severity
_SEVERITY_TAGS = {
    "DEBUG": COLORS["text_dim"],
    "INFO": COLORS["text_primary"],
    "WARNING": COLORS["accent_amber"],
    "ERROR": COLORS["accent_red"],
    "CRITICAL": COLORS["accent_red"],
}


class LogsFrame(ctk.CTkFrame):
    """Live log viewer with search, severity filtering, and export."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._auto_scroll = True
        self._filter_text = ""
        self._severity_filter = "ALL"
        self._tailing = False
        self._last_size = 0

        self._build_ui()

    def _build_ui(self):
        # ── Header ───────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 8))

        SectionHeader(
            header,
            title="Activity Log",
            subtitle="Real-time view of tool_manager.log",
            icon="📋",
        ).pack(side="left")

        # ── Toolbar ──────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        toolbar.pack(fill="x", padx=24, pady=(0, 8))

        # Search
        ctk.CTkLabel(
            toolbar,
            text="🔍",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(14, 4), pady=8)

        self._search_entry = ctk.CTkEntry(
            toolbar,
            placeholder_text="Search logs…",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            height=32,
            width=250,
        )
        self._search_entry.pack(side="left", padx=(0, 12), pady=8)
        self._search_entry.bind("<KeyRelease>", self._on_search_change)

        # Severity filter
        ctk.CTkLabel(
            toolbar,
            text="Level:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_secondary"],
        ).pack(side="left", padx=(8, 4), pady=8)

        self._severity_menu = ctk.CTkOptionMenu(
            toolbar,
            values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["accent_blue"],
            button_hover_color="#3a85e0",
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=110,
            command=self._on_severity_change,
        )
        self._severity_menu.pack(side="left", padx=(0, 12), pady=8)

        # Auto-scroll toggle
        self._auto_scroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            toolbar,
            text="Auto-scroll",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"],
            variable=self._auto_scroll_var,
            fg_color=COLORS["accent_blue"],
            hover_color="#3a85e0",
            corner_radius=4,
        ).pack(side="left", padx=(0, 12), pady=8)

        # Action buttons (right side)
        ctk.CTkButton(
            toolbar,
            text="📥  Export",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["accent_cyan"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
            height=32,
            width=90,
            command=self._export_log,
        ).pack(side="right", padx=(4, 14), pady=8)

        ctk.CTkButton(
            toolbar,
            text="🔄  Refresh",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
            height=32,
            width=100,
            command=self._load_full_log,
        ).pack(side="right", padx=4, pady=8)

        ctk.CTkButton(
            toolbar,
            text="🗑  Clear View",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["accent_red"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8,
            height=32,
            width=110,
            command=self._clear_view,
        ).pack(side="right", padx=4, pady=8)

        # ── Log display ──────────────────────────────────────────────
        self._log_text = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Cascadia Code", size=12),
            fg_color=COLORS["bg_dark"],
            text_color=COLORS["text_primary"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
            state="disabled",
            wrap="none",
        )
        self._log_text.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # ── Status bar ───────────────────────────────────────────────
        self._status_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_dim"],
        )
        self._status_label.pack(anchor="w", padx=28, pady=(0, 10))

        # Load initial content
        self._load_full_log()

        # Start tail thread
        self._start_tailing()

    def _load_full_log(self):
        """Read the entire log file and display it."""
        if not _LOG_FILE.exists():
            self._set_log_content("No log file found. Run a tool action to generate logs.")
            self._status_label.configure(text="Log file: not found")
            return

        try:
            with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self._last_size = _LOG_FILE.stat().st_size
        except Exception as e:
            self._set_log_content(f"Error reading log file: {e}")
            return

        lines = content.splitlines()
        filtered = self._apply_filters(lines)
        self._set_log_content("\n".join(filtered))
        self._status_label.configure(
            text=f"Log file: {_LOG_FILE}  •  {len(lines)} total lines  •  {len(filtered)} shown"
        )

    def _apply_filters(self, lines: list[str]) -> list[str]:
        """Filter lines by severity and search text."""
        result = []
        for line in lines:
            # Severity filter
            if self._severity_filter != "ALL":
                if f"| {self._severity_filter}" not in line:
                    continue
            # Search filter
            if self._filter_text:
                if self._filter_text.lower() not in line.lower():
                    continue
            result.append(line)
        return result

    def _set_log_content(self, text: str):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.insert("1.0", text)
        self._log_text.configure(state="disabled")
        if self._auto_scroll_var.get():
            self._log_text.see("end")

    def _append_log_lines(self, text: str):
        lines = text.splitlines()
        filtered = self._apply_filters(lines)
        if not filtered:
            return
        self._log_text.configure(state="normal")
        self._log_text.insert("end", "\n" + "\n".join(filtered))
        self._log_text.configure(state="disabled")
        if self._auto_scroll_var.get():
            self._log_text.see("end")

    def _on_search_change(self, event=None):
        self._filter_text = self._search_entry.get()
        self._load_full_log()

    def _on_severity_change(self, value: str):
        self._severity_filter = value
        self._load_full_log()

    def _clear_view(self):
        self._set_log_content("")
        self._status_label.configure(text="View cleared")

    def _export_log(self):
        """Export filtered log to a file on the desktop."""
        try:
            desktop = Path.home() / "Desktop"
            export_path = desktop / "esim_tool_manager_log_export.txt"

            self._log_text.configure(state="normal")
            content = self._log_text.get("1.0", "end")
            self._log_text.configure(state="disabled")

            with open(export_path, "w", encoding="utf-8") as f:
                f.write(content)

            self._status_label.configure(
                text=f"✅ Exported to {export_path}"
            )
        except Exception as e:
            self._status_label.configure(text=f"❌ Export failed: {e}")

    # ── Tail thread ──────────────────────────────────────────────────

    def _start_tailing(self):
        if self._tailing:
            return
        self._tailing = True
        thread = threading.Thread(target=self._tail_worker, daemon=True)
        thread.start()

    def _tail_worker(self):
        """Periodically check for new log content."""
        while self._tailing:
            time.sleep(2)
            if not _LOG_FILE.exists():
                continue

            try:
                current_size = _LOG_FILE.stat().st_size
                if current_size > self._last_size:
                    with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(self._last_size)
                        new_content = f.read()
                    self._last_size = current_size
                    if new_content.strip():
                        self.after(0, lambda c=new_content: self._append_log_lines(c))
            except Exception:
                pass

    def destroy(self):
        self._tailing = False
        super().destroy()
