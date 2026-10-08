"""Host memory telemetry; Windows commit capacity is not physical RAM availability."""

import ctypes
import os
import sys
from pathlib import Path
from typing import Any

import psutil

MEMORY_RESERVE = 1_000_000_000


def snapshot() -> dict[str, int]:
    physical = psutil.virtual_memory()
    if os.name == "nt":
        return windows_snapshot()
    fields = {
        line.split(":")[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    return {
        "physicalTotalBytes": physical.total,
        "physicalAvailableBytes": physical.available,
        "commitAvailableBytes": max(0, fields["CommitLimit"] - fields["Committed_AS"]),
        "pagefileTotalBytes": fields["SwapTotal"],
    }


def windows_snapshot() -> dict[str, int]:
    if sys.platform != "win32":
        raise OSError("Windows memory counters require Windows")
    # GetPerformanceInfo reports system commit; EnumPageFiles reports actual pagefile sizes.
    from ctypes import wintypes

    class Performance(ctypes.Structure):
        _fields_ = (
            [("cb", wintypes.DWORD)]
            + [
                (name, ctypes.c_size_t)
                for name in (
                    "CommitTotal",
                    "CommitLimit",
                    "CommitPeak",
                    "PhysicalTotal",
                    "PhysicalAvailable",
                    "SystemCache",
                    "KernelTotal",
                    "KernelPaged",
                    "KernelNonpaged",
                    "PageSize",
                )
            ]
            + [(name, wintypes.DWORD) for name in ("HandleCount", "ProcessCount", "ThreadCount")]
        )

    class PageFile(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("Reserved", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("TotalSize", "TotalInUse", "PeakUsage")
        ]

    api = ctypes.WinDLL("psapi", use_last_error=True)
    info = Performance()
    info.cb = ctypes.sizeof(info)
    api.GetPerformanceInfo.argtypes = [ctypes.POINTER(Performance), wintypes.DWORD]
    api.GetPerformanceInfo.restype = wintypes.BOOL
    if not api.GetPerformanceInfo(ctypes.byref(info), info.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    pages: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, ctypes.c_void_p, ctypes.POINTER(PageFile), wintypes.LPCWSTR
    )

    def collect(_context: object, entry: Any, _filename: object) -> bool:
        item = ctypes.cast(entry, ctypes.POINTER(PageFile)).contents
        pages.append(item.TotalSize)
        return True

    callback = callback_type(collect)
    api.EnumPageFilesW.argtypes = [callback_type, ctypes.c_void_p]
    api.EnumPageFilesW.restype = wintypes.BOOL
    if not api.EnumPageFilesW(callback, None):
        raise ctypes.WinError(ctypes.get_last_error())
    return {
        "physicalTotalBytes": info.PhysicalTotal * info.PageSize,
        "physicalAvailableBytes": info.PhysicalAvailable * info.PageSize,
        "commitAvailableBytes": max(0, info.CommitLimit - info.CommitTotal) * info.PageSize,
        "pagefileTotalBytes": sum(pages) * info.PageSize,
    }


def can_start(memory: dict[str, int], ram_bytes: int) -> bool:
    return memory["commitAvailableBytes"] >= ram_bytes + MEMORY_RESERVE
