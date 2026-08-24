from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from services.project_service import ProjectService
from utils.formatting import format_day_label, format_duration


class Dashboard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        project_service: ProjectService,
        on_open_project,
        on_new_project,
        on_quick_work,
        on_open_settings=None,
    ):
        super().__init__(master, fg_color="transparent")
        self._projects = project_service

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Projects", font=ctk.CTkFont(size=28, weight="bold")).grid(
            row=0, column=0
        )
        if on_open_settings is not None:
            ctk.CTkButton(
                header, text="\u2699 Settings", width=110, fg_color="transparent",
                border_width=1, border_color=("gray60", "gray35"), command=on_open_settings,
            ).grid(row=0, column=1, padx=(16, 0))
        ctk.CTkButton(header, text="+ New project", width=140, command=on_new_project).grid(
            row=0, column=2, padx=(16, 0)
        )

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=32)
        body.grid_columnconfigure(0, weight=1)

        summaries = project_service.list_summaries()
        if not summaries:
            empty = ctk.CTkFrame(body, fg_color=("gray90", "gray17"), corner_radius=12)
            empty.grid(row=0, column=0, sticky="ew", pady=24)
            ctk.CTkLabel(
                empty,
                text="No projects yet.\nCreate one and start accumulating focused work.",
                text_color="gray60",
                justify="center",
                font=ctk.CTkFont(size=14),
            ).pack(padx=40, pady=48)
        else:
            for index, summary in enumerate(summaries):
                self._build_card(body, summary, index, on_open_project, on_quick_work)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=32, pady=(8, 16))
        footer.grid_columnconfigure(2, weight=1)

        exports = ctk.CTkFrame(footer, fg_color="transparent")
        exports.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            exports, text="Export sessions", width=140, height=26, fg_color="transparent",
            border_width=1, border_color=("gray70", "gray30"),
            text_color=("gray30", "gray65"), command=self._export_sessions,
        ).pack(side="left", padx=(4, 6))
        ctk.CTkButton(
            exports, text="Export contributions", width=170, height=26, fg_color="transparent",
            border_width=1, border_color=("gray70", "gray30"),
            text_color=("gray30", "gray65"), command=self._export_contributions,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            exports, text="Backup database", width=150, height=26, fg_color="transparent",
            border_width=1, border_color=("gray70", "gray30"),
            text_color=("gray30", "gray65"), command=self._backup_database,
        ).pack(side="left", padx=6)

        today_seconds, week_seconds = project_service.global_totals()
        ctk.CTkLabel(
            footer,
            text=(
                f"Today {format_duration(today_seconds)}   ·   "
                f"This week {format_duration(week_seconds)}"
            ),
            text_color="gray55",
            font=ctk.CTkFont(size=13),
        ).grid(row=0, column=2, sticky="e")

    def _build_card(self, parent, summary, index, on_open_project, on_quick_work) -> None:
        card = ctk.CTkFrame(parent, corner_radius=12, border_width=1, border_color=("gray78", "gray28"))
        card.grid(row=index, column=0, sticky="ew", pady=6)
        card.grid_columnconfigure(0, weight=1)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=20, pady=16)

        name_label = ctk.CTkLabel(
            info, text=summary.project.name, font=ctk.CTkFont(size=18, weight="bold"), anchor="w"
        )
        name_label.pack(anchor="w")

        meta_parts = [format_duration(summary.total_seconds), f"{summary.session_count} sessions"]
        meta_text = "  ·  ".join(meta_parts)
        if summary.contribution_count:
            meta_text += f"  ·  {summary.contribution_count} contributions"
        if summary.last_activity is not None:
            meta_text += f"  ·  last {format_day_label(summary.last_activity).lower()}"

        meta_label = ctk.CTkLabel(
            info, text=meta_text, text_color="gray60", font=ctk.CTkFont(size=13), anchor="w"
        )
        meta_label.pack(anchor="w", pady=(4, 0))

        widgets_to_click = [card, info, name_label, meta_label]

        goal_minutes = summary.project.daily_goal_minutes
        if goal_minutes > 0:
            goal_seconds = goal_minutes * 60
            ratio = min(1.0, summary.today_seconds / goal_seconds) if goal_seconds else 0.0
            done_today = ratio >= 1.0
            goal_label = ctk.CTkLabel(
                info,
                text=(
                    f"{format_duration(summary.today_seconds)} / {format_duration(goal_seconds)} today"
                    + ("  \u2713" if done_today else "")
                ),
                text_color="#66bb6a" if done_today else "gray60",
                font=ctk.CTkFont(size=12),
                anchor="w",
            )
            goal_label.pack(anchor="w", pady=(6, 2))
            bar = ctk.CTkProgressBar(info, width=280, height=8, corner_radius=4)
            bar.set(ratio)
            if done_today:
                bar.configure(progress_color="#66bb6a")
            bar.pack(anchor="w")
            widgets_to_click.append(goal_label)
            widgets_to_click.append(bar)

        work_button = ctk.CTkButton(card, text="Work", width=110, height=34)
        work_button.grid(row=0, column=1, padx=(0, 20), pady=16)

        for widget in widgets_to_click:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _e, pid=summary.project.id: on_open_project(pid))
        work_button.configure(command=lambda pid=summary.project.id: on_quick_work(pid))

    def _ask_save_path(self, default_name: str, file_types: list[tuple[str, str]]) -> str | None:
        return filedialog.asksaveasfilename(
            parent=self,
            title="Save as",
            initialfile=default_name,
            defaultextension=file_types[0][1],
            filetypes=file_types,
        )

    def _export_sessions(self) -> None:
        path = self._ask_save_path(
            f"chromodoro-sessions-{date.today().isoformat()}.csv",
            [("CSV files", ".csv")],
        )
        if not path:
            return
        try:
            count = self._projects.export_sessions_csv(path)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        messagebox.showinfo("Export complete", f"{count} sessions written to\n{path}", parent=self)

    def _export_contributions(self) -> None:
        path = self._ask_save_path(
            f"chromodoro-contributions-{date.today().isoformat()}.csv",
            [("CSV files", ".csv")],
        )
        if not path:
            return
        try:
            count = self._projects.contributions_export_csv(path)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        messagebox.showinfo("Export complete", f"{count} contributions written to\n{path}", parent=self)

    def _backup_database(self) -> None:
        path = self._ask_save_path(
            f"chromodoro-backup-{date.today().isoformat()}.db",
            [("SQLite database", ".db")],
        )
        if not path:
            return
        try:
            from pathlib import Path

            self._projects.backup_database(Path(path))
        except Exception as exc:
            messagebox.showerror("Backup failed", str(exc), parent=self)
            return
        messagebox.showinfo("Backup complete", f"Database copied to\n{path}", parent=self)
