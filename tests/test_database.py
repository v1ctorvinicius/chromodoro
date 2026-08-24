from datetime import datetime

import pytest

from domain.contribution import Contribution
from domain.project import Project
from domain.session import Session, SessionStatus


def test_project_roundtrip(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    created = database.insert_project(Project(name="FetOS", description="An OS"))
    fetched = database.get_project(created.id)
    assert fetched.name == "FetOS"
    assert fetched.description == "An OS"
    assert fetched.created_at is not None
    database.close()


def test_session_roundtrip_and_progress(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    start = datetime(2026, 8, 20, 14, 0, 0)
    session = Session(project_id=project.id, started_at=start, running_since=start)
    session.id = database.insert_session(session)

    stored = database.get_session(session.id)
    assert stored.status is SessionStatus.RUNNING
    assert stored.started_at == start

    database.save_progress(session.id, 300.0, 20.0, None)
    paused = database.get_session(session.id)
    assert paused.duration == 300.0
    assert paused.pause_duration == 20.0
    assert paused.running_since is None

    ended = start.replace(hour=15)
    database.finish_session(session.id, 1500.0, 60.0, ended, SessionStatus.COMPLETED)
    done = database.get_session(session.id)
    assert done.status is SessionStatus.COMPLETED
    assert done.ended_at == ended
    database.close()


def test_list_running_sessions_filters_correctly(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    now = datetime(2026, 8, 21, 10, 0, 0)

    running = Session(project_id=project.id, started_at=now, running_since=now)
    running.id = database.insert_session(running)
    done = Session(
        project_id=project.id,
        started_at=now,
        status=SessionStatus.COMPLETED,
        duration=100.0,
    )
    database.insert_session(done)

    pending = database.list_running_sessions()
    assert [s.id for s in pending] == [running.id]
    database.close()


def test_contribution_insert_and_listing_with_limit(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    for index in range(5):
        contribution = Contribution(
            project_id=project.id,
            title=f"Thing {index}",
            created_at=datetime(2026, 8, 20, 12, index),
        )
        database.insert_contribution(contribution)

    all_items = database.list_contributions(project.id)
    limited = database.list_contributions(project.id, limit=2)
    assert len(all_items) == 5
    assert [c.title for c in limited] == ["Thing 4", "Thing 3"]
    assert database.count_contributions(project.id) == 5
    database.close()


def test_summary_rows_expose_counts(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    now = datetime(2026, 8, 20, 9, 0, 0)
    database.insert_session(
        Session(project_id=project.id, started_at=now, duration=600.0, status=SessionStatus.COMPLETED)
    )
    database.insert_session(
        Session(project_id=project.id, started_at=now, duration=500.0, status=SessionStatus.CANCELLED)
    )
    database.insert_contribution(Contribution(project_id=project.id, title="C", created_at=now))

    rows = database.project_summary_rows("active", datetime(2026, 8, 20, 0, 0, 0))
    assert len(rows) == 1
    row = rows[0]
    assert row["total_seconds"] == pytest.approx(600.0)
    assert row["session_count"] == 1
    assert row["contribution_count"] == 1
    assert row["last_activity"] is not None


def test_work_seconds_since_ignores_cancelled(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    boundary = datetime(2026, 8, 20, 0, 0, 0)
    database.insert_session(
        Session(
            project_id=project.id,
            started_at=datetime(2026, 8, 21, 9, 0, 0),
            duration=300.0,
            status=SessionStatus.INTERRUPTED,
        )
    )
    database.insert_session(
        Session(
            project_id=project.id,
            started_at=datetime(2026, 8, 22, 9, 0, 0),
            duration=900.0,
            status=SessionStatus.CANCELLED,
        )
    )

    total = database.work_seconds_since(boundary)
    assert total == pytest.approx(300.0)
    database.close()
