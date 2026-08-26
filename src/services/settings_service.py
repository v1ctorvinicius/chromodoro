from domain.settings import AppSettings
from storage.database import Database

_CYCLE_KEY = "completed_cycles"


class SettingsService:
    def __init__(self, db: Database):
        self._db = db
        self._cache: AppSettings | None = None

    def load(self) -> AppSettings:
        if self._cache is None:
            self._cache = AppSettings(
                work_minutes=self._int_setting("work_minutes", 25),
                break_minutes=self._int_setting("break_minutes", 5),
                long_break_minutes=self._int_setting("long_break_minutes", 15),
                cycles_before_long_break=self._int_setting("cycles_before_long_break", 4),
                sound_alerts=self._bool_setting("sound_alerts", True),
                auto_start_after_break=self._bool_setting("auto_start_after_break", False),
                close_to_tray=self._bool_setting("close_to_tray", True),
            )
        return self._cache

    def save(self, settings: AppSettings) -> AppSettings:
        validated = AppSettings(
            work_minutes=settings.work_minutes,
            break_minutes=settings.break_minutes,
            long_break_minutes=settings.long_break_minutes,
            cycles_before_long_break=settings.cycles_before_long_break,
            sound_alerts=settings.sound_alerts,
            auto_start_after_break=settings.auto_start_after_break,
            close_to_tray=settings.close_to_tray,
        )
        for key, value in (
            ("work_minutes", validated.work_minutes),
            ("break_minutes", validated.break_minutes),
            ("long_break_minutes", validated.long_break_minutes),
            ("cycles_before_long_break", validated.cycles_before_long_break),
            ("sound_alerts", int(validated.sound_alerts)),
            ("auto_start_after_break", int(validated.auto_start_after_break)),
            ("close_to_tray", int(validated.close_to_tray)),
        ):
            self._db.set_setting(key, str(value))
        self._cache = None
        return self.load()

    @property
    def completed_cycles(self) -> int:
        raw = self._db.get_setting(_CYCLE_KEY)
        try:
            return max(0, int(raw)) if raw is not None else 0
        except ValueError:
            return 0

    def bump_cycle(self) -> int:
        count = self.completed_cycles + 1
        self._db.set_setting(_CYCLE_KEY, str(count))
        return count

    def reset_cycle(self) -> None:
        self._db.set_setting(_CYCLE_KEY, "0")

    def _int_setting(self, key: str, default: int) -> int:
        raw = self._db.get_setting(key)
        if raw is None:
            return default
        try:
            return int(float(raw))
        except ValueError:
            return default

    def _bool_setting(self, key: str, default: bool) -> bool:
        raw = self._db.get_setting(key)
        if raw is None:
            return default
        normalized = raw.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
        return default
