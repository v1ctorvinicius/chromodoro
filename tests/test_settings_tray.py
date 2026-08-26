import time

import pytest

from domain.settings import AppSettings
from services.settings_service import SettingsService
from utils.tray import TrayController


@pytest.fixture()
def service(db):
    return SettingsService(db)


def test_new_settings_default_off_and_on(service):
    loaded = service.load()
    assert loaded.auto_start_after_break is False
    assert loaded.close_to_tray is True


def test_settings_roundtrip_persists_booleans(service):
    saved = service.save(
        AppSettings(
            work_minutes=30,
            break_minutes=6,
            long_break_minutes=18,
            cycles_before_long_break=3,
            sound_alerts=False,
            auto_start_after_break=True,
            close_to_tray=False,
        )
    )
    assert saved.auto_start_after_break is True
    assert saved.close_to_tray is False
    assert saved.sound_alerts is False

    service._cache = None
    reloaded = service.load()
    assert reloaded.auto_start_after_break is True
    assert reloaded.close_to_tray is False
    assert reloaded.work_minutes == 30


def test_partial_save_keeps_other_fields(service):
    service.save(AppSettings(work_minutes=40, break_minutes=8, auto_start_after_break=True))
    updated = service.save(AppSettings(close_to_tray=False))
    assert updated.work_minutes == 25
    assert updated.auto_start_after_break is False
    assert updated.close_to_tray is False


def test_tray_controller_lifecycle_without_run():
    controller = TrayController("Chromodoro")
    if not controller.available:
        pytest.skip("pystray unavailable")
    assert controller.open_requested.is_set() is False
    assert controller.quit_requested.is_set() is False
    controller.update_tooltip("no icon yet")
    controller.stop()

    assert controller.start() is True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and controller._icon is None:
        time.sleep(0.05)
    assert controller._icon is not None

    controller.stop()
    assert controller._icon is None


def test_tray_flags_set_by_callbacks():
    controller = TrayController("Chromodoro")
    controller._on_open()
    controller._on_quit()
    assert controller.open_requested.is_set()
    assert controller.quit_requested.is_set()
    controller.open_requested.clear()
    controller.quit_requested.clear()
    assert not controller.open_requested.is_set()
    assert not controller.quit_requested.is_set()
