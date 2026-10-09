"""Observe batch training conditions using W1's existing load evidence policy."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Event, Thread

import psutil

from training.jobs.benchmark_monitor import LoadMonitor, host_sample, policy
from training.jobs.monitor import Diagnostics, sample


@contextmanager
def observe_load() -> Iterator[dict]:
    """Keep Below Normal/limited affinity; this does not create a benchmark job."""
    limits = policy()
    monitor = LoadMonitor(limits)
    diagnostics = Diagnostics()
    stopped, ready = Event(), Event()
    errors: list[str] = []
    evidence: dict = {}

    def collect() -> None:
        try:
            process = psutil.Process()
            cpu: dict[int, float] = {}
            sample(process, cpu, diagnostics)
            monitor.last_cpu = sum(cpu.values())
            host_sample()  # Prime this thread's system CPU interval counter.
            previous = time.perf_counter()
            ready.set()
            while True:
                finished = stopped.wait(limits["sample_seconds"])
                sample(process, cpu, diagnostics)
                host = host_sample()
                now = time.perf_counter()
                monitor.observe(now - previous, sum(cpu.values()), host)
                previous = now
                if finished:
                    break
        except Exception as error:
            # No raw exception message or process identity enters public evidence.
            errors.append(type(error).__name__)
        finally:
            ready.set()

    thread = Thread(target=collect, name="w6-trial-load", daemon=True)
    thread.start()
    ready.wait()
    try:
        yield evidence
    finally:
        stopped.set()
        thread.join()
        evidence.update(monitor.report())
        if errors:
            evidence["validity"] = "invalid"
            evidence["invalidReasons"] = sorted(
                set(evidence["invalidReasons"]) | {"load-sampling-error"}
            )
        evidence.update(
            scope="batch training load screen; not engine latency benchmark validity",
            policy=limits,
            samplingErrors=errors,
            monitorDiagnostics=diagnostics.report(),
            comparisonEligible=evidence["validity"] == "valid",
        )
