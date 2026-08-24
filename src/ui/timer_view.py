import customtkinter as ctk

from domain.project import Project
from domain.session import Session
from services.session_service import SessionService
from services.timer_service import TimerMode, TimerService, TimerState
from ui.dialogs import InterruptDialog
from utils.formatting import format_clock, format_duration


class TimerView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        project: Project,
        session_service: SessionService,
        timer: TimerService,
        *,
        start_session: bool,
        on_exit_project,
        on_all_projects,
    ):
        super().__init__(master, fg_color="transparent")
        self._project = project
        assert project.id is not None
        self._project_id = project.id
        self._sessions = session_service
        self._timer = timer
        self._on_exit_project = on_exit_project
        self._on_all_projects = on_all_projects
        self._finished: Session | None = None
        self._break_done = False

        if start_session and not session_service.has_active:
            session_service.start(self._project_id)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=0, column=0, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._render()

    def show_review(self, finished: Session) -> None:
        self._finished = finished
        self._render()

    def break_finished(self) -> None:
        self._break_done = True
        self._render()

    def on_tick(self) -> None:
        if self._finished is not None or self._break_done:
            return
        mode = self._timer.mode
        state = self._timer.state
        active_phase = (mode is TimerMode.BREAK and state in (TimerState.RUNNING, TimerState.PAUSED)) or (
            mode is TimerMode.WORK and state in (TimerState.RUNNING, TimerState.PAUSED)
        )
        if not active_phase:
            return
        if self._clock_label is not None and self._clock_label.winfo_exists():
            self._clock_label.configure(text=format_clock(self._timer.remaining()))
        if self._progress is not None and self._progress.winfo_exists():
            self._progress.set(self._timer.progress())

    def _clear(self) -> None:
        for widget in self._content.winfo_children():
            widget.destroy()
        self._clock_label = None
        self._progress = None

    def _render(self) -> None:
        self._clear()
        if self._finished is not None:
            self._render_review()
            return
        if self._break_done:
            self._render_break_done()
            return
        if self._timer.mode is TimerMode.BREAK:
            self._render_break()
            return
        if self._timer.state is TimerState.PAUSED:
            self._render_paused()
        else:
            self._render_running()

    def _header(self) -> None:
        ctk.CTkLabel(
            self._content, text=self._project.name.upper(), text_color="gray55",
            font=ctk.CTkFont(size=15, weight="bold"), text_color_disabled="gray",
        ).grid(row=0, column=0, pady=(8, 2))

    def _clock_and_progress(self) -> None:
        clock_label = ctk.CTkLabel(
            self._content,
            text=format_clock(self._timer.remaining()),
            font=ctk.CTkFont(family="Consolas", size=72, weight="bold"),
        )
        progress = ctk.CTkProgressBar(self._content, width=420, height=12, corner_radius=6)
        progress.set(self._timer.progress())
        self._clock_label = clock_label
        self._progress = progress
        clock_label.grid(row=3, column=0, pady=(6, 10))
        progress.grid(row=4, column=0, pady=(0, 30))

    def _render_running(self) -> None:
        self._header()
        ctk.CTkLabel(
            self._content, text="FOCUS", text_color="#66bb6a",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=1, column=0, pady=(14, 4))
        self._clock_and_progress()

        actions = ctk.CTkFrame(self._content, fg_color="transparent")
        actions.grid(row=5, column=0)
        ctk.CTkButton(actions, text="Pause", width=130, height=38, command=self._pause_clicked).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            actions, text="End session", width=130, height=38, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray35"), command=self._end_clicked,
        ).pack(side="left", padx=6)

    def _render_paused(self) -> None:
        self._header()
        ctk.CTkLabel(
            self._content, text="PAUSED", text_color="#ffb74d",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=1, column=0, pady=(14, 4))
        self._clock_and_progress()

        actions = ctk.CTkFrame(self._content, fg_color="transparent")
        actions.grid(row=5, column=0)
        ctk.CTkButton(actions, text="Resume", width=130, height=38, command=self._resume_clicked).pack(
            side="left", padx=6
        )
        ctk.CTkButton(
            actions, text="End session", width=130, height=38, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray35"), command=self._end_clicked,
        ).pack(side="left", padx=6)

    def _render_review(self) -> None:
        finished = self._finished
        assert finished is not None
        duration_text = format_duration(finished.duration)
        headline = (
            f"Pomodoro complete  ·  +{duration_text} logged"
            if finished.status.value == "completed"
            else f"Session registered  ·  +{duration_text} logged"
        )
        ctk.CTkLabel(self._content, text=headline, font=ctk.CTkFont(size=21, weight="bold")).grid(
            row=0, column=0, pady=(40, 2)
        )
        ctk.CTkLabel(
            self._content,
            text=f"Time added to {self._project.name}. What did you produce?",
            text_color="gray60",
        ).grid(row=1, column=0, pady=(0, 18))

        entry = ctk.CTkEntry(
            self._content, width=480, height=40, placeholder_text="e.g. Implemented map loading"
        )
        entry.grid(row=2, column=0, pady=4)
        entry.focus_set()

        feedback = ctk.CTkLabel(self._content, text="", text_color="#66bb6a", height=20)
        feedback.grid(row=3, column=0, pady=(2, 0))

        actions = ctk.CTkFrame(self._content, fg_color="transparent")
        actions.grid(row=4, column=0, pady=(10, 0))
        add_button = ctk.CTkButton(actions, text="Add contribution", width=170, height=38)
        add_button.pack(side="left", padx=6)
        break_seconds = self._sessions.peek_break_seconds()
        break_minutes = int(round(break_seconds / 60))
        break_label = (
            f"Long break \u25B8 {break_minutes} min"
            if self._sessions.completed_cycles >= self._sessions.config.cycles_before_long_break
            else f"Take a break \u25B8 {break_minutes} min"
        )
        ctk.CTkButton(
            actions, text=break_label, width=190, height=38, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray35"), command=self._start_break,
        ).pack(side="left", padx=6)

        def add() -> None:
            title = entry.get().strip()
            if not title:
                feedback.configure(text="Write something first, or take a break.", text_color="gray60")
                return
            self._sessions.add_contribution(finished, title)
            entry.delete(0, "end")
            feedback.configure(text=f"Added. ({title})", text_color="#66bb6a")

        add_button.configure(command=add)
        entry.bind("<Return>", lambda _e: add())

        ctk.CTkButton(
            self._content,
            text="< Back to project", width=160, height=28, fg_color="transparent",
            text_color="gray60", border_width=0, hover_color=("gray92", "gray17"),
            command=self._on_exit_project,
        ).grid(row=5, column=0, pady=(26, 0))

    def _render_break(self) -> None:
        self._header()
        is_long = self._timer.target >= self._sessions.config.long_break_minutes * 60
        ctk.CTkLabel(
            self._content,
            text="LONG BREAK" if is_long else "BREAK",
            text_color="#ba68c8" if is_long else "#64b5f6",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=1, column=0, pady=(14, 4))
        clock_label = ctk.CTkLabel(
            self._content,
            text=format_clock(self._timer.remaining()),
            font=ctk.CTkFont(family="Consolas", size=72, weight="bold"),
        )
        self._clock_label = clock_label
        clock_label.grid(row=3, column=0, pady=(24, 24))
        ctk.CTkButton(self._content, text="Skip break", width=140, height=36, command=self._skip_break).grid(
            row=5, column=0
        )

    def _render_break_done(self) -> None:
        ctk.CTkLabel(self._content, text="Break finished.", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, pady=(48, 4)
        )
        ctk.CTkLabel(
            self._content, text="Ready for another round of focus?", text_color="gray60"
        ).grid(row=1, column=0)

        ctk.CTkButton(
            self._content, text="\u25B6  Work again", width=220, height=44,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._work_again,
        ).grid(row=3, column=0, pady=(24, 6))

        links = ctk.CTkFrame(self._content, fg_color="transparent")
        links.grid(row=4, column=0, pady=(16, 0))
        ctk.CTkButton(
            links, text="Back to project", width=150, height=28, fg_color="transparent",
            text_color="gray60", hover_color=("gray92", "gray17"), command=self._on_exit_project,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            links, text="All projects", width=120, height=28, fg_color="transparent",
            text_color="gray60", hover_color=("gray92", "gray17"), command=self._on_all_projects,
        ).pack(side="left", padx=6)

    def _pause_clicked(self) -> None:
        self._sessions.pause()
        self._render()

    def _resume_clicked(self) -> None:
        self._sessions.resume()
        self._render()

    def _end_clicked(self) -> None:
        elapsed_text = format_duration(self._timer.elapsed())
        dialog = InterruptDialog(self.winfo_toplevel(), elapsed_text)
        choice = dialog.show()
        if choice == "register":
            self._finished = self._sessions.register_interrupted()
            self._render()
        elif choice == "discard":
            self._sessions.discard()
            self._on_exit_project()
        else:
            self._render()

    def _start_break(self) -> None:
        seconds = self._sessions.start_break()
        self._timer.start(seconds, TimerMode.BREAK)
        self._finished = None
        self._break_done = False
        self._render()

    def _skip_break(self) -> None:
        self._timer.cancel()
        self._break_done = True
        self._render()

    def _work_again(self) -> None:
        self._sessions.start(self._project_id)
        self._break_done = False
        self._finished = None
        self._render()
