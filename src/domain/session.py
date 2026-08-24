from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass
class Session:
    project_id: int
    started_at: datetime
    ended_at: datetime | None = None
    duration: float = 0.0
    pause_duration: float = 0.0
    status: SessionStatus = SessionStatus.RUNNING
    running_since: datetime | None = None
    id: int | None = None

    def work_seconds(self, now: datetime) -> float:
        if self.running_since is not None:
            delta = (now - self.running_since).total_seconds()
            return max(0.0, self.duration + delta)
        return self.duration
