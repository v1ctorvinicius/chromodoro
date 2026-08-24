import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from domain.contribution import Contribution
from domain.project import Project
from domain.session import Session, SessionStatus

_COUNTED = "('completed', 'interrupted')"

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration REAL NOT NULL DEFAULT 0,
    pause_duration REAL NOT NULL DEFAULT 0,
    running_since TEXT,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT
);
"""

_MIGRATIONS: dict[int, str] = {
    1: _SCHEMA_V1,
    2: """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
""",
    3: "ALTER TABLE projects ADD COLUMN daily_goal_minutes REAL NOT NULL DEFAULT 0;",
}


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    try:
        roots.append(Path(__file__).resolve().parents[2])
    except IndexError:
        pass
    return roots


def portable_data_dir() -> Path | None:
    for root in candidate_roots():
        data_dir = root / "data"
        if data_dir.is_dir():
            return data_dir
    return None


def default_db_path() -> Path:
    override = os.environ.get("CHROMODORO_DB")
    if override:
        return Path(override)
    portable = portable_data_dir()
    if portable is not None:
        return portable / "chromodoro.db"
    base = os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "Chromodoro"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "chromodoro.db"


def _to_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _to_dt_required(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def _to_int(row_value: int | None) -> int:
    assert row_value is not None
    return row_value


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=_to_int(row["id"]),
        name=row["name"],
        description=row["description"],
        status=row["status"],
        created_at=_to_dt_required(row["created_at"]),
        daily_goal_minutes=float(row["daily_goal_minutes"]),
    )


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=_to_int(row["id"]),
        project_id=_to_int(row["project_id"]),
        started_at=_to_dt_required(row["started_at"]),
        ended_at=_to_dt(row["ended_at"]),
        duration=row["duration"],
        pause_duration=row["pause_duration"],
        status=SessionStatus(row["status"]),
        running_since=_to_dt(row["running_since"]),
    )


def _row_to_contribution(row: sqlite3.Row) -> Contribution:
    return Contribution(
        id=_to_int(row["id"]),
        project_id=_to_int(row["project_id"]),
        session_id=_to_int(row["session_id"]) if row["session_id"] is not None else None,
        created_at=_to_dt_required(row["created_at"]),
        title=row["title"],
        type=row["type"],
    )


class Database:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_db_path()
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def _migrate(self) -> None:
        current = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        for version in sorted(_MIGRATIONS):
            if version <= current:
                continue
            self._conn.executescript(_MIGRATIONS[version])
            self._conn.execute(f"PRAGMA user_version = {version}")
            self._conn.commit()

    @property
    def schema_version(self) -> int:
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def close(self) -> None:
        self._conn.close()

    def get_setting(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def insert_project(self, project: Project) -> Project:
        now = _to_str(project.created_at) or datetime.now().isoformat(timespec="seconds")
        cur = self._conn.execute(
            "INSERT INTO projects (name, description, status, created_at, daily_goal_minutes)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                project.name,
                project.description,
                project.status,
                now,
                project.daily_goal_minutes,
            ),
        )
        self._conn.commit()
        assert cur.lastrowid is not None
        project.id = int(cur.lastrowid)
        project.created_at = datetime.fromisoformat(now)
        return project

    def get_project(self, project_id: int) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _row_to_project(row) if row else None

    def update_project(self, project: Project) -> None:
        self._conn.execute(
            "UPDATE projects SET name = ?, description = ?, status = ?, daily_goal_minutes = ? WHERE id = ?",
            (project.name, project.description, project.status, project.daily_goal_minutes, project.id),
        )
        self._conn.commit()

    def list_projects(self, status: str | None = None) -> list[Project]:
        if status is None:
            rows = self._conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
        return [_row_to_project(r) for r in rows]

    def insert_session(self, session: Session) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (project_id, started_at, ended_at, duration,"
            " pause_duration, running_since, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session.project_id,
                _to_str(session.started_at),
                _to_str(session.ended_at),
                session.duration,
                session.pause_duration,
                _to_str(session.running_since),
                session.status.value,
            ),
        )
        self._conn.commit()
        assert cur.lastrowid is not None
        return int(cur.lastrowid)

    def get_session(self, session_id: int) -> Session | None:
        row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _row_to_session(row) if row else None

    def save_progress(
        self,
        session_id: int,
        duration: float,
        pause_duration: float,
        running_since: datetime | None,
    ) -> None:
        self._conn.execute(
            "UPDATE sessions SET duration = ?, pause_duration = ?, running_since = ? WHERE id = ?",
            (duration, pause_duration, _to_str(running_since), session_id),
        )
        self._conn.commit()

    def finish_session(
        self,
        session_id: int,
        duration: float,
        pause_duration: float,
        ended_at: datetime,
        status: SessionStatus,
    ) -> None:
        self._conn.execute(
            "UPDATE sessions SET duration = ?, pause_duration = ?, ended_at = ?,"
            " running_since = NULL, status = ?"
            " WHERE id = ?",
            (duration, pause_duration, _to_str(ended_at), status.value, session_id),
        )
        self._conn.commit()

    def list_sessions(self, project_id: int) -> list[Session]:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE project_id = ? ORDER BY started_at DESC, id DESC",
            (project_id,),
        ).fetchall()
        return [_row_to_session(r) for r in rows]

    def list_running_sessions(self) -> list[Session]:
        rows = self._conn.execute("SELECT * FROM sessions WHERE status = 'running' ORDER BY id").fetchall()
        return [_row_to_session(r) for r in rows]

    def work_seconds_since(self, boundary: datetime) -> float:
        row = self._conn.execute(
            f"SELECT COALESCE(SUM(duration), 0) AS total FROM sessions"
            f" WHERE status IN {_COUNTED} AND started_at >= ?",
            (_to_str(boundary),),
        ).fetchone()
        return float(row["total"])

    def insert_contribution(self, contribution: Contribution) -> int:
        created = _to_str(contribution.created_at) or datetime.now().isoformat(timespec="seconds")
        cur = self._conn.execute(
            "INSERT INTO contributions (project_id, session_id, created_at, title, type)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                contribution.project_id,
                contribution.session_id,
                created,
                contribution.title,
                contribution.type,
            ),
        )
        self._conn.commit()
        assert cur.lastrowid is not None
        return int(cur.lastrowid)

    def list_contributions(self, project_id: int, limit: int | None = None) -> list[Contribution]:
        query = "SELECT * FROM contributions WHERE project_id = ? ORDER BY created_at DESC, id DESC"
        params: tuple = (project_id,)
        if limit is not None:
            query += " LIMIT ?"
            params = (project_id, limit)
        rows = self._conn.execute(query, params).fetchall()
        return [_row_to_contribution(r) for r in rows]

    def count_contributions(self, project_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS total FROM contributions WHERE project_id = ?", (project_id,)
        ).fetchone()
        return int(row["total"])

    def contributions_by_session(self, project_id: int) -> dict[int | None, list[Contribution]]:
        grouped: dict[int | None, list[Contribution]] = {}
        for c in self.list_contributions(project_id):
            grouped.setdefault(c.session_id, []).append(c)
        return grouped

    def project_summary_rows(self, status: str, today_boundary: datetime) -> list[sqlite3.Row]:
        return self._conn.execute(
            f"SELECT p.id, p.name, p.description, p.status, p.created_at, p.daily_goal_minutes,"
            f" COALESCE(agg.total_seconds, 0) AS total_seconds,"
            f" COALESCE(agg.session_count, 0) AS session_count,"
            f" (SELECT COUNT(*) FROM contributions c WHERE c.project_id = p.id) AS contribution_count,"
            f" COALESCE((SELECT SUM(s.duration) FROM sessions s"
            f"   WHERE s.project_id = p.id AND s.status IN {_COUNTED} AND s.started_at >= ?), 0)"
            f"   AS today_seconds,"
            f" agg.last_activity AS last_activity"
            f" FROM projects p"
            f" LEFT JOIN ("
            f"   SELECT project_id, SUM(duration) AS total_seconds, COUNT(*) AS session_count,"
            f"          MAX(started_at) AS last_activity"
            f"   FROM sessions WHERE status IN {_COUNTED} GROUP BY project_id"
            f" ) agg ON agg.project_id = p.id"
            f" WHERE p.status = ?"
            f" ORDER BY (agg.last_activity IS NULL), agg.last_activity DESC, p.name COLLATE NOCASE",
            (_to_str(today_boundary), status),
        ).fetchall()

    def project_stats_row(self, project_id: int) -> sqlite3.Row:
        return self._conn.execute(
            f"SELECT COALESCE(SUM(CASE WHEN status IN {_COUNTED} THEN duration ELSE 0 END), 0)"
            f" AS total_seconds,"
            f" COUNT(CASE WHEN status IN {_COUNTED} THEN 1 END) AS session_count,"
            f" MAX(started_at) AS last_activity"
            f" FROM sessions WHERE project_id = ?",
            (project_id,),
        ).fetchone()

    def export_sessions_csv(self, path: Path) -> int:
        import csv

        rows = self._conn.execute(
            "SELECT s.started_at, s.ended_at, s.duration, s.pause_duration, s.status, p.name AS project"
            " FROM sessions s JOIN projects p ON p.id = s.project_id"
            " ORDER BY s.started_at, s.id"
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["started_at", "ended_at", "minutes", "pause_minutes", "status", "project"]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["started_at"],
                        row["ended_at"] or "",
                        round(float(row["duration"]) / 60.0, 2),
                        round(float(row["pause_duration"]) / 60.0, 2),
                        row["status"],
                        row["project"],
                    ]
                )
        return len(rows)

    def export_contributions_csv(self, path: Path) -> int:
        import csv

        rows = self._conn.execute(
            "SELECT c.created_at, c.title, c.type, p.name AS project"
            " FROM contributions c JOIN projects p ON p.id = c.project_id"
            " ORDER BY c.created_at, c.id"
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["created_at", "project", "title", "type"])
            for row in rows:
                writer.writerow([row["created_at"], row["project"], row["title"], row["type"] or ""])
        return len(rows)

    def backup_to(self, path: Path) -> None:
        if path.exists():
            path.unlink()
        self._conn.execute("VACUUM INTO ?", (str(path),))
        self._conn.commit()
