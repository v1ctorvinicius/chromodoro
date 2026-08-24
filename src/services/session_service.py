from collections.abc import Callable
from datetime import datetime

from domain.contribution import Contribution
from domain.session import Session, SessionStatus
from domain.settings import AppSettings
from services.settings_service import SettingsService
from services.timer_service import TimerMode, TimerService, TimerState
from storage.database import Database


class SessionError(RuntimeError):
    pass


class SessionService:
    def __init__(
        self,
        db: Database,
        timer: TimerService,
        settings: SettingsService,
        now_fn: Callable[[], datetime] = datetime.now,
    ):
        self._db = db
        self._timer = timer
        self._settings = settings
        self._now_fn = now_fn
        self.active: Session | None = None

    @property
    def has_active(self) -> bool:
        return self.active is not None

    @property
    def timer(self) -> TimerService:
        return self._timer

    @property
    def config(self) -> AppSettings:
        return self._settings.load()

    @property
    def completed_cycles(self) -> int:
        return self._settings.completed_cycles

    def start(self, project_id: int) -> Session:
        self._require_no_active("A session is already active")
        now = self._now_fn()
        session = Session(project_id=project_id, started_at=now, running_since=now)
        session.id = self._db.insert_session(session)
        self.active = session
        self._timer.start(self.config.work_minutes * 60, TimerMode.WORK)
        self._flush()
        return session

    def peek_break_seconds(self) -> float:
        if self._settings.completed_cycles >= self.config.cycles_before_long_break:
            return self.config.long_break_minutes * 60
        return self.config.break_minutes * 60

    def start_break(self) -> float:
        if self._settings.completed_cycles >= self.config.cycles_before_long_break:
            self._settings.reset_cycle()
            return self.config.long_break_minutes * 60
        return self.config.break_minutes * 60

    def pause(self) -> None:
        self._require_active()
        self._timer.pause()
        self._flush()

    def resume(self) -> None:
        self._require_active()
        self._timer.resume()
        self._flush()

    def complete(self) -> Session:
        self._require_active()
        session = self._finalize(SessionStatus.COMPLETED)
        self._settings.bump_cycle()
        return session

    def register_interrupted(self) -> Session:
        self._require_active()
        return self._finalize(SessionStatus.INTERRUPTED)

    def discard(self) -> Session:
        self._require_active()
        return self._finalize(SessionStatus.CANCELLED)

    def tick_flush(self) -> None:
        if self.active is None:
            return
        if self._timer.state in (TimerState.RUNNING, TimerState.PAUSED):
            self._flush()

    def recover_pending(self) -> list[tuple[Session, float]]:
        now = self._now_fn()
        return [(session, session.work_seconds(now)) for session in self._db.list_running_sessions()]

    def resolve_stale(self, session: Session, status: SessionStatus) -> None:
        now = self._now_fn()
        duration = session.work_seconds(now)
        assert session.id is not None
        self._db.finish_session(session.id, duration, session.pause_duration, now, status)

    def adopt(self, session: Session) -> Session:
        self._require_no_active("Another session is already active")
        self._timer.adopt(
            target_seconds=self.config.work_minutes * 60,
            elapsed_base=session.duration,
            pause_seconds=session.pause_duration,
            segment_start=session.running_since,
        )
        self.active = session
        self._flush()
        return session

    def add_contribution(self, session: Session, title: str, ctype: str | None = None) -> Contribution:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("Contribution title must not be empty")
        contribution = Contribution(
            project_id=session.project_id,
            session_id=session.id,
            created_at=self._now_fn(),
            title=cleaned,
            type=ctype,
        )
        contribution.id = self._db.insert_contribution(contribution)
        return contribution

    def _finalize(self, status: SessionStatus) -> Session:
        session = self.active
        assert session is not None
        assert session.id is not None
        now = self._now_fn()
        duration = self._timer.elapsed()
        pauses = self._timer.pause_seconds()
        self._db.finish_session(session.id, duration, pauses, now, status)
        session.duration = duration
        session.pause_duration = pauses
        session.ended_at = now
        session.status = status
        session.running_since = None
        self.active = None
        self._timer.cancel()
        return session

    def _flush(self) -> None:
        session = self.active
        if session is None or session.id is None:
            return
        running_since = self._now_fn() if self._timer.state is TimerState.RUNNING else None
        self._db.save_progress(session.id, self._timer.elapsed(), self._timer.pause_seconds(), running_since)

    def _require_active(self) -> None:
        if self.active is None:
            raise SessionError("No active session")

    def _require_no_active(self, message: str) -> None:
        if self.active is not None:
            raise SessionError(message)
