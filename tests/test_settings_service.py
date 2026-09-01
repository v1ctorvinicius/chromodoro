from domain.settings import MAX_MINUTES, MIN_CYCLES, AppSettings
from services.settings_service import SettingsService


def test_defaults_when_nothing_saved(db):
    service = SettingsService(db)

    loaded = service.load()

    assert loaded == AppSettings(
        work_minutes=25, break_minutes=5, long_break_minutes=15, cycles_before_long_break=4
    )


def test_save_and_reload_roundtrip(db):
    service = SettingsService(db)

    saved = service.save(
        AppSettings(work_minutes=50, break_minutes=10, long_break_minutes=25, cycles_before_long_break=3)
    )

    assert saved.work_minutes == 50
    assert saved.break_minutes == 10
    assert saved.long_break_minutes == 25
    assert saved.cycles_before_long_break == 3
    assert SettingsService(db).load() == saved


def test_out_of_range_values_are_clamped(db):
    clamped = AppSettings(
        work_minutes=MAX_MINUTES + 500,
        break_minutes=-3,
        long_break_minutes=0,
        cycles_before_long_break=MIN_CYCLES - 1,
    )

    assert clamped.work_minutes == MAX_MINUTES
    assert clamped.break_minutes == 1
    assert clamped.long_break_minutes == 1
    assert clamped.cycles_before_long_break == MIN_CYCLES


def test_cycle_counter_bump_and_reset(db):
    service = SettingsService(db)

    assert service.completed_cycles == 0
    assert service.bump_cycle() == 1
    assert service.bump_cycle() == 2
    assert service.completed_cycles == 2

    service.reset_cycle()
    assert service.completed_cycles == 0


def test_invalid_stored_setting_falls_back_to_default(db):
    db.set_setting("work_minutes", "not-a-number")
    service = SettingsService(db)

    loaded = service.load()
    assert loaded.work_minutes == 25


def test_sound_alerts_disabled_persists(db):
    service = SettingsService(db)

    saved = service.save(AppSettings(sound_alerts=False))

    assert saved.sound_alerts is False
    assert SettingsService(db).load().sound_alerts is False


def test_invalid_stored_sound_flag_falls_back_to_enabled(db):
    db.set_setting("sound_alerts", "banana")
    service = SettingsService(db)

    assert service.load().sound_alerts is True


def test_sound_flag_accepts_text_forms(db):
    for raw, expected in (("1", True), ("0", False), ("true", True), ("off", False)):
        db.set_setting("sound_alerts", raw)
        assert SettingsService(db).load().sound_alerts is expected


def test_start_filter_current_day_persists(db):
    service = SettingsService(db)
    saved = service.save(AppSettings(start_filter_current_day=True))
    assert saved.start_filter_current_day is True
    assert SettingsService(db).load().start_filter_current_day is True
