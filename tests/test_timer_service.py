from datetime import timedelta

import pytest

from services.timer_service import TimerMode, TimerService, TimerState


def make_timer(clock) -> TimerService:
    return TimerService(now_fn=clock.now)


def test_elapsed_grows_with_wall_clock(clock):
    timer = make_timer(clock)
    timer.start(1500)
    clock.advance(60)
    assert timer.elapsed() == pytest.approx(60, abs=1)
    assert timer.remaining() == pytest.approx(1440, abs=1)


def test_pause_freezes_and_resume_continues(clock):
    timer = make_timer(clock)
    timer.start(1500)
    clock.advance(600)
    timer.pause()
    clock.advance(120)
    assert timer.elapsed() == pytest.approx(600, abs=1)
    assert timer.state is TimerState.PAUSED
    timer.resume()
    assert timer.state is TimerState.RUNNING
    clock.advance(40)
    assert timer.elapsed() == pytest.approx(640, abs=1)


def test_pause_accumulates_pause_seconds(clock):
    timer = make_timer(clock)
    timer.start(1500)
    clock.advance(100)
    timer.pause()
    clock.advance(50)
    assert timer.pause_seconds() == pytest.approx(50, abs=1)
    timer.resume()
    clock.advance(10)
    timer.pause()
    clock.advance(20)
    assert timer.pause_seconds() == pytest.approx(70, abs=1)


def test_poll_completes_once_and_fires_callbacks(clock):
    timer = make_timer(clock)
    fired = []
    timer.on_complete.append(lambda: fired.append(True))
    timer.start(1500)
    clock.advance(1500)
    assert timer.poll() is True
    assert timer.poll() is False
    assert timer.state is TimerState.COMPLETED
    assert timer.elapsed() == pytest.approx(1500, abs=1)
    assert len(fired) == 1


def test_poll_does_not_complete_before_target(clock):
    timer = make_timer(clock)
    timer.start(1500)
    clock.advance(1499)
    assert timer.poll() is False


def test_cancel_resets_state(clock):
    timer = make_timer(clock)
    timer.start(1500)
    clock.advance(100)
    timer.cancel()
    assert timer.state is TimerState.IDLE
    assert timer.elapsed() == 0
    assert timer.target == 0


def test_adopt_running_session(clock):
    timer = make_timer(clock)
    segment_start = clock.now()
    timer.adopt(target_seconds=1500, elapsed_base=600, pause_seconds=0, segment_start=segment_start)
    assert timer.state is TimerState.RUNNING
    clock.advance(30)
    assert timer.elapsed() == pytest.approx(630, abs=1)


def test_adopt_paused_session(clock):
    timer = make_timer(clock)
    timer.adopt(target_seconds=1500, elapsed_base=600, pause_seconds=45, segment_start=None)
    assert timer.state is TimerState.PAUSED
    assert timer.elapsed() == pytest.approx(600, abs=1)
    assert timer.pause_seconds() == pytest.approx(45, abs=2)


def test_adopt_past_target_completes_on_first_poll(clock):
    timer = make_timer(clock)
    segment_start = clock.now() - timedelta(seconds=3600)
    timer.adopt(target_seconds=1500, elapsed_base=0, pause_seconds=0, segment_start=segment_start)
    assert timer.poll() is True
    assert timer.elapsed() >= 1500


def test_break_mode_is_tracked(clock):
    timer = make_timer(clock)
    timer.start(300, TimerMode.BREAK)
    assert timer.mode is TimerMode.BREAK
