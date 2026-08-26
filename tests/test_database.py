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
    assert database.count_contributions(project.id) == 0
    assert database.count_notes(project.id) == 5
    database.close()


def test_summary_rows_expose_counts(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    now = datetime(2026, 8, 20, 9, 0, 0)
    session_id = database.insert_session(
        Session(project_id=project.id, started_at=now, duration=600.0, status=SessionStatus.COMPLETED)
    )
    database.insert_session(
        Session(project_id=project.id, started_at=now, duration=500.0, status=SessionStatus.CANCELLED)
    )
    database.insert_contribution(
        Contribution(project_id=project.id, title="C", created_at=now, session_id=session_id)
    )
    database.insert_contribution(Contribution(project_id=project.id, title="N", created_at=now))

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


def test_parked_summaries_latest_per_project(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    alpha = database.insert_project(Project(name="Alpha"))
    beta = database.insert_project(Project(name="Beta"))
    now = datetime(2026, 8, 24, 9, 0, 0)

    first = Session(project_id=alpha.id, started_at=now, duration=60.0)
    first.id = database.insert_session(first)
    second = Session(project_id=alpha.id, started_at=now, duration=180.0)
    second.id = database.insert_session(second)
    beta_parked = Session(
        project_id=beta.id, started_at=now, duration=240.0, running_since=None
    )
    beta_parked.id = database.insert_session(beta_parked)

    parked = database.parked_summaries()

    assert parked[alpha.id] == pytest.approx(180.0)
    assert parked[beta.id] == pytest.approx(240.0)
    assert database.get_session(first.id).running_since is None
    database.close()


def test_project_seconds_since_filters_project_and_boundary(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    alpha = database.insert_project(Project(name="Alpha"))
    beta = database.insert_project(Project(name="Beta"))
    boundary = datetime(2026, 8, 20, 0, 0, 0)

    database.insert_session(
        Session(
            project_id=alpha.id,
            started_at=datetime(2026, 8, 21, 9, 0, 0),
            duration=300.0,
            status=SessionStatus.COMPLETED,
        )
    )
    database.insert_session(
        Session(
            project_id=alpha.id,
            started_at=datetime(2026, 8, 19, 9, 0, 0),
            duration=999.0,
            status=SessionStatus.COMPLETED,
        )
    )
    database.insert_session(
        Session(
            project_id=beta.id,
            started_at=datetime(2026, 8, 21, 10, 0, 0),
            duration=700.0,
            status=SessionStatus.COMPLETED,
        )
    )

    assert database.project_seconds_since(alpha.id, boundary) == pytest.approx(300.0)
    assert database.project_seconds_since(beta.id, boundary) == pytest.approx(700.0)
    database.close()


def test_update_and_delete_contribution(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    created = datetime(2026, 8, 24, 10, 0, 0)
    contribution = Contribution(project_id=project.id, title="First draft", created_at=created)
    contribution.id = database.insert_contribution(contribution)

    database.update_contribution(contribution.id, "Polished draft")
    stored = database.list_contributions(project.id)[0]
    assert stored.title == "Polished draft"

    database.delete_contribution(contribution.id)
    assert database.list_contributions(project.id) == []
    database.close()


def test_notes_are_separated_from_contributions(tmp_path):
    from storage.database import Database

    database = Database(tmp_path / "a.db")
    project = database.insert_project(Project(name="P"))
    started = datetime(2026, 8, 24, 9, 0, 0)
    session_id = database.insert_session(
        Session(project_id=project.id, started_at=started)
    )
    real = Contribution(
        project_id=project.id, title="From session", created_at=started, session_id=session_id
    )
    database.insert_contribution(real)
    note = Contribution(project_id=project.id, title="Standalone note", created_at=started)
    database.insert_contribution(note)

    assert [n.title for n in database.list_notes(project.id)] == ["Standalone note"]
    assert database.count_notes(project.id) == 1
    assert database.count_contributions(project.id) == 1
    grouped = database.contributions_by_session(project.id)
    assert [c.title for c in grouped[session_id]] == ["From session"]
    database.close()
