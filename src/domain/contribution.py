from dataclasses import dataclass
from datetime import datetime


@dataclass
class Contribution:
    project_id: int
    title: str
    created_at: datetime | None = None
    session_id: int | None = None
    type: str | None = None
    id: int | None = None
