import time
import traceback
from tkinter import TclError

import customtkinter as ctk

try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]

from config import (
    ALERT_CAPTION_COLOR,
    ALERT_OPENING_TONES,
    ALERT_REPEAT_TONES,
    ALERT_SOUND_REPEAT_MS,
    APP_NAME,
    FLUSH_INTERVAL_SECONDS,
    TICK_MS,
)
from domain.session import SessionStatus
from services.project_service import ProjectService
from services.session_service import SessionService
from services.settings_service import SettingsService
from services.timer_service import TimerMode, TimerService
from storage.database import Database
from ui.dashboard import Dashboard
from ui.dialogs import ProjectFormDialog, RecoveryDialog, confirm
from ui.project_view import ProjectView
from ui.settings_dialog import SettingsDialog
from ui.timer_view import TimerView
from utils.alerts import (
    flash_until_focus,
    get_hwnd,
    is_foreground,
    set_caption_color,
    stop_flash,
    system_caption_color,
)
from utils.formatting import format_clock, format_duration, format_time


class ChromodoroApp(ctk.CTk):
    def __init__(self, db_path=None):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title(APP_NAME)
        self.geometry("1000x700")
        self.minsize(780, 540)

        self._db = Database(db_path)
        self._timer = TimerService()
        self._settings = SettingsService(self._db)
        self._sessions = SessionService(self._db, self._timer, self._settings)
        self._projects = ProjectService(self._db)

        self._view = None
        self._project_name_cache: dict[int, str] = {}
        self._last_flush = time.monotonic()
        self._tick_job: str | None = None
        self._alert_job: str | None = None
        self._alerting = False
        self._hwnd = get_hwnd(self)
        self._caption_restore = system_caption_color(is_dark_theme=True)

        self.bind("<FocusIn>", self._on_focus_in)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._recover_pending_sessions()
        self._schedule_tick()

    def report_callback_exception(self, exc, val, tb) -> None:
        if isinstance(val, TclError) and (
            "bad window path name" in str(val) or "invalid command name" in str(val)
        ):
            return
        traceback.print_exception(exc, val, tb)

    def _swap(self, frame) -> None:
        if self._view is not None:
            self._view.destroy()
        frame.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._view = frame

    def show_dashboard(self) -> None:
        self.title(APP_NAME)
        self._swap(
            Dashboard(
                self,
                self._projects,
                on_open_project=self.open_project,
                on_new_project=self._new_project_dialog,
                on_quick_work=self.start_focus,
                on_open_settings=self._open_settings_dialog,
            )
        )

    def open_project(self, project_id: int) -> None:
        try:
            project = self._projects.get_project(project_id)
        except KeyError:
            self.show_dashboard()
            return
        assert project.id is not None
        self._project_name_cache[project.id] = project.name
        self._swap(
            ProjectView(
                self,
                project,
                self._projects,
                on_back=self.show_dashboard,
                on_work=lambda: self.start_focus(project.id),
                on_changed=lambda: self.open_project(project.id),
                on_archived=self.show_dashboard,
            )
        )

    def start_focus(self, project_id: int) -> None:
        if self._sessions.has_active and (
            self._sessions.active is None or self._sessions.active.project_id != project_id
        ):
            self._enter_timer(project_id, start_session=False)
            return
        self._enter_timer(project_id, start_session=not self._sessions.has_active)

    def _new_project_dialog(self) -> None:
        dialog = ProjectFormDialog(self, title="New project")
        result = dialog.show()
        if result:
            name, description, goal = result
            project = self._projects.create_project(name, description, daily_goal_minutes=goal)
            assert project.id is not None
            self.open_project(project.id)
        else:
            self.show_dashboard()

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self, self._settings.load())
        result = dialog.show()
        if result is not None:
            self._settings.save(result)

    def _enter_timer(self, project_id: int, *, start_session: bool) -> None:
        try:
            project = self._projects.get_project(project_id)
        except KeyError:
            self.show_dashboard()
            return
        assert project.id is not None
        self._swap(
            TimerView(
                self,
                project,
                self._sessions,
                self._timer,
                start_session=start_session,
                on_exit_project=lambda: self.open_project(project.id),
                on_all_projects=self.show_dashboard,
            )
        )

    def _recover_pending_sessions(self) -> None:
        pending = self._sessions.recover_pending()
        if not pending:
            self.show_dashboard()
            return

        resumed = False
        for session, elapsed in pending:
            if resumed:
                self._sessions.resolve_stale(session, SessionStatus.INTERRUPTED)
                continue
            try:
                project = self._projects.get_project(session.project_id)
            except KeyError:
                self._sessions.resolve_stale(session, SessionStatus.CANCELLED)
                continue

            choice = RecoveryDialog(
                self,
                project.name,
                f"started at {format_time(session.started_at)}",
                format_duration(elapsed),
            ).show()

            if choice == "resume":
                self._sessions.adopt(session)
                assert project.id is not None
                self._project_name_cache[project.id] = project.name
                self._enter_timer(project.id, start_session=False)
                resumed = True
            elif choice == "finish":
                self._sessions.adopt(session)
                self._sessions.register_interrupted()
            else:
                self._sessions.adopt(session)
                self._sessions.discard()

        if not resumed:
            self.show_dashboard()

    def _tick(self) -> None:
        completed = self._timer.poll()
        if completed:
            self._notify()
            self._handle_completion()
        elif self._sessions.has_active and time.monotonic() - self._last_flush >= FLUSH_INTERVAL_SECONDS:
            self._sessions.tick_flush()
            self._last_flush = time.monotonic()

        if isinstance(self._view, TimerView):
            self._view.on_tick()

        self._update_title()
        self._schedule_tick()

    def _schedule_tick(self) -> None:
        self._tick_job = self.after(TICK_MS, self._tick)

    def _handle_completion(self) -> None:
        if self._timer.mode is TimerMode.WORK and self._sessions.has_active:
            finished = self._sessions.complete()
            if isinstance(self._view, TimerView):
                self._view.show_review(finished)
        else:
            if isinstance(self._view, TimerView):
                self._view.break_finished()

    def _update_title(self) -> None:
        active = self._sessions.active
        if active is not None and self._timer.is_running:
            name = self._resolve_project_name(active.project_id)
            self.title(f"{format_clock(self._timer.remaining())} · {name} — {APP_NAME}")
        else:
            self.title(APP_NAME)

    def _resolve_project_name(self, project_id: int) -> str:
        if project_id not in self._project_name_cache:
            try:
                self._project_name_cache[project_id] = self._projects.get_project(project_id).name
            except KeyError:
                self._project_name_cache[project_id] = "Project"
        return self._project_name_cache[project_id]

    def _ensure_hwnd(self) -> int | None:
        if not self._hwnd:
            self._hwnd = get_hwnd(self)
        return self._hwnd

    def _sound_enabled(self) -> bool:
        try:
            return self._settings.load().sound_alerts
        except Exception:
            return True

    def _play_tones(self, tones) -> None:
        def play(index: int) -> None:
            if not self._alerting or not self._sound_enabled():
                return
            frequency, duration = tones[index]
            try:
                if winsound is not None:
                    winsound.Beep(frequency, duration)
                else:
                    self.bell()
            except Exception:
                self.bell()
            next_index = index + 1
            if next_index < len(tones):
                self.after(60, lambda n=next_index: play(n))

        self.after(0, lambda: play(0))

    def _notify(self) -> None:
        if self._alerting:
            return
        self._alerting = True
        hwnd = self._ensure_hwnd()
        if hwnd:
            try:
                flash_until_focus(hwnd)
                set_caption_color(hwnd, ALERT_CAPTION_COLOR)
            except Exception:
                pass
        self._play_tones(ALERT_OPENING_TONES)
        self._schedule_alert_repeat()

    def _schedule_alert_repeat(self) -> None:
        self._alert_job = self.after(ALERT_SOUND_REPEAT_MS, self._alert_repeat)

    def _alert_repeat(self) -> None:
        self._alert_job = None
        if not self._alerting:
            return
        if self._hwnd and is_foreground(self._hwnd):
            self._stop_alerts()
            return
        self._play_tones(ALERT_REPEAT_TONES)
        self._schedule_alert_repeat()

    def _stop_alerts(self) -> None:
        self._alerting = False
        if self._alert_job is not None:
            self.after_cancel(self._alert_job)
            self._alert_job = None
        if self._hwnd:
            try:
                stop_flash(self._hwnd)
                set_caption_color(self._hwnd, self._caption_restore)
            except Exception:
                pass

    def _on_focus_in(self, event) -> None:
        self._stop_alerts()

    def _on_close(self) -> None:
        if self._tick_job is not None:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self._stop_alerts()
        if self._sessions.has_active:
            proceed = confirm(
                self,
                "Quit Chromodoro",
                "A focus session is running.\n\n"
                "If you quit now the session will be kept safe and offered "
                "for recovery next time you open Chromodoro.\n\nQuit anyway?",
            )
            if not proceed:
                return
            self._sessions.tick_flush()
        self._db.close()
        self.destroy()


def main(db_path=None) -> None:
    app = ChromodoroApp(db_path=db_path)
    app.mainloop()
