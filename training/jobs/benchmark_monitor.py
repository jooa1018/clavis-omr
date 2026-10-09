"""Approved benchmark admission and time-weighted external-load evidence."""

import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil
import yaml

from training.jobs.memory import snapshot
from training.jobs.power import power_state


def policy() -> dict[str, float]:
    path = Path(__file__).resolve().parents[2] / "configs/jobs/benchmark.yaml"
    return dict(yaml.safe_load(path.read_text(encoding="utf-8"))["values"])


def host_sample() -> dict[str, Any]:
    return {
        "systemLogicalCpus": psutil.cpu_percent() * (psutil.cpu_count() or 1) / 100,
        "availablePhysicalBytes": snapshot()["physicalAvailableBytes"],
        **power_state(),
    }


class LoadMonitor:
    def __init__(self, limits: dict[str, float]):
        self.limits = limits
        self.samples: list[dict[str, Any]] = []
        self.duration = self.external_seconds = self.maximum_window = 0.0
        self.last_cpu = 0.0
        self.reasons: set[str] = set()
        self.window: deque[tuple[float, float, float]] = deque()

    def observe(self, seconds: float, cpu_seconds: float, host: dict[str, Any]) -> None:
        if seconds <= 0:
            raise ValueError("sample interval must be positive")
        tree = max(0.0, cpu_seconds - self.last_cpu) / seconds
        self.last_cpu = cpu_seconds
        external = max(0.0, host["systemLogicalCpus"] - tree)
        previous = self.duration
        self.duration += seconds
        self.window.append((previous, self.duration, external))
        self.external_seconds += seconds * external
        self.samples.append(
            {
                "elapsedSeconds": self.duration,
                "intervalSeconds": seconds,
                "treeLogicalCpus": tree,
                "externalLogicalCpus": external,
                **host,
            }
        )
        window = self.limits["window_seconds"]
        if self.duration >= window:
            # A piecewise-constant moving integral can peak at either interval
            # boundary or at a boundary shifted by the window duration.
            ends = [self.duration] + [
                end + window for _, end, _ in self.window if previous < end + window < self.duration
            ]
            for end in ends:
                area = sum(
                    max(0.0, min(right, end) - max(left, end - window)) * value
                    for left, right, value in self.window
                )
                self.maximum_window = max(self.maximum_window, area / window)
            while self.window and self.window[0][1] <= self.duration - window:
                self.window.popleft()
            if self.maximum_window > self.limits["window_external_cpus"]:
                self.reasons.add("external-window-load")
        if host["availablePhysicalBytes"] < self.limits["run_available_bytes"]:
            self.reasons.add("physical-memory-low")
        if host["acConnected"] is not True:
            self.reasons.add("ac-power-lost-or-unknown")

    def report(self) -> dict[str, Any]:
        mean = self.external_seconds / self.duration if self.duration else None
        reasons = set(self.reasons)
        if mean is None:
            reasons.add("no-load-samples")
        elif mean > self.limits["mean_external_cpus"]:
            reasons.add("external-mean-load")
        return {
            "validity": "invalid" if reasons else "valid",
            "invalidReasons": sorted(reasons),
            "meanExternalLogicalCpus": mean,
            "maxFiveSecondExternalLogicalCpus": self.maximum_window
            if self.duration >= self.limits["window_seconds"]
            else None,
            "minimumAvailablePhysicalBytes": min(
                (s["availablePhysicalBytes"] for s in self.samples), default=None
            ),
            "powerStates": sorted({str(s["acConnected"]) for s in self.samples}),
            "windowsPowerModes": sorted({s["windowsPowerMode"] for s in self.samples}),
            "samples": self.samples,
        }


def preflight(limits: dict[str, float], cancelled: Callable[[], bool]) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(int(limits["retries"]) + 1):
        if cancelled():
            return {"status": "cancelled", "attempts": attempts}
        monitor = LoadMonitor(limits)
        host_sample()  # Prime nonblocking system CPU counter; first value is not an interval.
        start = prior_sample_time = time.monotonic()
        while monitor.duration < limits["preflight_seconds"]:
            if cancelled():
                return {"status": "cancelled", "attempts": attempts}
            time.sleep(limits["sample_seconds"])
            host = host_sample()
            now = time.monotonic()
            monitor.observe(now - prior_sample_time, 0.0, host)
            prior_sample_time = now
        result = monitor.report()
        attempts.append(result)
        if (
            result["meanExternalLogicalCpus"] <= limits["mean_external_cpus"]
            and result["minimumAvailablePhysicalBytes"] >= limits["start_available_bytes"]
            and all(s["acConnected"] is True for s in monitor.samples)
        ):
            return {"status": "ready", "attempts": attempts}
        if attempt < int(limits["retries"]):
            # Retry start times are at least 60 seconds apart, and pause remains responsive.
            while time.monotonic() - start < limits["retry_seconds"]:
                if cancelled():
                    return {"status": "cancelled", "attempts": attempts}
                time.sleep(limits["sample_seconds"])
    return {"status": "busy", "attempts": attempts}
