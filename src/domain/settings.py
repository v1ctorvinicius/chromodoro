from dataclasses import dataclass

MIN_MINUTES = 1
MAX_MINUTES = 240
MIN_CYCLES = 2
MAX_CYCLES = 8


@dataclass(frozen=True)
class AppSettings:
    work_minutes: int = 25
    break_minutes: int = 5
    long_break_minutes: int = 15
    cycles_before_long_break: int = 4
    sound_alerts: bool = True
    auto_start_after_break: bool = False
    close_to_tray: bool = True
    start_in_tray: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "work_minutes", _clamp(int(self.work_minutes), MIN_MINUTES, MAX_MINUTES))
        object.__setattr__(self, "break_minutes", _clamp(int(self.break_minutes), MIN_MINUTES, MAX_MINUTES))
        object.__setattr__(
            self, "long_break_minutes", _clamp(int(self.long_break_minutes), MIN_MINUTES, MAX_MINUTES)
        )
        object.__setattr__(
            self,
            "cycles_before_long_break",
            _clamp(int(self.cycles_before_long_break), MIN_CYCLES, MAX_CYCLES),
        )
        object.__setattr__(self, "sound_alerts", bool(self.sound_alerts))
        object.__setattr__(self, "auto_start_after_break", bool(self.auto_start_after_break))
        object.__setattr__(self, "close_to_tray", bool(self.close_to_tray))
        object.__setattr__(self, "start_in_tray", bool(self.start_in_tray))


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))
