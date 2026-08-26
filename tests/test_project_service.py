from datetime import timedelta

import pytest

from domain.contribution import Contribution
from domain.session import Session, SessionStatus
from services.project_service import ProjectService
from storage.database import Database


def make_projects(database: Database, clock):
    return ProjectService(database, now_fn=clock.now)


def add_session(database: Database, project_id: int, started, duration: float, status: SessionStatus):
    return database.insert_session(
        Session(project_id=project_id, started_at=started, duration=duration, status=status)
    )


def test_create_project_strips_and_validates(clock, db):
    projects = make_projects(db, clock)
    project = projects.create_project("  The Signal  ", " A horror game ")
    assert project.name == "The Signal"
    assert project.description == "A horror game"
    with pytest.raises(ValueError):
        projects.create_project("   ")


def test_summaries_order_by_recent_activity(clock, db):
    services = make_projects(db, clock)
    old = services.create_project("Old")
    new = services.create_project("New")

    add_session(db, old.id, clock.now().replace(hour=1), 600.0, SessionStatus.COMPLETED)
    add_session(db, new.id, clock.now().replace(hour=8), 300.0, SessionStatus.COMPLETED)

    summaries = services.list_summaries()
    assert [s.project.name for s in summaries] == ["New", "Old"]
    first = summaries[0]
    assert first.total_seconds == pytest.approx(300.0)
    assert first.session_count == 1


def test_archive_removes_from_summaries_but_keeps_data(clock, db):
    services = make_projects(db, clock)
    project = services.create_project("Done")
    add_session(db, project.id, clock.now(), 900.0, SessionStatus.COMPLETED)

    services.archive_project(project)
    assert services.list_summaries() == []
    stats = services.project_stats(project.id)
    assert stats.total_seconds == pytest.approx(900.0)
    assert db.get_project(project.id) is not None


def test_project_stats_counts_only_counted_sessions(clock, db):
    services = make_projects(db, clock)
    project = services.create_project("P")
    now = clock.now()
    counted = add_session(db, project.id, now.replace(hour=9), 1500.0, SessionStatus.COMPLETED)
    add_session(db, project.id, now.replace(hour=11), 780.0, SessionStatus.INTERRUPTED)
    add_session(db, project.id, now.replace(hour=13), 999.0, SessionStatus.CANCELLED)
    db.insert_contribution(
        Contribution(project_id=project.id, title="C", created_at=now, session_id=counted)
    )
    db.insert_contribution(Contribution(project_id=project.id, title="N", created_at=now))

    stats = services.project_stats(project.id)
    assert stats.total_seconds == pytest.approx(2280.0)
    assert stats.session_count == 2
    assert stats.contribution_count == 1
    assert stats.notes_count == 1
    assert stats.last_activity is not None


def test_contributions_by_session_groups_correctly(clock, db):
    services = make_projects(db, clock)
    project = services.create_project("P")
    now = clock.now()
    session_a = Session(
        project_id=project.id, started_at=now, duration=100.0, status=SessionStatus.COMPLETED
    )
    session_a.id = db.insert_session(session_a)

    db.insert_contribution(
        Contribution(project_id=project.id, session_id=session_a.id, title="A", created_at=now)
    )
    db.insert_contribution(Contribution(project_id=project.id, session_id=None, title="B", created_at=now))

    grouped = services.contributions_by_session(project.id)
    assert [c.title for c in grouped[session_a.id]] == ["A"]
    assert [c.title for c in grouped[None]] == ["B"]


def test_global_totals_split_today_and_week(clock, db):
    services = make_projects(db, clock)
    project = services.create_project("P")
    base = clock.now()

    add_session(db, project.id, base - timedelta(days=3), 1200.0, SessionStatus.COMPLETED)
    add_session(db, project.id, base - timedelta(days=10), 5000.0, SessionStatus.COMPLETED)
    today_start = base.replace(hour=0, minute=0, second=0, microsecond=0)
    add_session(db, project.id, today_start + timedelta(hours=1), 600.0, SessionStatus.INTERRUPTED)

    today_seconds, week_seconds = services.global_totals()
    assert today_seconds == pytest.approx(600.0)
    assert week_seconds == pytest.approx(1800.0)


def test_update_project_fields(clock, db):
    services = make_projects(db, clock)
    project = services.create_project("Draft", "")
    updated = services.update_project(project, "Renamed", "Now with description")
    stored = db.get_project(updated.id)
    assert stored.name == "Renamed"
    assert stored.description == "Now with description"



