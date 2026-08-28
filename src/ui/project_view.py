import tkinter as tk
from tkinter import font as tkfont

import customtkinter as ctk

from domain.project import Project
from services.project_service import ProjectService
from ui.dialogs import ProjectFormDialog, TextPromptDialog, confirm
from utils.formatting import format_date_heading, format_day_label, format_duration, format_time

_TK_BG = "#242424"
_TK_CARD = "#2b2b2b"
_TK_FG = "#DCE4EE"
_TK_MUTED = "#9aa4b2"
_TK_HEADING = "#8f959f"


class ProjectView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        project: Project,
        project_service: ProjectService,
        on_back,
        on_work,
        on_changed,
        on_archived,
        switch_mode: bool = False,
        focus_bar_fn=None,
    ):
        super().__init__(master, fg_color="transparent")
        self._project = project
        assert project.id is not None
        self._project_id = project.id
        self._projects = project_service
        self._on_changed = on_changed
        self._on_archived = on_archived

        self.grid_columnconfigure(0, weight=1)
        next_row = 0
        bar = focus_bar_fn(self) if focus_bar_fn is not None else None
        if bar is not None:
            bar.grid(row=next_row, column=0, sticky="ew", padx=28, pady=(14, 2))
            next_row += 1
        self.grid_rowconfigure(next_row + 6, weight=1)

        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.grid(row=next_row, column=0, sticky="ew", padx=28, pady=(18, 0))
        ctk.CTkButton(
            topbar, text="< All projects", width=110, height=30, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray35"), command=on_back,
        ).pack(side="left")

        actions = ctk.CTkFrame(topbar, fg_color="transparent")
        actions.pack(side="right")
        ctk.CTkButton(
            actions, text="Edit", width=70, height=30, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray35"), command=self._edit_project,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            actions, text="Archive", width=80, height=30, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray35"),
            text_color="#ef9a9a", hover_color=("gray88", "gray22"), command=self._archive_project,
        ).pack(side="left", padx=4)

        ctk.CTkLabel(
            self, text=project.name.upper(), font=ctk.CTkFont(size=26, weight="bold"), anchor="w"
        ).grid(row=next_row + 1, column=0, sticky="ew", padx=32, pady=(14, 2))

        description = project.description or "No description yet."
        ctk.CTkLabel(
            self, text=description, text_color="gray60", font=ctk.CTkFont(size=13),
            anchor="w", wraplength=760, justify="left",
        ).grid(row=next_row + 2, column=0, sticky="ew", padx=32, pady=(0, 14))

        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=next_row + 3, column=0, sticky="ew", padx=32, pady=(0, 10))

        stats = project_service.project_stats(self._project_id)
        today_secs = project_service.today_seconds(self._project_id)
        blocks = [
            (format_duration(stats.total_seconds), "Time invested"),
            (format_duration(today_secs), "Today"),
            (str(stats.session_count), "Sessions"),
            (str(stats.contribution_count), "Contributions"),
            (str(stats.notes_count), "Notes"),
        ]
        if project.daily_goal_minutes > 0:
            minutes = int(project.daily_goal_minutes)
            blocks.append((f"{minutes} min", "Daily goal"))
        for index in range(len(blocks)):
            stats_frame.grid_columnconfigure(index, weight=1)
        for index, (value, caption) in enumerate(blocks):
            self._stat_block(stats_frame, index, value, caption)

        work_label = "\u21C4  Switch here" if switch_mode else "\u23F1  Focus"
        ctk.CTkButton(
            self, text=work_label, height=46, width=260, font=ctk.CTkFont(size=16, weight="bold"),
            command=on_work,
        ).grid(row=next_row + 4, column=0, pady=(6, 4))

        last_line = "No sessions yet."
        if stats.last_activity is not None:
            last_line = (
                f"Last activity: {format_day_label(stats.last_activity)} "
                f"at {format_time(stats.last_activity)}"
            )
        ctk.CTkLabel(self, text=last_line, text_color="gray55", font=ctk.CTkFont(size=12)).grid(
            row=next_row + 5, column=0, pady=(2, 8)
        )

        history = ctk.CTkScrollableFrame(self, fg_color="transparent")
        history.grid(row=next_row + 6, column=0, sticky="nsew", padx=28, pady=(4, 18))
        history.grid_columnconfigure(0, weight=1)

        self._build_notes(history)
        self._build_contributions(history, stats)
        self._build_history(history)

    def _add_note(self) -> None:
        dialog = TextPromptDialog(
            self.winfo_toplevel(),
            title="Add note",
            label="Note",
            ok_text="Add note",
            empty_message="Write something first.",
        )
        title = dialog.show()
        if title is None:
            return
        try:
            self._projects.add_note(self._project_id, title)
        except ValueError:
            return
        self._on_changed()

    def _build_notes(self, parent) -> None:
        ctk.CTkLabel(
            parent, text="Notes", font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
        ).grid(row=0, column=0, sticky="ew", pady=(6, 2))
        ctk.CTkButton(
            parent, text="+ Note", width=70, height=24, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray35"),
            command=self._add_note,
        ).grid(row=0, column=1, sticky="e", padx=8, pady=(6, 2))

        notes = self._projects.notes(self._project_id)
        if not notes:
            ctk.CTkLabel(
                parent,
                text="Quick thoughts and ideas live here — no timer needed.",
                text_color="gray55",
            ).grid(row=1, column=0, sticky="w", padx=8, pady=(2, 8))
            return
        body_font = tkfont.Font(size=13)
        muted_font = tkfont.Font(size=11)
        act_font = tkfont.Font(size=13)
        row = 1
        for note in notes:
            item = tk.Frame(parent, bg=_TK_BG)
            item.grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=3)
            item.columnconfigure(0, weight=1)
            tk.Label(
                item, text="\u2022  " + note.title, font=body_font, fg=_TK_FG, bg=_TK_BG,
                anchor="w", justify="left", wraplength=620,
            ).grid(row=0, column=0, sticky="w")
            created = note.created_at
            detail = format_day_label(created) if created is not None else ""
            tk.Label(
                item, text=detail, fg=_TK_MUTED, bg=_TK_BG, font=muted_font, anchor="w"
            ).grid(row=1, column=0, sticky="w", padx=(14, 0))
            actions = tk.Frame(item, bg=_TK_BG)
            actions.grid(row=0, column=1, rowspan=2, padx=(8, 2))
            edit_lbl = tk.Label(
                actions, text="\u270E", fg=_TK_FG, bg=_TK_BG, font=act_font, cursor="hand2"
            )
            edit_lbl.pack(side="left", padx=3)
            del_lbl = tk.Label(
                actions, text="\U0001F5D1", fg="#ef9a9a", bg=_TK_BG, font=act_font, cursor="hand2"
            )
            del_lbl.pack(side="left", padx=3)
            edit_lbl.bind("<Button-1>", lambda _e: self._edit_note(note))
            del_lbl.bind("<Button-1>", lambda _e: self._delete_note(note))
            row += 1

    def _stat_block(self, parent, column, value: str, caption: str) -> None:
        block = ctk.CTkFrame(parent, corner_radius=10, fg_color=("gray92", "gray15"))
        block.grid(row=0, column=column, sticky="ew", padx=6)
        ctk.CTkLabel(block, text=value, font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(12, 0))
        ctk.CTkLabel(block, text=caption, text_color="gray60", font=ctk.CTkFont(size=12)).pack(pady=(0, 12))

    def _build_contributions(self, parent, stats) -> None:
        ctk.CTkLabel(
            parent, text="Recent contributions", font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
        ).grid(row=40, column=0, sticky="ew", pady=(18, 2))

        items = [
            c for c in self._projects.contributions(self._project_id, limit=8)
            if c.session_id is not None
        ]
        if not items:
            ctk.CTkLabel(parent, text="Contributions come from focus sessions.", text_color="gray55").grid(
                row=41, column=0, sticky="w", padx=8, pady=(2, 8)
            )
            return
        body_font = tkfont.Font(size=13)
        muted_font = tkfont.Font(size=11)
        act_font = tkfont.Font(size=13)
        row = 41
        session_durations = {s.id: s.duration for s in self._projects.sessions(self._project_id)}
        for contribution in items:
            item = tk.Frame(parent, bg=_TK_BG)
            item.grid(row=row, column=0, sticky="ew", padx=8, pady=3)
            item.columnconfigure(0, weight=1)

            bullet = "\u2022  " + contribution.title
            tk.Label(
                item, text=bullet, font=body_font, fg=_TK_FG, bg=_TK_BG,
                anchor="w", justify="left", wraplength=620,
            ).grid(row=0, column=0, sticky="w")
            created = contribution.created_at
            detail = format_day_label(created) if created is not None else ""
            duration = session_durations.get(contribution.session_id)
            if duration:
                detail += f" — {format_duration(duration)}"
            tk.Label(
                item, text=detail, fg=_TK_MUTED, bg=_TK_BG, font=muted_font, anchor="w"
            ).grid(row=1, column=0, sticky="w", padx=(14, 0))

            actions = tk.Frame(item, bg=_TK_BG)
            actions.grid(row=0, column=1, rowspan=2, padx=(8, 2))
            edit_lbl = tk.Label(
                actions, text="\u270E", fg=_TK_FG, bg=_TK_BG, font=act_font, cursor="hand2"
            )
            edit_lbl.pack(side="left", padx=3)
            del_lbl = tk.Label(
                actions, text="\U0001F5D1", fg="#ef9a9a", bg=_TK_BG, font=act_font, cursor="hand2"
            )
            del_lbl.pack(side="left", padx=3)
            edit_lbl.bind("<Button-1>", lambda _e: self._edit_contribution(contribution))
            del_lbl.bind("<Button-1>", lambda _e: self._delete_contribution(contribution))
            row += 1

    def _edit_contribution(self, contribution) -> None:
        dialog = TextPromptDialog(
            self.winfo_toplevel(),
            title="Edit contribution",
            initial=contribution.title,
            label="Contribution",
            empty_message="Write something first.",
        )
        new_title = dialog.show()
        if new_title is None or new_title == contribution.title:
            return
        self._projects.update_contribution(contribution.id, new_title)
        self._on_changed()

    def _delete_contribution(self, contribution) -> None:
        message = (
            f"Delete '{contribution.title}'?\n\n"
            "The session time is kept; only this entry is removed."
        )
        if not confirm(self.winfo_toplevel(), "Delete contribution", message):
            return
        self._projects.delete_contribution(contribution.id)
        self._on_changed()

    def _edit_note(self, note) -> None:
        dialog = TextPromptDialog(
            self.winfo_toplevel(),
            title="Edit note",
            initial=note.title,
            label="Note",
            empty_message="Write something first.",
        )
        new_title = dialog.show()
        if new_title is None or new_title == note.title:
            return
        self._projects.update_contribution(note.id, new_title)
        self._on_changed()

    def _delete_note(self, note) -> None:
        message = f"Delete note '{note.title}'?"
        if not confirm(self.winfo_toplevel(), "Delete note", message):
            return
        self._projects.delete_contribution(note.id)
        self._on_changed()
    def _build_history(self, parent) -> None:
        bold = tkfont.Font(size=15, weight="bold")
        sub_bold = tkfont.Font(size=12, weight="bold")
        body_font = tkfont.Font(size=13)
        muted_font = tkfont.Font(size=12)
        small_font = tkfont.Font(size=11)

        ctk.CTkLabel(
            parent, text="History", font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
        ).grid(row=100, column=0, sticky="ew", pady=(18, 2))

        sessions = self._projects.sessions(self._project_id)
        counted = [s for s in sessions if s.status.value != "running"]
        if not counted:
            ctk.CTkLabel(parent, text="No sessions yet.", text_color="gray55").grid(
                row=101, column=0, sticky="w", padx=8, pady=(2, 8)
            )
            return

        grouped: dict[str, list] = {}
        order: list[str] = []
        for session in counted:
            heading = format_date_heading(session.started_at)
            if heading not in grouped:
                grouped[heading] = []
                order.append(heading)
            grouped[heading].append(session)

        by_session = self._projects.contributions_by_session(self._project_id)
        status_colors = {
            "completed": "#66bb6a",
            "interrupted": "#ffb74d",
            "cancelled": _TK_MUTED,
        }

        row = 101
        for heading in order:
            tk.Label(
                parent, text=heading, font=sub_bold, fg=_TK_HEADING, bg=_TK_BG,
                anchor="w", justify="left",
            ).grid(row=row, column=0, sticky="w", padx=8, pady=(8, 2))
            row += 1
            for session in grouped[heading]:
                entry = tk.Frame(parent, bg=_TK_CARD, bd=0, highlightthickness=1,
                                 highlightbackground=_TK_CARD)
                entry.grid(row=row, column=0, sticky="ew", padx=8, pady=2)
                entry.grid_columnconfigure(0, weight=1)
                entry.columnconfigure(0, weight=1)

                start = format_time(session.started_at)
                end = format_time(session.ended_at) if session.ended_at else "\u2026"
                line = tk.Frame(entry, bg=_TK_CARD)
                line.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))

                tk.Label(line, text=f"{start} \u2013 {end}", font=bold, fg=_TK_FG, bg=_TK_CARD).pack(
                    side="left"
                )
                tk.Label(
                    line, text=format_duration(session.duration), font=muted_font, fg=_TK_MUTED, bg=_TK_CARD,
                ).pack(side="left", padx=10)
                if session.pause_duration > 0:
                    tk.Label(
                        line,
                        text=f"\u00B7 paused {format_duration(session.pause_duration)}",
                        font=muted_font, fg=_TK_MUTED, bg=_TK_CARD,
                    ).pack(side="left")
                tk.Label(
                    line,
                    text=session.status.value,
                    font=small_font,
                    fg=status_colors.get(session.status.value, _TK_MUTED),
                    bg=_TK_CARD,
                ).pack(side="right")

                contributions = by_session.get(session.id, [])
                if contributions:
                    text = "\n".join(f"\u2022  {c.title}" for c in reversed(contributions))
                    tk.Label(
                        entry, text=text, font=body_font, fg="#c9d3de", bg=_TK_CARD,
                        anchor="w", justify="left", wraplength=680,
                    ).grid(row=1, column=0, sticky="ew", padx=20, pady=(2, 8))
                row += 1

    def _edit_project(self) -> None:
        dialog = ProjectFormDialog(
            self.winfo_toplevel(),
            title="Edit project",
            name=self._project.name,
            description=self._project.description,
            daily_goal_minutes=self._project.daily_goal_minutes,
        )
        result = dialog.show()
        if result:
            name, description, goal = result
            self._projects.update_project(self._project, name, description, daily_goal_minutes=goal)
            self._on_changed()

    def _archive_project(self) -> None:
        message = (
            f"Archive '{self._project.name}'?\n\n"
            "It will disappear from the dashboard but its history is preserved."
        )
        if not confirm(self.winfo_toplevel(), "Archive project", message):
            return
        self._projects.archive_project(self._project)
        self._on_archived()
