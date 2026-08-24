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
    id: int | None = None
