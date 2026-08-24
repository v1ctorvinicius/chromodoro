import sqlite3

from storage.database import _MIGRATIONS, Database


def test_fresh_database_is_at_latest_migration(db):
    assert db.schema_version == max(_MIGRATIONS)


def test_legacy_database_without_user_version_upgrades(tmp_path):
    legacy_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy_path)
    conn.executescript(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        );
        INSERT INTO projects (name, created_at) VALUES ('Legacy', '2026-01-01T08:00:00');
        """
    )
    conn.commit()
    conn.close()

    database = Database(legacy_path)
    try:
        assert database.schema_version == max(_MIGRATIONS)
        project = database.get_project(1)
        assert project is not None
        assert project.name == "Legacy"
        assert project.daily_goal_minutes == 0.0
    finally:
        database.close()


def test_reopening_database_does_not_reapply_migrations(db, tmp_path):
    db.set_setting("marker", "kept")
    path = db.path
    db.close()

    reopened = Database(path)
    try:
        assert reopened.schema_version == max(_MIGRATIONS)
        assert reopened.get_setting("marker") == "kept"
    finally:
        reopened.close()
