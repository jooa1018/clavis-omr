"""Process-tree sampling with bounded, identity-free diagnostics."""

from typing import Any

import psutil

from training.jobs.resources import constrain

TRANSIENT_CHILD_ERRORS = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess)


class Diagnostics:
    def __init__(self) -> None:
        self.errors: dict[tuple[str, str, bool], int] = {}

    def record(self, error: BaseException, site: str, *, skipped: bool = False) -> None:
        # No exception message, traceback, command, PID, path or process identity.
        key = (type(error).__name__, site, skipped)
        self.errors[key] = self.errors.get(key, 0) + 1

    def report(self) -> list[dict[str, Any]]:
        return [
            {"exceptionType": kind, "site": site, "skippedChild": skipped, "count": count}
            for (kind, site, skipped), count in sorted(self.errors.items())
        ]


def sample(
    process: psutil.Process, cpu: dict[int, float], diagnostics: Diagnostics | None = None
) -> tuple[int, int]:
    diagnostics = diagnostics or Diagnostics()
    rss = threads = 0
    for item in [process, *process.children(recursive=True)]:
        site = "sample.memory_info"
        try:
            with item.oneshot():
                item_rss = item.memory_info().rss
                site = "sample.num_threads"
                item_threads = item.num_threads()
                site = "sample.cpu_times"
                timing = item.cpu_times()
        except TRANSIENT_CHILD_ERRORS as error:
            if item == process:
                diagnostics.record(error, site)
                raise
            diagnostics.record(error, site, skipped=True)
            continue
        # Commit a complete sample only; failed child reads cannot inflate aggregates.
        rss += item_rss
        threads += item_threads
        cpu[item.pid] = max(cpu.get(item.pid, 0), timing.user + timing.system)
    return rss, threads


def enforce_affinity(process: psutil.Process, cpus: list[int], diagnostics: Diagnostics) -> None:
    for member in [process, *process.children(recursive=True)]:
        try:
            if set(member.cpu_affinity()) - set(cpus):
                constrain(member, cpus)
        except TRANSIENT_CHILD_ERRORS as error:
            if member == process:
                raise
            diagnostics.record(error, "affinity.child", skipped=True)
