from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import APP_VERSION
from services.project_service import ProjectService
from ui.dialogs import ProjectFormDialog, confirm
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
        on_changed=None,
        active_project_id: int | None = None,
        active_state: str | None = None,
        parked_map: dict[int, float] | None = None,
        focus_bar_fn=None,
        on_quit=None,
        on_widget=None,
    ):
        super().__init__(master, fg_color="transparent")
        self._projects = project_service
        self._on_changed = on_changed
        self._on_quit = on_quit
        self._on_widget = on_widget
        self._active_project_id = active_project_id
        self._active_state = active_state
        self._parked_map = parked_map or {}

        self.grid_columnconfigure(0, weight=1)
        next_row = 1
        bar = focus_bar_fn(self) if focus_bar_fn is not None else None
        if bar is not None:
            bar.grid(row=1, column=0, sticky="ew", padx=32, pady=(0, 4))
            next_row = 2
        self.grid_rowconfigure(next_row, weight=1)

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
        body.grid(row=next_row, column=0, sticky="nsew", padx=32)
        body.grid_columnconfigure(0, weight=1)

        def _on_scroll(event):
            delta = event.delta
            body._parent_frame.yview_scroll(int(-delta / 4), "units")
            return "break"

        body.bind("<MouseWheel>", _on_scroll)

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
        footer.grid(row=next_row + 1, column=0, sticky="ew", padx=32, pady=(8, 16))
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
        if self._on_widget is not None:
            ctk.CTkButton(
                exports, text="\u25A1 Mini Widget", width=80, height=26, fg_color="transparent",
                border_width=1, border_color=("gray70", "gray30"),
                text_color=("gray30", "gray65"), command=self._on_widget,
            ).pack(side="left", padx=(12, 6))
        if self._on_quit is not None:
            ctk.CTkButton(
                exports, text="Quit", width=60, height=26, fg_color="transparent",
                border_width=1, border_color=("gray70", "gray30"),
                text_color=("#c62828", "#ef9a9a"), hover_color=("gray88", "gray22"),
                command=self._on_quit,
            ).pack(side="left", padx=6)

        today_seconds, week_seconds = project_service.global_totals()
        ctk.CTkLabel(
            footer,
            text=(
                f"Today {format_duration(today_seconds)}   ·   "
                f"This week {format_duration(week_seconds)}"
                f"   ·   v{APP_VERSION}"
            ),
            text_color="gray55",
            font=ctk.CTkFont(size=13),
        ).grid(row=0, column=2, sticky="e")

    def _refresh(self) -> None:
        if self._on_changed is not None:
            self._on_changed()

    def _edit_project(self, summary) -> None:
        project = summary.project
        dialog = ProjectFormDialog(
            self.winfo_toplevel(),
            title="Edit project",
            name=project.name,
            description=project.description,
            daily_goal_minutes=project.daily_goal_minutes,
        )
        result = dialog.show()
        if not result:
            return
        name, description, goal = result
        try:
            self._projects.update_project(project, name, description, daily_goal_minutes=goal)
        except ValueError:
            return
        self._refresh()

    def _archive_project(self, summary) -> None:
        message = (
            f"Archive '{summary.project.name}'?\n\n"
            "It will disappear from the dashboard but its history is preserved."
        )
        if not confirm(self.winfo_toplevel(), "Archive project", message):
            return
        self._projects.archive_project(summary.project)
        self._refresh()

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

        assert summary.project.id is not None
        if summary.project.id == self._active_project_id and self._active_state is not None:
            badge_text = "\u25CF  Running" if self._active_state == "running" else "\u2758\u2758  Paused"
            badge_color = "#66bb6a" if self._active_state == "running" else "#ffb74d"
            ctk.CTkLabel(
                info, text=badge_text, text_color=badge_color,
                font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
            ).pack(anchor="w", pady=(2, 0))
        elif summary.project.id in self._parked_map:
            parked_seconds = self._parked_map[summary.project.id]
            if parked_seconds > 0:
                ctk.CTkLabel(
                    info,
                    text=f"\u23F8  {format_duration(parked_seconds)} parked",
                    text_color="#ffb74d", font=ctk.CTkFont(size=12), anchor="w",
                ).pack(anchor="w", pady=(2, 0))

        meta_parts = [format_duration(summary.total_seconds), f"{summary.session_count} sessions"]
        if summary.today_seconds > 0:
            meta_parts.append(f"{format_duration(summary.today_seconds)} today")
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

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=1, padx=(0, 20), pady=16)
        work_label = "\u23F1  Focus"
        if self._active_project_id is not None and summary.project.id != self._active_project_id:
            work_label = "\u21C4  Switch"
        work_button = ctk.CTkButton(actions, text=work_label, width=110, height=34)
        work_button.grid(row=0, column=0)
        ctk.CTkButton(
            actions, text="\u270E", width=34, height=34, fg_color="transparent",
            border_width=1, border_color=("gray65", "gray35"),
            text_color=("gray40", "gray65"),
            command=lambda s=summary: self._edit_project(s),
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            actions, text="\U0001F4E6", width=34, height=34, fg_color="transparent",
            border_width=1, border_color=("gray65", "gray35"),
            text_color="#ef9a9a", hover_color=("gray88", "gray22"),
            command=lambda s=summary: self._archive_project(s),
        ).grid(row=0, column=2, padx=(6, 0))

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
