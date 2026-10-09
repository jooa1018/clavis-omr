"""Machine-wide short-run slots sharing the queue's exclusive worker lock."""

import ctypes
import json
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from ctypes import wintypes as w

from training.jobs import store
from training.jobs.model import atomic_json

DEFAULT_SLOTS = 3


class Overlapped(ctypes.Structure):
    _fields_ = [
        ("internal", ctypes.c_size_t),
        ("internal_high", ctypes.c_size_t),
        ("offset", w.DWORD),
        ("offset_high", w.DWORD),
        ("event", w.HANDLE),
    ]


@contextmanager
def shared_worker_lock() -> Iterator[None]:
    """Use the same byte/range as worker_lock; OS releases locks after a crash."""
    path = store.home().parent / "worker.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if sys.platform == "win32":
            import msvcrt

            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.LockFileEx.argtypes = [
                w.HANDLE,
                w.DWORD,
                w.DWORD,
                w.DWORD,
                w.DWORD,
                ctypes.c_void_p,
            ]
            api.LockFileEx.restype = w.BOOL
            api.UnlockFileEx.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, ctypes.c_void_p]
            api.UnlockFileEx.restype = w.BOOL
            handle = msvcrt.get_osfhandle(stream.fileno())
            overlap = Overlapped()
            # FAIL_IMMEDIATELY, without EXCLUSIVE_LOCK: other short runs may share.
            if not api.LockFileEx(handle, 1, 0, 1, 0, ctypes.byref(overlap)):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if sys.platform == "win32":
                if not api.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(overlap)):
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def slot_count() -> int:
    path = store.home().parent / "short-slots.json"
    value = (
        json.loads(path.read_text(encoding="utf-8"))["slots"] if path.exists() else DEFAULT_SLOTS
    )
    if type(value) is not int or value < 1:
        raise ValueError("slot count must be a positive integer")
    return value


def configure_slots(count: int) -> None:
    if type(count) is not int or count < 1:
        raise ValueError("slot count must be a positive integer")
    # Reconfiguration cannot race a running short task or an exclusive queue worker.
    with store.worker_lock():
        atomic_json(store.home().parent / "short-slots.json", {"slots": count})


@contextmanager
def short_slot() -> Iterator[int]:
    with shared_worker_lock():
        for index in range(slot_count()):
            stack = ExitStack()
            try:
                stack.enter_context(
                    store.worker_lock(store.home().parent / f"short-slot-{index}.lock")
                )
            except OSError:
                stack.close()
                continue
            with stack:
                yield index
            return
        raise BlockingIOError("all short-run slots are occupied")
