import pytest

from domain.project import Project
from domain.settings import AppSettings
from services.session_service import SessionError, SessionService
from services.settings_service import SettingsService
from services.timer_service import TimerService
from storage.database import Database


def make_service(database: Database, clock, settings: AppSettings | None = None) -> SessionService:
    timer = TimerService(now_fn=clock.now)
    service_settings = SettingsService(database)
    if settings is not None:
        service_settings.save(settings)
    return SessionService(database, timer, service_settings, now_fn=clock.now)


def make_project(database: Database, name: str = "The Signal") -> Project:
    return database.insert_project(Project(name=name))


def test_start_creates_running_session(clock, db):
    project = make_project(db)
    service = make_service(db, clock)

    session = service.start(project.id)

    assert service.has_active
    stored = db.get_session(session.id)
    assert stored.status.value == "running"
    assert stored.project_id == project.id
    assert stored.running_since is not None
    assert db.list_sessions(project.id)[0].id == session.id


def test_full_pomodoro_lifecycle(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    session = service.start(project.id)

    clock.advance(600)
    service.pause()
    clock.advance(120)
    service.resume()
    clock.advance(900)

    finished = service.complete()

    assert finished.status.value == "completed"
    assert finished.duration == pytest.approx(1500, abs=2)
    assert finished.pause_duration == pytest.approx(120, abs=2)
    assert finished.ended_at is not None
    assert not service.has_active

    stored = db.get_session(session.id)
    assert stored.status.value == "completed"
    assert stored.duration == pytest.approx(1500, abs=2)
    assert stored.running_since is None


def test_interrupted_session_keeps_partial_time(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    service.start(project.id)
    clock.advance(780)

    finished = service.register_interrupted()

    assert finished.status.value == "interrupted"
    assert finished.duration == pytest.approx(780, abs=2)


def test_discarded_session_is_cancelled(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    service.start(project.id)
    clock.advance(100)

    discarded = service.discard()

    assert discarded.status.value == "cancelled"


def test_contribution_is_linked_to_session(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    session = service.start(project.id)
    clock.advance(1500)

    service.complete()
    service.add_contribution(session, "Implemented map loading")

    stored = db.list_contributions(project.id)
    assert len(stored) == 1
    assert stored[0].session_id == session.id
    assert stored[0].title == "Implemented map loading"


def test_empty_contribution_title_rejected(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    session = service.start(project.id)
    with pytest.raises(ValueError):
        service.add_contribution(session, "   ")


def test_double_start_raises(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    service.start(project.id)
    with pytest.raises(SessionError):
        service.start(project.id)


def test_tick_flush_persists_progress(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    session = service.start(project.id)

    clock.advance(300)
    service.tick_flush()

    stored = db.get_session(session.id)
    assert stored.duration == pytest.approx(300, abs=1)


def test_recovery_of_abandoned_session(clock, db):
    project = make_project(db)
    first = make_service(db, clock)
    abandoned = first.start(project.id)
    clock.advance(500)

    second = make_service(db, clock)
    pending = second.recover_pending()

    assert len(pending) == 1
    recovered, elapsed = pending[0]
    assert recovered.id == abandoned.id
    assert elapsed == pytest.approx(500, abs=1)

    second.adopt(recovered)
    assert second.has_active
    clock.advance(60)
    assert second.timer.elapsed() == pytest.approx(560, abs=2)

    finished = second.complete()
    assert finished.duration == pytest.approx(560, abs=3)


def test_resolve_stale_marks_interrupted_with_elapsed_time(clock, db):
    project = make_project(db)
    first = make_service(db, clock)
    abandoned = first.start(project.id)
    clock.advance(420)

    second = make_service(db, clock)
    from domain.session import SessionStatus

    second.resolve_stale(abandoned, SessionStatus.INTERRUPTED)

    stored = db.get_session(abandoned.id)
    assert stored.status.value == "interrupted"
    assert stored.duration == pytest.approx(420, abs=1)


def test_adopt_paused_session_stays_paused(clock, db):
    project = make_project(db)
    first = make_service(db, clock)
    first.start(project.id)
    clock.advance(200)
    first.pause()
    clock.advance(999)

    second = make_service(db, clock)
    pending = second.recover_pending()
    _, elapsed = pending[0]
    assert elapsed == pytest.approx(200, abs=1)

    second.adopt(pending[0][0])
    assert second.timer.state.value == "paused"


def test_short_break_before_reaching_cycle_threshold(clock, db):
    project = make_project(db)
    settings = AppSettings(break_minutes=5, long_break_minutes=15, cycles_before_long_break=2)
    service = make_service(db, clock, settings)

    assert service.completed_cycles == 0
    assert service.peek_break_seconds() == pytest.approx(300)

    service.start(project.id)
    clock.advance(1500)
    service.complete()

    assert service.completed_cycles == 1
    assert service.peek_break_seconds() == pytest.approx(300)
    seconds = service.start_break()
    assert seconds == pytest.approx(300)
    assert service.completed_cycles == 1


def test_long_break_after_threshold_and_counter_reset(clock, db):
    project = make_project(db)
    settings = AppSettings(break_minutes=5, long_break_minutes=15, cycles_before_long_break=2)
    service = make_service(db, clock, settings)

    for _ in range(2):
        service.start(project.id)
        clock.advance(1500)
        service.complete()

    assert service.completed_cycles == 2
    assert service.peek_break_seconds() == pytest.approx(900)

    seconds = service.start_break()
    assert seconds == pytest.approx(900)
    assert service.completed_cycles == 0
    assert service.peek_break_seconds() == pytest.approx(300)


def test_interrupted_session_does_not_count_toward_long_break(clock, db):
    project = make_project(db)
    settings = AppSettings(cycles_before_long_break=1)
    service = make_service(db, clock, settings)

    service.start(project.id)
    clock.advance(600)
    service.register_interrupted()

    assert service.completed_cycles == 0
    assert service.peek_break_seconds() != pytest.approx(service.config.long_break_minutes * 60)


def test_switch_parks_current_and_starts_target(clock, db):
    alpha = make_project(db, "Alpha")
    beta = make_project(db, "Beta")
    service = make_service(db, clock)
    first = service.start(alpha.id)
    clock.advance(300)

    switched = service.switch_to(beta.id)
    assert switched is not None

    assert switched.project_id == beta.id
    assert service.has_active
    assert service.active is not None and service.active.project_id == beta.id
    parked = db.get_session(first.id)
    assert parked.status.value == "running"
    assert parked.running_since is None
    assert parked.duration == pytest.approx(300, abs=1)
    assert service.timer.elapsed() == pytest.approx(0, abs=1)


def test_switch_back_resumes_parked_session(clock, db):
    alpha = make_project(db, "Alpha")
    beta = make_project(db, "Beta")
    service = make_service(db, clock)
    original = service.start(alpha.id)
    clock.advance(300)
    service.switch_to(beta.id)
    clock.advance(100)

    back = service.switch_to(alpha.id)
    assert back is not None

    assert back.id == original.id
    assert service.timer.state.value == "running"
    assert service.timer.elapsed() == pytest.approx(300, abs=2)
    beta_sessions = db.list_sessions(beta.id)
    assert len(beta_sessions) == 1
    assert beta_sessions[0].duration == pytest.approx(100, abs=1)
    assert beta_sessions[0].status.value == "running"


def test_switch_to_same_project_is_noop(clock, db):
    project = make_project(db)
    service = make_service(db, clock)
    started = service.start(project.id)
    clock.advance(60)

    result = service.switch_to(project.id)

    assert result is None
    assert service.active is not None and service.active.id == started.id


def test_switch_without_active_resumes_parked_instead_of_new_session(clock, db):
    alpha = make_project(db, "Alpha")
    service = make_service(db, clock)
    parked_session = service.start(alpha.id)
    clock.advance(200)
    service.park()
    assert not service.has_active

    resumed = service.switch_to(alpha.id)
    assert resumed is not None

    assert resumed.id == parked_session.id
    assert service.timer.state.value == "running"
    assert len(db.list_sessions(alpha.id)) == 1


def test_peek_parked_reports_session_without_disturbing_state(clock, db):
    alpha = make_project(db, "Alpha")
    beta = make_project(db, "Beta")
    service = make_service(db, clock)
    parked_session = service.start(alpha.id)
    clock.advance(120)
    service.park()

    peeked = service.peek_parked(alpha.id)

    assert peeked is not None
    assert peeked.id == parked_session.id
    assert peeked.duration == pytest.approx(120, abs=1)
    assert service.peek_parked(beta.id) is None
    assert not service.has_active
