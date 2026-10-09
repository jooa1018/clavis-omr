"""OR-004 Windows-only limits for the one authorized PDMX streaming process."""

import ctypes
import os
import sys
from ctypes import wintypes


def constrain(memory_bytes: int, threads: int) -> int:
    """Enforce job memory/process limits, CPU affinity and Below Normal priority."""
    if sys.platform != "win32" or memory_bytes <= 0 or not 1 <= threads <= 2:
        raise ValueError("OR-004 requires Windows and the approved resource limits")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = str(threads)

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_int64),
            ("job_time", ctypes.c_int64),
            ("flags", wintypes.DWORD),
            ("min_working", ctypes.c_size_t),
            ("max_working", ctypes.c_size_t),
            ("active", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", ctypes.c_uint64 * 6),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetCurrentProcess.restype = wintypes.HANDLE
    process = api.GetCurrentProcess()
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    job = api.CreateJobObjectW(None, None)
    api.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    api.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.GetProcessAffinityMask.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    api.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    limits = Extended()
    limits.basic.flags = 0x100 | 0x8
    limits.basic.active = 1
    limits.process_memory = memory_bytes
    allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not api.GetProcessAffinityMask(process, ctypes.byref(allowed), ctypes.byref(system)):
        raise OSError("Cannot inspect affinity")
    bits = [
        1 << bit for bit in range(ctypes.sizeof(ctypes.c_size_t) * 8) if allowed.value & (1 << bit)
    ]
    if not (
        job
        and api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
        and api.AssignProcessToJobObject(job, process)
        and api.SetPriorityClass(process, 0x4000)
        and api.SetProcessAffinityMask(process, sum(bits[:threads]))
    ):
        raise OSError("Cannot enforce OR-004 Windows limits")
    return int(job)
