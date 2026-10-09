"""Read power state without device names or custom plan descriptions."""

import ctypes
import sys
import uuid
from ctypes import wintypes as w

import psutil


def power_state() -> dict[str, bool | str | None]:
    if sys.platform != "win32":
        battery = psutil.sensors_battery()
        return {
            "acConnected": None if battery is None else battery.power_plugged,
            "windowsPowerMode": "not-applicable",
        }

    class Status(ctypes.Structure):
        _fields_ = [(name, w.BYTE) for name in ("ac", "flags", "percent", "saver")] + [
            ("life", w.DWORD),
            ("full", w.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetSystemPowerStatus.argtypes = [ctypes.POINTER(Status)]
    kernel.GetSystemPowerStatus.restype = w.BOOL
    status = Status()
    if not kernel.GetSystemPowerStatus(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    mode = "unavailable"
    try:
        api = ctypes.WinDLL("powrprof", use_last_error=True)
        query = api.PowerGetUserConfiguredACPowerMode
        query.argtypes = [ctypes.c_void_p]
        query.restype = w.DWORD
        guid = (ctypes.c_ubyte * 16)()
        if query(ctypes.byref(guid)) == 0:
            mode = str(uuid.UUID(bytes_le=bytes(guid)))
    except (AttributeError, OSError):
        pass
    return {
        "acConnected": status.ac == 1 if status.ac in (0, 1) else None,
        "windowsPowerMode": mode,
    }
