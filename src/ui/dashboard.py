from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import APP_VERSION
from services.project_service import ProjectService
from ui.dialogs import ProjectFormDialog, confirm
from utils.formatting import format_day_label, format_duration

SEARCH_DEBOUNCE_MS = 250


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
        self._on_open_project = on_open_project
        self._on_quick_work = on_quick_work
        self._on_new_project_cb = on_new_project
        self._focus_bar_fn = focus_bar_fn
        self._on_open_settings = on_open_settings
        self._search_job: str | None = None
        self._empty_frame: ctk.CTkFrame | None = None
        self._focus_bar: ctk.CTkFrame | None = None

        self.grid_columnconfigure(0, weight=1)
        for row in (0, 1, 3, 4):
            self.grid_rowconfigure(row, weight=0)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_body()
        self._build_footer()
        self._summaries_all = project_service.list_summaries()
        self.update_state(active_project_id, active_state, parked_map)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Projects", font=ctk.CTkFont(size=28, weight="bold")).grid(
            row=0, column=0
        )

        self._filter_var = ctk.StringVar(value="")
        ctk.CTkLabel(header, text="Search:", text_color="gray60", font=ctk.CTkFont(size=13)).grid(
            row=0, column=1, padx=(16, 4)
        )
        search_entry = ctk.CTkEntry(
            header, placeholder_text="type a project name", width=200, height=30,
            textvariable=self._filter_var,
        )
        search_entry.grid(row=0, column=2, padx=(0, 0))
        self._filter_var.trace_add("write", self._on_filter_changed)

        ctk.CTkButton(header, text="+ New project", width=140, command=self._on_new_project).grid(
            row=0, column=3, padx=(16, 0)
        )

    def _on_new_project(self) -> None:
        self._on_new_project_cb()

    def _build_body(self) -> None:
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=32)
        body.grid_columnconfigure(0, weight=1)

        def _on_scroll(event):
            delta = event.delta
            canvas = getattr(body, "_parent_canvas", None)
            if canvas is None:
                canvas = getattr(body, "_parent_frame", None)
            if canvas is not None:
                canvas.yview_scroll(int(-delta / 4), "units")
            return "break"

        body.bind("<MouseWheel>", _on_scroll)
        self._body = body

    def _build_footer(self) -> None:
        self._week_frame = ctk.CTkFrame(self, fg_color=("gray92", "gray20"), corner_radius=10)
        self._week_frame.grid(row=3, column=0, sticky="ew", padx=32, pady=(0, 6))
        self._week_labels: list[ctk.CTkLabel] = []
        for i in range(7):
            self._week_frame.grid_columnconfigure(i, weight=1)
            label = ctk.CTkLabel(
                self._week_frame,
                text="",
                font=ctk.CTkFont(size=11),
                justify="center",
            )
            label.grid(row=0, column=i, padx=2, pady=6)
            self._week_labels.append(label)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=32, pady=(8, 16))
        footer.grid_columnconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="ew")
        btn_row.grid_columnconfigure(1, weight=1)

        exports = ctk.CTkFrame(btn_row, fg_color="transparent")
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

        actions = ctk.CTkFrame(btn_row, fg_color="transparent")
        actions.grid(row=0, column=2, sticky="e")
        if self._on_widget is not None:
            self._widget_btn = ctk.CTkButton(
                actions, text="\u25A1 Mini Widget", width=100, height=26,
                fg_color=("#4a6fa5", "#3a5a8a"),
                text_color="white", command=self._on_widget,
            )
            self._widget_btn.pack(side="left", padx=(0, 6))
        if self._on_open_settings is not None:
            ctk.CTkButton(
                actions, text="\u2699 Settings", width=110, height=26, fg_color="transparent",
                border_width=1, border_color=("gray70", "gray30"),
                text_color=("gray30", "gray65"), command=self._on_open_settings,
            ).pack(side="left", padx=6)
        if self._on_quit is not None:
            ctk.CTkButton(
                actions, text="Quit", width=60, height=26, fg_color="transparent",
                border_width=1, border_color=("gray70", "gray30"),
                text_color=("#c62828", "#ef9a9a"), hover_color=("gray88", "gray22"),
                command=self._on_quit,
            ).pack(side="left", padx=6)

        self._totals_label = ctk.CTkLabel(
            footer,
            text="",
            text_color="gray55",
            font=ctk.CTkFont(size=13),
        )
        self._totals_label.grid(row=1, column=0, sticky="e", pady=(4, 0))

    def update_state(self, active_project_id=None, active_state=None, parked_map=None) -> None:
        self._active_project_id = active_project_id
        self._active_state = active_state
        if parked_map is not None:
            self._parked_map = parked_map
        self._rebuild_focus_bar()
        self._rebuild_week()
        self._rebuild_totals()
        self._update_widget_button()
        if not getattr(self, "_cards", None):
            self._build_cards()
        else:
            self._refresh_cards()

    def _rebuild_focus_bar(self) -> None:
        if self._focus_bar_fn is None:
            return
        bar = self._focus_bar
        if bar is not None:
            bar.grid_forget()
            bar.destroy()
        bar = self._focus_bar_fn(self)
        if bar is not None:
            bar.grid(row=1, column=0, sticky="ew", padx=32, pady=(0, 4))
        self._focus_bar = bar

    def _rebuild_week(self) -> None:
        day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        daily = self._projects.weekly_daily_totals()
        for i, label in enumerate(self._week_labels):
            secs = daily[i] if i < len(daily) else 0
            val = f"{int(secs // 60)}m" if secs >= 60 else "0"
            label.configure(
                text=f"{day_labels[i]}\n{val}",
                text_color="gray45" if secs < 60 else "gray85",
            )

    def _rebuild_totals(self) -> None:
        today_seconds, week_seconds = self._projects.global_totals()
        self._totals_label.configure(
            text=(
                f"Today {format_duration(today_seconds)}   ·   "
                f"This week {format_duration(week_seconds)}"
                f"   ·   v{APP_VERSION}"
            )
        )

    def _update_widget_button(self) -> None:
        if not hasattr(self, "_widget_btn"):
            return
        has_active = self._active_project_id is not None
        if has_active:
            self._widget_btn.configure(state="normal", fg_color=("#4a6fa5", "#3a5a8a"))
        else:
            self._widget_btn.configure(state="disabled", fg_color="gray50")

    def _on_filter_changed(self, *_args) -> None:
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.after(SEARCH_DEBOUNCE_MS, self._refresh_cards)

    def _build_cards(self) -> None:
        self._search_job = None
        self._cards: dict[int, object] = {}
        self._empty_frame = None
        for w in self._body.winfo_children():
            w.destroy()
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        self._search_job = None
        filter_text = self._filter_var.get().strip().lower() if hasattr(self, "_filter_var") else ""
        summaries = [
            s for s in self._summaries_all
            if filter_text in s.project.name.lower()
        ]
        if not summaries:
            existing = getattr(self, "_cards", None)
            if existing:
                for pid in list(existing):
                    existing[pid].destroy()
                    del existing[pid]
            if self._empty_frame is None:
                self._empty_frame = ctk.CTkFrame(self._body, fg_color=("gray90", "gray17"), corner_radius=12)
                self._empty_frame.grid(row=0, column=0, sticky="ew", pady=24)
                ctk.CTkLabel(
                    self._empty_frame,
                    text="No projects yet.\nCreate one and start accumulating focused work."
                    if not self._summaries_all else "No matching projects.",
                    text_color="gray60",
                    justify="center",
                    font=ctk.CTkFont(size=14),
                ).pack(padx=40, pady=48)
            return
        if self._empty_frame is not None:
            self._empty_frame.destroy()
            self._empty_frame = None
        existing = getattr(self, "_cards", None)
        if not existing:
            existing = {}
            self._cards = existing
        for s in summaries:
            assert s.project.id is not None
            card = existing.get(s.project.id)
            if card is None:
                card = self._build_card(self._body, s, 0, self._on_open_project, self._on_quick_work)
                existing[s.project.id] = card
            else:
                self._update_card(card, s)
        stale = [pid for pid in existing if pid not in {s.project.id for s in summaries}]
        for pid in stale:
            existing[pid].destroy()
            del existing[pid]
        for index, s in enumerate(summaries):
            assert s.project.id is not None
            existing[s.project.id].grid(row=index, column=0, sticky="ew", pady=6)

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

    def _build_card(self, parent, summary, index, on_open_project, on_quick_work):
        card = ctk.CTkFrame(parent, corner_radius=12, border_width=1, border_color=("gray78", "gray28"))
        card.grid(row=index, column=0, sticky="ew", pady=6)
        card.grid_columnconfigure(0, weight=1)
        assert summary.project.id is not None
        card.pid = summary.project.id

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=20, pady=16)

        name_label = ctk.CTkLabel(
            info, text="", font=ctk.CTkFont(size=18, weight="bold"), anchor="w"
        )
        name_label.pack(anchor="w")
        status_frame = ctk.CTkFrame(info, fg_color="transparent")

        meta_label = ctk.CTkLabel(
            info, text="", text_color="gray60", font=ctk.CTkFont(size=13), anchor="w"
        )

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=1, padx=(0, 20), pady=16)
        work_button = ctk.CTkButton(actions, text="", width=110, height=34)
        work_button.grid(row=0, column=0)
        ctk.CTkButton(
            actions, text="\u270E", width=34, height=34, fg_color="transparent",
            border_width=1, border_color=("gray65", "gray35"),
            text_color=("gray40", "gray65"),
            command=lambda: self._edit_project(summary),
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            actions, text="\U0001F4E6", width=34, height=34, fg_color="transparent",
            border_width=1, border_color=("gray65", "gray35"),
            text_color="#ef9a9a", hover_color=("gray88", "gray22"),
            command=lambda: self._archive_project(summary),
        ).grid(row=0, column=2, padx=(6, 0))

        card.info = info
        card.name_label = name_label
        card.status_frame = status_frame
        card.meta_label = meta_label
        card.work_button = work_button
        card.goal_frame = None
        card.pid = summary.project.id
        card.id_open = on_open_project
        card.id_work = on_quick_work
        card.click_set = False

        self._populate_card(card, summary, build=True)
        return card

    def _populate_card(self, card, summary, build: bool = False) -> None:
        card.name_label.configure(text=summary.project.name)
        for w in card.status_frame.winfo_children():
            w.destroy()
        if summary.project.id == self._active_project_id and self._active_state is not None:
            badge_text = "\u25CF  Running" if self._active_state == "running" else "\u2758\u2758  Paused"
            badge_color = "#66bb6a" if self._active_state == "running" else "#ffb74d"
            ctk.CTkLabel(
                card.status_frame, text=badge_text, text_color=badge_color,
                font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
            ).pack(anchor="w", pady=(2, 0))
        elif summary.project.id in self._parked_map:
            parked_seconds = self._parked_map[summary.project.id]
            if parked_seconds > 0:
                ctk.CTkLabel(
                    card.status_frame,
                    text=f"\u23F8  {format_duration(parked_seconds)} parked",
                    text_color="#ffb74d", font=ctk.CTkFont(size=12), anchor="w",
                ).pack(anchor="w", pady=(2, 0))
        if card.status_frame.winfo_children():
            card.status_frame.pack(anchor="w")
        else:
            card.status_frame.pack_forget()

        meta_parts = [format_duration(summary.total_seconds), f"{summary.session_count} sessions"]
        if summary.today_seconds > 0:
            meta_parts.append(f"{format_duration(summary.today_seconds)} today")
        meta_text = "  ·  ".join(meta_parts)
        if summary.contribution_count:
            meta_text += f"  ·  {summary.contribution_count} contributions"
        if summary.last_activity is not None:
            meta_text += f"  ·  last {format_day_label(summary.last_activity).lower()}"
        card.meta_label.configure(text=meta_text)
        if not build:
            card.meta_label.pack_configure(pady=(4, 0))
        else:
            card.meta_label.pack(anchor="w", pady=(4, 0))

        goal_minutes = summary.project.daily_goal_minutes
        if goal_minutes > 0 and card.goal_frame is None:
            card.goal_frame = ctk.CTkFrame(card.info, fg_color="transparent")
        if card.goal_frame is not None:
            for w in card.goal_frame.winfo_children():
                w.destroy()
            if goal_minutes > 0:
                goal_seconds = goal_minutes * 60
                ratio = min(1.0, summary.today_seconds / goal_seconds) if goal_seconds else 0.0
                done_today = ratio >= 1.0
                goal_label = ctk.CTkLabel(
                    card.goal_frame,
                    text=(
                        f"{format_duration(summary.today_seconds)} / {format_duration(goal_seconds)} today"
                        + ("  \u2713" if done_today else "")
                    ),
                    text_color="#66bb6a" if done_today else "gray60",
                    font=ctk.CTkFont(size=12),
                    anchor="w",
                )
                goal_label.pack(anchor="w", pady=(6, 2))
                bar = ctk.CTkProgressBar(card.goal_frame, width=280, height=8, corner_radius=4)
                bar.set(ratio)
                if done_today:
                    bar.configure(progress_color="#66bb6a")
                bar.pack(anchor="w")
                card.goal_frame.pack(anchor="w")
            else:
                card.goal_frame.pack_forget()

        work_label = "\u23F1  Focus"
        if self._active_project_id is not None and summary.project.id != self._active_project_id:
            work_label = "\u21C4  Switch"
        card.work_button.configure(text=work_label)

        if not card.click_set:
            click_widgets = [card, card.info, card.name_label, card.meta_label]
            if card.goal_frame is not None:
                goal_block = card.goal_frame
                if goal_block.winfo_children():
                    click_widgets.append(goal_block.winfo_children()[0])
            for widget in click_widgets:
                widget.configure(cursor="hand2")
                widget.bind(
                    "<Button-1>",
                    lambda _e, pid=summary.project.id: card.id_open(pid),
                )
            card.work_button.configure(command=lambda pid=summary.project.id: card.id_work(pid))
            card.click_set = True

    def _update_card(self, card, summary) -> None:
        self._populate_card(card, summary, build=False)
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
