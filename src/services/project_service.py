from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from domain.contribution import Contribution
from domain.project import ARCHIVED, Project
from domain.session import Session
from storage.database import Database


@dataclass
class ProjectSummary:
    project: Project
    total_seconds: float
    session_count: int
    contribution_count: int
    last_activity: datetime | None
    today_seconds: float = 0.0


@dataclass
class ProjectStats:
    total_seconds: float
    session_count: int
    contribution_count: int
    last_activity: datetime | None


class ProjectService:
    def __init__(self, db: Database, now_fn: Callable[[], datetime] = datetime.now):
        self._db = db
        self._now_fn = now_fn

    def create_project(self, name: str, description: str = "", daily_goal_minutes: float = 0.0) -> Project:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Project name must not be empty")
        project = Project(
            name=cleaned,
            description=description.strip(),
            created_at=self._now_fn(),
            daily_goal_minutes=_clamp_goal(daily_goal_minutes),
        )
        return self._db.insert_project(project)

    def get_project(self, project_id: int) -> Project:
        project = self._db.get_project(project_id)
        if project is None:
            raise KeyError(f"Project {project_id} not found")
        return project

    def update_project(
        self,
        project: Project,
        name: str,
        description: str,
        daily_goal_minutes: float | None = None,
    ) -> Project:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Project name must not be empty")
        project.name = cleaned
        project.description = description.strip()
        if daily_goal_minutes is not None:
            project.daily_goal_minutes = _clamp_goal(daily_goal_minutes)
        self._db.update_project(project)
        return project

    def archive_project(self, project: Project) -> Project:
        project.status = ARCHIVED
        self._db.update_project(project)
        return project

    def list_summaries(self) -> list[ProjectSummary]:
        today = self._now_fn().replace(hour=0, minute=0, second=0, microsecond=0)
        summaries = []
        for row in self._db.project_summary_rows("active", today):
            project = Project(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                status=row["status"],
                created_at=datetime.fromisoformat(row["created_at"]),
                daily_goal_minutes=float(row["daily_goal_minutes"]),
            )
            summaries.append(
                ProjectSummary(
                    project=project,
                    total_seconds=float(row["total_seconds"]),
                    session_count=int(row["session_count"]),
                    contribution_count=int(row["contribution_count"]),
                    last_activity=_parse(row["last_activity"]),
                    today_seconds=float(row["today_seconds"]),
                )
            )
        return summaries

    def project_stats(self, project_id: int) -> ProjectStats:
        row = self._db.project_stats_row(project_id)
        return ProjectStats(
            total_seconds=float(row["total_seconds"]),
            session_count=int(row["session_count"]),
            contribution_count=self._db.count_contributions(project_id),
            last_activity=_parse(row["last_activity"]),
        )

    def sessions(self, project_id: int) -> list[Session]:
        return self._db.list_sessions(project_id)

    def contributions(self, project_id: int, limit: int | None = None) -> list[Contribution]:
        return self._db.list_contributions(project_id, limit)

    def contributions_by_session(self, project_id: int) -> dict[int | None, list[Contribution]]:
        return self._db.contributions_by_session(project_id)

    def global_totals(self) -> tuple[float, float]:
        today = self._now_fn().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today - timedelta(days=6)
        return (
            self._db.work_seconds_since(today),
            self._db.work_seconds_since(week_start),
        )

    def export_sessions_csv(self, path: str) -> int:
        return self._db.export_sessions_csv(Path(path))

    def contributions_export_csv(self, path: str) -> int:
        return self._db.export_contributions_csv(Path(path))

    def backup_database(self, path: Path) -> None:
        self._db.backup_to(path)


def _parse(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _clamp_goal(minutes: float) -> float:
    try:
        value = float(minutes)
    except (TypeError, ValueError):
        return 0.0
    if value != value or value in (float("inf"), float("-inf")):
        return 0.0
    return max(0.0, min(1440.0, value))