def _goal_service(database, clock):
    from services.project_service import ProjectService

    return ProjectService(database, now_fn=clock.now)


def test_create_project_with_daily_goal(clock, db):
    service = _goal_service(db, clock)

    project = service.create_project("Thesis", daily_goal_minutes=90)

    stored = db.get_project(project.id)
    assert stored.daily_goal_minutes == 90.0


def test_daily_goal_defaults_to_zero_and_clamps(clock, db):
    service = _goal_service(db, clock)

    plain = service.create_project("Plain")
    huge = service.create_project("Huge", daily_goal_minutes=99999)
    negative = service.create_project("Negative", daily_goal_minutes=-5)

    assert plain.daily_goal_minutes == 0.0
    assert huge.daily_goal_minutes == 1440.0
    assert negative.daily_goal_minutes == 0.0


def test_update_project_changes_goal_only_when_provided(clock, db):
    service = _goal_service(db, clock)
    project = service.create_project("Thesis", daily_goal_minutes=60)

    service.update_project(project, "Thesis v2", "new text", daily_goal_minutes=120)
    assert service.get_project(project.id).daily_goal_minutes == 120.0

    service.update_project(project, "Thesis v3", "newer")
    kept = service.get_project(project.id)
    assert kept.name == "Thesis v3"
    assert kept.daily_goal_minutes == 120.0


def test_summary_includes_today_seconds_and_goal(clock, db):
    from domain.session import Session, SessionStatus

    service = _goal_service(db, clock)
    project = service.create_project("Thesis", daily_goal_minutes=60)
    now = clock.now()
    db.insert_session(
        Session(
            project_id=project.id,
            started_at=now,
            duration=1800.0,
            status=SessionStatus.COMPLETED,
        )
    )
    yesterday = now.replace(day=now.day - 1)
    db.insert_session(
        Session(
            project_id=project.id,
            started_at=yesterday,
            duration=3600.0,
            status=SessionStatus.COMPLETED,
        )
    )

    summaries = {s.project.id: s for s in service.list_summaries()}
    summary = summaries[project.id]
    assert summary.today_seconds == 1800.0
    assert summary.total_seconds == 5400.0
    assert summary.project.daily_goal_minutes == 60.0


def test_summary_today_ignores_running_sessions(clock, db):
    from domain.session import Session

    service = _goal_service(db, clock)
    project = service.create_project("Live")
    db.insert_session(Session(project_id=project.id, started_at=clock.now(), duration=999.0))

    summary = service.list_summaries()[0]
    assert summary.today_seconds == 0.0


def add_contribution(database: Database, project_id: int, title: str, created):
    contribution = Contribution(project_id=project_id, title=title, created_at=created)
    contribution.id = database.insert_contribution(contribution)
    return contribution


def test_update_contribution_validates_and_persists(clock, db):
    projects = make_projects(db, clock)
    project = projects.create_project("Alpha")
    contribution = add_contribution(db, project.id, "First draft", clock.now())

    with pytest.raises(ValueError):
        projects.update_contribution(contribution.id, "   ")

    projects.update_contribution(contribution.id, "Polished draft")

    stored = db.list_contributions(project.id)[0]
    assert stored.title == "Polished draft"
    assert stored.id == contribution.id


def test_delete_contribution_removes_only_target(clock, db):
    projects = make_projects(db, clock)
    project = projects.create_project("Alpha")
    keep = add_contribution(db, project.id, "Keep me", clock.now())
    drop = add_contribution(db, project.id, "Drop me", clock.now())

    projects.delete_contribution(drop.id)

    remaining = db.list_contributions(project.id)
    assert [c.title for c in remaining] == ["Keep me"]
    assert remaining[0].id == keep.id


def test_add_note_persists_without_session(clock, db):
    projects = make_projects(db, clock)
    project = projects.create_project("Alpha")

    note = projects.add_note(project.id, "  Idea captured mid-day  ")

    assert note.id is not None
    stored = db.list_contributions(project.id)[0]
    assert stored.title == "Idea captured mid-day"
    assert stored.session_id is None

    grouped = projects.contributions_by_session(project.id)
    assert "Idea captured mid-day" in [c.title for c in grouped[None]]


def test_add_note_rejects_empty(clock, db):
    projects = make_projects(db, clock)
    project = projects.create_project("Alpha")
    with pytest.raises(ValueError):
        projects.add_note(project.id, "   ")
