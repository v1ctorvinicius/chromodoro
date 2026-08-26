import ctypes
import hashlib
from ctypes import wintypes
from pathlib import Path

_ERROR_ALREADY_EXISTS = 0x00B7


def mutex_name_for(db_path: Path) -> str:
    try:
        identity = str(db_path.resolve()).casefold()
    except Exception:
        identity = str(db_path).casefold()
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()
    return f"Chromodoro_{digest[:20]}"


def acquire_instance_lock(db_path: Path) -> bool:
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        name = mutex_name_for(db_path)
        kernel32.CreateMutexW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW(None, False, name)
        return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS
    except Exception:
        return True
