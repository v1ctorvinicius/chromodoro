import csv
from datetime import datetime

from domain.contribution import Contribution
from domain.project import Project
from domain.session import Session, SessionStatus
from storage.database import Database


def _seed(db: Database):
    project = db.insert_project(Project(name="The Signal", description="d"))
    started = datetime.fromisoformat("2026-08-20T09:00:00")
    ended = datetime.fromisoformat("2026-08-20T09:26:00")
    session_id = db.insert_session(
        Session(
            project_id=project.id,
            started_at=started,
            duration=1500.0,
            pause_duration=60.0,
            status=SessionStatus.COMPLETED,
            ended_at=ended,
        )
    )
    db.insert_contribution(
        Contribution(
            project_id=project.id,
            session_id=session_id,
            created_at=started,
            title="Implemented map loading",
            type="feature",
        )
    )
    return project


def test_export_sessions_csv_writes_rows(db, tmp_path):
    _seed(db)
    path = tmp_path / "sessions.csv"

    count = db.export_sessions_csv(path)

    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    assert count == 1
    assert rows[0] == ["started_at", "ended_at", "minutes", "pause_minutes", "status", "project"]
    assert rows[1][2] == "25.0"
    assert rows[1][4] == "completed"
    assert rows[1][5] == "The Signal"


def test_export_contributions_csv_writes_rows(db, tmp_path):
    _seed(db)
    path = tmp_path / "contributions.csv"

    count = db.export_contributions_csv(path)

    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    assert count == 1
    assert rows[0] == ["created_at", "project", "title", "type"]
    assert rows[1][1] == "The Signal"
    assert rows[1][2] == "Implemented map loading"


def test_backup_creates_independent_database(db, tmp_path):
    _seed(db)
    backup_path = tmp_path / "backup.db"

    db.backup_to(backup_path)

    replica = Database(backup_path)
    try:
        projects = replica.list_projects()
        assert len(projects) == 1
        assert projects[0].name == "The Signal"
        assert len(replica.list_sessions(projects[0].id)) == 1
    finally:
        replica.close()


def test_backup_overwrites_existing_file(db, tmp_path):
    path = tmp_path / "backup.db"
    path.write_text("stale")
    db.set_setting("key", "value")

    db.backup_to(path)

    replica = Database(path)
    try:
        assert replica.get_setting("key") == "value"
    finally:
        replica.close()
