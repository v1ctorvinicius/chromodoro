from dataclasses import dataclass
from datetime import datetime

ACTIVE = "active"
ARCHIVED = "archived"


@dataclass
class Project:
    name: str
    description: str = ""
    status: str = ACTIVE
    created_at: datetime | None = None
    daily_goal_minutes: float = 0.0
    weekly_goal_minutes: float = 0.0
    monthly_goal_minutes: float = 0.0
    goal_days_of_week: list[int] | None = None  # 0=Mon .. 6=Sun, None/empty = all days
    id: int | None = None

    def is_goal_day(self, weekday: int) -> bool:
        if not self.goal_days_of_week:
            return True
        return weekday in self.goal_days_of_week
