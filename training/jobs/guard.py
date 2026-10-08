"""OS process containment; Windows Job memory limit and kill-on-close."""

import ctypes
import os
import signal
import sys
from ctypes import wintypes as w


class Basic(ctypes.Structure):
    _fields_ = [
        ("processTime", ctypes.c_longlong),
        ("jobTime", ctypes.c_longlong),
        ("flags", w.DWORD),
        ("minimum", ctypes.c_size_t),
        ("maximum", ctypes.c_size_t),
        ("active", w.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", w.DWORD),
        ("scheduling", w.DWORD),
    ]


class Extended(ctypes.Structure):
    _fields_ = [
        ("basic", Basic),
        ("io", ctypes.c_ulonglong * 6),
        ("processMemory", ctypes.c_size_t),
        ("jobMemory", ctypes.c_size_t),
        ("peakProcess", ctypes.c_size_t),
        ("peakJob", ctypes.c_size_t),
    ]


class Guard:
    def __init__(self, pid: int, memory: int, cpus: list[int]):
        self.pid = pid
        self.handle = None
        if sys.platform != "win32":
            return
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [
            w.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            w.DWORD,
        ]
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.api.OpenProcess.restype = w.HANDLE
        self.api.CloseHandle.argtypes = [w.HANDLE]
        handle = self.api.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        # KILL_ON_CLOSE, JOB_MEMORY, AFFINITY, PRIORITY_CLASS: inherited by descendants.
        limits.basic.flags = 0x2000 | 0x200 | 0x10 | 0x20
        limits.basic.affinity = sum(1 << cpu for cpu in cpus)
        limits.basic.priority = 0x4000
        limits.jobMemory = memory
        process = self.api.OpenProcess(0x0100 | 0x0001, False, pid)
        try:
            if (
                not process
                or not self.api.SetInformationJobObject(
                    handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
                )
                or not self.api.AssignProcessToJobObject(handle, process)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = handle
        except OSError:
            self.api.CloseHandle(handle)
            raise
        finally:
            if process:
                self.api.CloseHandle(process)

    def close(self) -> None:
        if sys.platform == "win32":
            if self.handle:
                self.api.CloseHandle(self.handle)
                self.handle = None
        else:
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
