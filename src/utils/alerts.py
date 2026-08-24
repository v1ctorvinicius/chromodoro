import ctypes
from ctypes import wintypes

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]

FLASHW_ALL = 0x00000003
FLASHW_TIMERNOFG = 0x0000000C
DWMWA_CAPTION_COLOR = 35

_user32 = ctypes.windll.user32
_dwmapi = ctypes.windll.dwmapi


class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwnd", wintypes.HWND),
        ("dwFlags", wintypes.DWORD),
        ("uCount", wintypes.UINT),
        ("dwTimeout", wintypes.DWORD),
    ]


_FLASHWINFO_P = ctypes.POINTER(FLASHWINFO)

_user32.GetParent.argtypes = [wintypes.HWND]
_user32.GetParent.restype = wintypes.HWND
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.FlashWindowEx.argtypes = [_FLASHWINFO_P]
_user32.FlashWindowEx.restype = wintypes.BOOL
_dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
_dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
_dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
_dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long


def get_hwnd(widget) -> int | None:
    try:
        hwnd = _user32.GetParent(widget.winfo_id())
        return int(hwnd) if hwnd else None
    except Exception:
        return None


def is_foreground(hwnd: int) -> bool:
    try:
        return int(_user32.GetForegroundWindow() or 0) == hwnd
    except Exception:
        return True


def flash_until_focus(hwnd: int) -> bool:
    info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), wintypes.HWND(hwnd), FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0)
    return bool(_user32.FlashWindowEx(ctypes.byref(info)))


def stop_flash(hwnd: int) -> bool:
    info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), wintypes.HWND(hwnd), 0, 0, 0)
    return bool(_user32.FlashWindowEx(ctypes.byref(info)))


DARK_NEUTRAL_CAPTION = 0x202020
LIGHT_NEUTRAL_CAPTION = 0xF3F3F3


def system_caption_color(is_dark_theme: bool) -> int:
    neutral = DARK_NEUTRAL_CAPTION if is_dark_theme else LIGHT_NEUTRAL_CAPTION
    if winreg is None:
        return neutral
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            accent = _query_reg(key, "AccentColor")
            precedence = _query_reg(key, "ColorPrecedence")
            if precedence == 1 and accent is not None:
                return int(accent) & 0xFFFFFF
    except Exception:
        pass
    return neutral


def _query_reg(key, name: str) -> int | None:
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return int(value)
    except Exception:
        return None


def read_caption_color(hwnd: int) -> int | None:
    color = wintypes.COLORREF()
    result = _dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_CAPTION_COLOR, ctypes.byref(color), ctypes.sizeof(color)
    )
    if result != 0:
        return None
    return int(color.value)


def set_caption_color(hwnd: int, color: int) -> bool:
    value = wintypes.COLORREF(color)
    result = _dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_CAPTION_COLOR, ctypes.byref(value), ctypes.sizeof(value)
    )
    return result == 0
