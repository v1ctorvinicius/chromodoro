import sys

import pytest

from utils.alerts import get_hwnd, is_foreground, read_caption_color


class ExplodingWidget:
    def winfo_id(self):
        raise RuntimeError("no display")


def test_get_hwnd_swallows_widget_errors():
    assert get_hwnd(ExplodingWidget()) is None


def test_get_hwnd_swallows_missing_api():
    assert get_hwnd(object()) is None


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="win32 only")
def test_is_foreground_invalid_hwnd_is_false():
    assert is_foreground(1 << 30) is False


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="win32 only")
def test_read_caption_color_invalid_hwnd_is_none():
    assert read_caption_color(1 << 30) is None
