import atexit
import time
import traceback
from pathlib import Path
from tkinter import TclError, messagebox

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
from domain.project import ARCHIVED
from domain.session import SessionStatus
from services.project_service import ProjectService
from services.session_service import SessionService
from services.settings_service import SettingsService
from services.timer_service import TimerMode, TimerService
from storage.database import Database, default_db_path
from ui.dashboard import Dashboard
from ui.dialogs import ProjectFormDialog, RecoveryDialog, confirm
from ui.focus_bar import FocusBar
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
from utils.keys import is_typing_widget
from utils.singleinstance import acquire_instance_lock
from utils.tray import TrayController


class ChromodoroApp(ctk.CTk):
    def __init__(self, db_path=None):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title(APP_NAME)
        self.minsize(780, 540)

        self._db = Database(db_path)
        self._timer = TimerService()
        self._settings = SettingsService(self._db)
        self._sessions = SessionService(self._db, self._timer, self._settings)
        self._projects = ProjectService(self._db)

        saved_geom = self._settings.get_str("window_geometry")
        self.geometry(saved_geom if saved_geom else "1000x700")

        self._view = None
        self._project_name_cache: dict[int, str] = {}
        self._last_flush = time.monotonic()
        self._tick_job: str | None = None
        self._alert_job: str | None = None
        self._alerting = False
        self._hwnd = get_hwnd(self)
        self._caption_restore = system_caption_color(is_dark_theme=True)
        self._tray = TrayController(APP_NAME)
        self._quit_from_tray = False
        self._mini_view = None
        self._mini_pending_project: int | None = None
        self._cached_dashboard = None

        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<space>", self._on_space_key)
        self.bind("<Escape>", self._on_escape_key)
        self.bind("<F2>", lambda _: self._open_settings_dialog())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._recover_pending_sessions()
        self._schedule_tick()
        self._tray.start()
        self._update_tray_tooltip()
        atexit.register(self._atexit_flush)
        try:
            if self._settings.load().start_in_tray:
                self.withdraw()
        except Exception:
            pass

    def _atexit_flush(self) -> None:
        try:
            if self._sessions.has_active:
                self._sessions.tick_flush()
        except Exception:
            pass

    def report_callback_exception(self, exc, val, tb) -> None:
        if isinstance(val, TclError) and (
            "bad window path name" in str(val) or "invalid command name" in str(val)
        ):
            return
        traceback.print_exception(exc, val, tb)

    def _swap(self, frame) -> None:
        previous = self._view
        if previous is not None and previous is not frame:
            previous.grid_remove()
            if previous is not self._cached_dashboard:
                previous.destroy()
        frame.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._view = frame

    def _build_focus_bar(self, master):
        active = self._sessions.active
        if active is None or active.project_id is None:
            return None
        name = self._resolve_project_name(active.project_id)
        return FocusBar(
            master,
            project_name=name,
            clock_fn=self._timer.remaining,
            running_fn=lambda: self._timer.is_running,
            on_toggle=self._toggle_active_pause,
            on_open=self._open_active_focus,
        )

    def _toggle_active_pause(self) -> None:
        if self._sessions.active is None:
            if self._mini_pending_project is not None:
                self._start_break_from_mini()
                return
            if self._timer.mode is TimerMode.BREAK:
                if self._timer.is_running:
                    self._timer.pause()
                elif self._timer.state.value == "paused":
                    self._timer.resume()
            return
        if self._timer.state.value == "paused":
            self._sessions.resume()
        else:
            self._sessions.pause()

    def _start_break_from_mini(self) -> None:
        try:
            seconds = self._sessions.start_break()
            self._timer.start(seconds, TimerMode.BREAK)
        except Exception:
            return
        self._mini_pending_project = None
        if self._mini_view is not None and self._mini_view.winfo_exists():
            self._mini_view.show_normal()
        self._refresh_mini()

    def _open_active_focus(self) -> None:
        active = self._sessions.active
        if active is None:
            self.show_dashboard()
            return
        self.start_focus(active.project_id)

    def _toggle_mini(self) -> None:
        if self._mini_view is not None:
            self._close_mini()
            return
        if self._sessions.active is None:
            return
        self._open_mini()

    def _open_mini(self) -> None:
        if self._mini_view is not None:
            return
        from ui.mini_view import MiniView

        saved_pos = self._settings.get_str("mini_position")
        self._mini_view = MiniView(
            self,
            on_toggle=self._toggle_active_pause,
            on_close=self._close_mini,
            on_switch=self._switch_mini_project,
            on_refresh=self._refresh_mini,
            saved_position=saved_pos,
        )
        self._refresh_mini()
        self.withdraw()

    def _close_mini(self) -> None:
        if self._mini_view is None:
            return
        try:
            geo = self._mini_view.geometry()
            parts = geo.split("+")
            if len(parts) == 3:
                self._settings.set_str("mini_position", f"{parts[1]}+{parts[2]}")
        except Exception:
            pass
        self._mini_view.destroy()
        self._mini_view = None
        self._mini_pending_project = None
        self.deiconify()
        self.lift()
        self._refresh_main_view_state()
        self.focus_force()

    def _refresh_main_view_state(self) -> None:
        from ui.timer_view import TimerView

        if not isinstance(self._view, TimerView):
            return
        if self._sessions.active is None and self._timer.mode is TimerMode.BREAK:
            self._view.refresh_state()

    def _refresh_mini(self) -> None:
        if self._mini_view is None or not self._mini_view.winfo_exists():
            return
        name = ""
        active = self._sessions.active
        if active is not None and active.project_id is not None:
            name = self._resolve_project_name(active.project_id)
        self._mini_view.update_info(
            format_clock(self._timer.remaining()),
            self._timer.is_running,
            name,
        )

    def _switch_mini_project(self) -> None:
        from ui.dialogs import SwitchProjectDialog

        active = self._sessions.active
        current_pid = active.project_id if active is not None else None
        parked = self._sessions.parked_map()
        summaries = self._projects.list_summaries()

        targets: list[tuple[int, str]] = []
        for s in summaries:
            pid = s.project.id
            if pid is None or pid == current_pid:
                continue
            label = s.project.name
            seconds = parked.get(pid)
            if seconds:
                label += f"  ({format_duration(seconds)} parked)"
            targets.append((pid, label))

        if not targets:
            return

        dialog = SwitchProjectDialog(self._mini_view, targets)
        chosen = dialog.show()
        if chosen is not None:
            self._sessions.switch_to(chosen)
            self._mini_pending_project = None
            self._refresh_mini()

    def _mini_log(self, session) -> None:
        from ui.dialogs import TextPromptDialog

        dialog = TextPromptDialog(
            self,
            title="Log contribution",
            label="What did you accomplish?",
            ok_text="Log",
            empty_message="Write something first.",
        )
        title = dialog.show()
        if title is not None and session.project_id is not None and session.id is not None:
            from domain.contribution import Contribution

            self._db.insert_contribution(
                Contribution(
                    project_id=session.project_id,
                    title=title,
                    session_id=session.id,
                )
            )
        if self._mini_view is not None and self._mini_view.winfo_exists():
            self._mini_view.show_normal()
        self._refresh_mini()

    def _mini_skip(self, session) -> None:
        if self._mini_view is not None and self._mini_view.winfo_exists():
            self._mini_view.show_normal()
        self._refresh_mini()

    def _mini_break_done(self) -> None:
        started = False
        if self._auto_start_enabled():
            active = self._sessions.active
            if active is not None and active.project_id is not None:
                try:
                    self._sessions.start(active.project_id)
                    started = True
                except Exception:
                    pass
        if started:
            self._mini_pending_project = None
        if self._mini_view is not None and self._mini_view.winfo_exists():
            self._mini_view.show_normal()
        self._refresh_mini()

    def show_dashboard(self) -> None:
        self.title(APP_NAME)
        active = self._sessions.active
        active_pid = active.project_id if active is not None else None
        parked = {
            pid: seconds
            for pid, seconds in self._sessions.parked_map().items()
            if pid != active_pid
        }
        if self._cached_dashboard is None:
            self._cached_dashboard = Dashboard(
                self,
                self._projects,
                on_open_project=self.open_project,
                on_new_project=self._new_project_dialog,
                on_quick_work=self.start_focus,
                on_open_settings=self._open_settings_dialog,
                on_changed=self._on_project_data_changed,
                active_project_id=active_pid,
                active_state=self._timer.state.value if active is not None else None,
                parked_map=parked,
                focus_bar_fn=self._build_focus_bar,
                on_quit=self._force_quit,
                on_widget=self._toggle_mini,
            )
        else:
            self._cached_dashboard._summaries_all = self._projects.list_summaries()
            self._cached_dashboard.update_state(
                active_project_id=active_pid,
                active_state=self._timer.state.value if active is not None else None,
                parked_map=parked,
            )
        self._swap(self._cached_dashboard)

    def _on_project_data_changed(self) -> None:
        self._project_name_cache.clear()
        self.show_dashboard()

    def open_project(self, project_id: int) -> None:
        try:
            project = self._projects.get_project(project_id)
        except KeyError:
            self.show_dashboard()
            return
        assert project.id is not None
        self._project_name_cache[project.id] = project.name
        active = self._sessions.active
        switch_mode = active is not None and active.project_id != project.id
        self._swap(
            ProjectView(
                self,
                project,
                self._projects,
                on_back=self.show_dashboard,
                on_work=lambda: self.start_focus(project.id),
                on_changed=lambda: self.open_project(project.id),
                on_archived=self.show_dashboard,
                switch_mode=switch_mode,
                focus_bar_fn=self._build_focus_bar,
            )
        )

    def start_focus(self, project_id: int) -> None:
        self._sessions.switch_to(project_id)
        self._enter_timer(project_id, start_session=False)

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
                on_switch=lambda: self._quick_switch(project.id),
                on_switch_project=self._quick_switch,
                switch_targets_fn=self._switch_targets,
                project_namer=self._resolve_project_name,
                today_total_fn=lambda pid: self._projects.today_seconds(pid),
                on_toggle_mini=self._toggle_mini,
            )
        )

    def _switch_targets(self, exclude_pid: int) -> list[tuple[int, str]]:
        parked = self._sessions.parked_map()
        targets: list[tuple[int, str]] = []
        for summary in self._projects.list_summaries():
            project = summary.project
            if project.id is None or project.id == exclude_pid or project.status == ARCHIVED:
                continue
            seconds = parked.get(project.id)
            label = f"{project.name} · {format_duration(seconds)} parked" if seconds else project.name
            targets.append((project.id, label))
        return targets

    def _keyboard_free(self) -> bool:
        try:
            focused = self.focus_get()
        except Exception:
            return False
        return not is_typing_widget(focused)

    def _on_space_key(self, _event=None) -> str:
        if isinstance(self._view, TimerView) and self._keyboard_free():
            self._view.handle_space()
        return "break"

    def _on_escape_key(self, _event=None) -> str:
        if isinstance(self._view, TimerView) and self._keyboard_free():
            self._view.handle_escape()
        return "break"

    def _quick_switch(self, project_id: int) -> None:
        self._sessions.switch_to(project_id)
        self._enter_timer(project_id, start_session=False)

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
        if self._tray.open_requested.is_set():
            self._tray.open_requested.clear()
            self._restore_from_tray()
        if self._tray.quit_requested.is_set():
            self._tray.quit_requested.clear()
            self._quit_from_tray = True
            self._on_close()
            return
        if self._tray.mini_requested.is_set():
            self._tray.mini_requested.clear()
            self._toggle_mini()
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
        self._update_tray_tooltip()
        self._refresh_mini()
        self._schedule_tick()

    def _schedule_tick(self) -> None:
        self._tick_job = self.after(TICK_MS, self._tick)

    def _handle_completion(self) -> None:
        if self._timer.mode is TimerMode.WORK and self._sessions.has_active:
            finished = self._sessions.complete()
            if self._mini_view is not None and self._mini_view.winfo_exists():
                if finished.project_id is not None:
                    self._mini_pending_project = finished.project_id
                self._stop_alerts()
                self._mini_view.show_completion(
                    format_duration(finished.duration or 0),
                    on_log=lambda s=finished: self._mini_log(s),
                    on_skip=lambda s=finished: self._mini_skip(s),
                )
            elif isinstance(self._view, TimerView):
                self._view.show_review(finished)
        else:
            if self._mini_view is not None and self._mini_view.winfo_exists():
                self._stop_alerts()
                self._mini_view.show_break(
                    "Ready?",
                    on_start=self._mini_break_done,
                )
            elif isinstance(self._view, TimerView):
                if self._auto_start_enabled():
                    self._view.auto_restart()
                else:
                    self._view.break_finished()

    def _auto_start_enabled(self) -> bool:
        try:
            return self._settings.load().auto_start_after_break
        except Exception:
            return False

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
        if self._mini_view is not None:
            self._close_mini()
            return
        if self._quit_from_tray:
            self._real_close()
            return
        try:
            close_to_tray = self._settings.load().close_to_tray
        except Exception:
            close_to_tray = True
        if close_to_tray and self._tray.available:
            self.withdraw()
            self._update_tray_tooltip()
            return
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
        self._real_close()

    def _real_close(self) -> None:
        self._tray.stop()
        if self._tick_job is not None:
            self.after_cancel(self._tick_job)
            self._tick_job = None
        self._stop_alerts()
        if self._sessions.has_active:
            self._sessions.tick_flush()
        try:
            self._settings.set_str("window_geometry", self.geometry())
        except Exception:
            pass
        self._db.close()
        self.destroy()

    def _force_quit(self) -> None:
        if self._mini_view is not None:
            self._close_mini()
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
        self._real_close()

    def _restore_from_tray(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self._stop_alerts()

    def _update_tray_tooltip(self) -> None:
        active = self._sessions.active
        is_running = active is not None and self._timer.is_running
        if active is not None and self._timer.is_running:
            name = self._resolve_project_name(active.project_id)
            self._tray.update_tooltip(f"{format_clock(self._timer.remaining())} · {name}")
        else:
            self._tray.update_tooltip(APP_NAME)
        self._tray.update_icon(is_running)


def main(db_path=None, *, on_already_running=None) -> None:
    path = Path(db_path) if db_path is not None else default_db_path()
    handler = on_already_running or _show_already_running
    if not acquire_instance_lock(path):
        handler()
        return
    try:
        ctk.deactivate_automatic_dpi_awareness()
    except Exception:
        pass
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)
    try:
        from customtkinter.windows.widgets.core_rendering import DrawEngine

        DrawEngine.preferred_drawing_method = "circle_shapes"
    except Exception:
        pass
    app = ChromodoroApp(db_path=db_path)
    app.mainloop()


def _show_already_running() -> None:
    try:
        probe = ctk.CTk()
        probe.withdraw()
        messagebox.showinfo(
            APP_NAME,
            "Chromodoro is already running for this data.\n\n"
            "Use the existing window and Quick Switch between projects.",
            parent=probe,
        )
        probe.destroy()
    except Exception:
        pass
