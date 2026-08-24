from collections.abc import Callable
from datetime import datetime
from enum import Enum


class TimerState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class TimerMode(Enum):
    WORK = "work"
    BREAK = "break"


class TimerService:
    def __init__(self, now_fn: Callable[[], datetime] = datetime.now):
        self._now_fn = now_fn
        self._state = TimerState.IDLE
        self._mode = TimerMode.WORK
        self._target = 0.0
        self._elapsed_base = 0.0
        self._segment_start: datetime | None = None
        self._pause_base = 0.0
        self._paused_at: datetime | None = None
        self.on_complete: list[Callable[[], None]] = []

    @property
    def state(self) -> TimerState:
        return self._state

    @property
    def mode(self) -> TimerMode:
        return self._mode

    @property
    def target(self) -> float:
        return self._target

    @property
    def is_running(self) -> bool:
        return self._state is TimerState.RUNNING

    def start(self, duration_seconds: float, mode: TimerMode = TimerMode.WORK) -> None:
        self._target = max(0.0, float(duration_seconds))
        self._mode = mode
        self._reset_run()
        self._segment_start = self._now_fn()
        self._state = TimerState.RUNNING

    def adopt(
        self,
        target_seconds: float,
        elapsed_base: float,
        pause_seconds: float,
        segment_start: datetime | None,
    ) -> None:
        self._target = max(0.0, float(target_seconds))
        self._mode = TimerMode.WORK
        self._reset_run()
        self._elapsed_base = max(0.0, float(elapsed_base))
        self._pause_base = max(0.0, float(pause_seconds))
        if segment_start is not None:
            self._segment_start = segment_start
            self._state = TimerState.RUNNING
        else:
            self._paused_at = self._now_fn()
            self._state = TimerState.PAUSED

    def pause(self) -> None:
        if self._state is not TimerState.RUNNING:
            return
        self._elapsed_base = self.elapsed()
        self._segment_start = None
        self._paused_at = self._now_fn()
        self._state = TimerState.PAUSED

    def resume(self) -> None:
        if self._state is not TimerState.PAUSED:
            return
        assert self._paused_at is not None
        now = self._now_fn()
        span = (now - self._paused_at).total_seconds()
        self._pause_base += max(0.0, span)
        self._paused_at = None
        self._segment_start = now
        self._state = TimerState.RUNNING

    def cancel(self) -> None:
        self._state = TimerState.IDLE
        self._mode = TimerMode.WORK
        self._target = 0.0
        self._reset_run()

    def elapsed(self) -> float:
        if self._state is TimerState.RUNNING and self._segment_start is not None:
            delta = (self._now_fn() - self._segment_start).total_seconds()
            return max(0.0, self._elapsed_base + delta)
        return self._elapsed_base

    def remaining(self) -> float:
        return max(0.0, self._target - self.elapsed())

    def progress(self) -> float:
        if self._target <= 0:
            return 0.0
        return min(1.0, self.elapsed() / self._target)

    def pause_seconds(self) -> float:
        total = self._pause_base
        if self._state is TimerState.PAUSED and self._paused_at is not None:
            total += max(0.0, (self._now_fn() - self._paused_at).total_seconds())
        return total

    def poll(self) -> bool:
        if self._state is not TimerState.RUNNING:
            return False
        if self.elapsed() < self._target:
            return False
        self._elapsed_base = max(self._elapsed_base, self._target)
        self._segment_start = None
        self._state = TimerState.COMPLETED
        for callback in list(self.on_complete):
            callback()
        return True

    def _reset_run(self) -> None:
        self._elapsed_base = 0.0
        self._segment_start = None
        self._pause_base = 0.0
        self._paused_at = None
