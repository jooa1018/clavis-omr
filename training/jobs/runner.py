"""Single local CPU worker with sampled process-tree limits and durable pause."""

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from training.jobs.guard import Guard
from training.jobs.launcher import alive, kill_tree
from training.jobs.memory import can_start, snapshot
from training.jobs.model import JobSpec, atomic_json
from training.jobs.monitor import Diagnostics, enforce_affinity, sample
from training.jobs.resources import THREAD_ENV, allowed_cpus, constrain
from training.jobs.store import Queue, worker_lock

DISK_RESERVE = 3_000_000_000


def in_window(now: datetime | None = None) -> bool:
    return 1 <= (now or datetime.now()).hour < 7


def disk_ok(paths: list[Path]) -> bool:
    return all(shutil.disk_usage(path).free >= DISK_RESERVE for path in paths)


def recover(queue: Queue) -> None:
    for row in queue.rows():
        if row["status"] != "running":
            continue
        if row["pid"] and alive(row["pid"], row["born"]):
            kill_tree(psutil.Process(row["pid"]))
        queue.update(row["id"], status="paused", reason="interrupted")


def execute(queue: Queue, row: dict[str, Any], manual: bool) -> dict[str, Any]:
    spec = JobSpec.model_validate_json(row["spec"])
    directory = queue.root / row["id"]
    directory.mkdir(exist_ok=True)
    for name in ("go", "stop"):
        (directory / name).unlink(missing_ok=True)
    atomic_json(directory / "request.json", spec.model_dump())
    queue.record(
        {
            "event": "started",
            "jobId": row["id"],
            "config": spec.config,
            "seed": spec.seed,
            "dataDigest": spec.data_digest,
            "gitSha": spec.git_sha,
            "priorWallSeconds": row["wall"],
            "jobDigest": spec.digest(),
        }
    )
    env = dict(os.environ)
    env.update(
        {
            "CLAVIS_JOB_DIR": str(directory),
            "CLAVIS_JOB_DIGEST": spec.digest(),
            "CLAVIS_RUNNER_PID": str(os.getpid()),
            "CLAVIS_RUNNER_BORN": str(psutil.Process().create_time()),
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        }
    )
    cpus = allowed_cpus(spec.threads, psutil.Process().cpu_affinity())
    env["CLAVIS_CPU_LIMIT"] = str(len(cpus))
    for name in THREAD_ENV:
        env[name] = str(len(cpus))
    repository = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repository / "training/jobs/bootstrap"), str(repository), str(repository / "src")]
    )
    paths = [queue.root, Path(spec.cwd)]
    # Only the supplied environment path is consulted; no private directory is enumerated.
    if private := env.get("CLAVIS_PRIVATE_ROOT"):
        paths.append(Path(private))
    start = time.monotonic()
    cpu: dict[int, float] = {}
    peak = peak_threads = 0
    peak_cpu = last_cpu = 0.0
    last_sample = start
    host_memory: list[dict[str, int | float]] = []
    reason = "completed"
    diagnostics = Diagnostics()
    site = "preflight.memory"
    process: psutil.Process | None = None
    guard: Guard | None = None
    try:
        initial_memory = snapshot()
        host_memory.append({"elapsedSeconds": 0.0, **initial_memory})
        if not can_start(initial_memory, spec.ram_bytes):
            reason = "memory-low"
        elif not disk_ok(paths):
            reason = "disk-low"
        elif row["wall"] >= spec.wall_seconds:
            reason = "wall-limit"
        else:
            flags = 0
            if sys.platform == "win32":
                flags = subprocess.CREATE_NO_WINDOW
            site = "launch.Popen"
            child = subprocess.Popen(
                [sys.executable, "-m", "training.jobs.launcher"],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                start_new_session=os.name != "nt",
            )
            site = "launch.containment"
            process = psutil.Process(child.pid)
            guard = Guard(child.pid, spec.ram_bytes, cpus)
            constrain(process, cpus)
            queue.update(row["id"], pid=child.pid, born=process.create_time())
            (directory / "go").touch()
            while child.poll() is None:
                try:
                    site = "sample.process_tree"
                    rss, threads = sample(process, cpu, diagnostics)
                except psutil.NoSuchProcess:
                    break
                peak, peak_threads = max(peak, rss), max(peak_threads, threads)
                sampled_at = time.monotonic()
                site = "sample.host_memory"
                host_memory.append({"elapsedSeconds": sampled_at - start, **snapshot()})
                total_cpu = sum(cpu.values())
                peak_cpu = max(
                    peak_cpu, (total_cpu - last_cpu) / max(sampled_at - last_sample, 1e-9)
                )
                last_cpu, last_sample = total_cpu, sampled_at
                site = "affinity.process_tree"
                if guard.handle is None:
                    try:
                        enforce_affinity(process, cpus, diagnostics)
                    except psutil.NoSuchProcess:
                        pass
                elapsed = row["wall"] + time.monotonic() - start
                site = "monitor.queue_and_limits"
                queue.update(row["id"], wall=elapsed)
                if rss > spec.ram_bytes:
                    reason = "ram-limit"
                elif elapsed >= spec.wall_seconds:
                    reason = "wall-limit"
                elif queue.paused():
                    reason = "user-pause"
                elif not manual and not in_window():
                    reason = "window-closed"
                elif not disk_ok(paths):
                    reason = "disk-low"
                if reason != "completed":
                    (directory / "stop").touch()
                    if reason in {"user-pause", "window-closed"}:
                        try:
                            child.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            pass
                    kill_tree(process)
                    break
                time.sleep(0.1)
            if child.wait() != 0 and reason == "completed":
                reason = "command-failed"
            site = "cleanup.process_tree"
            kill_tree(process)
    except (OSError, psutil.Error) as error:
        diagnostics.record(error, site)
        reason = "monitor-error"
    except KeyboardInterrupt:
        queue.pause()
        reason = "user-pause"
    finally:
        try:
            if guard is not None:
                guard.close()
            if process is not None:
                kill_tree(process)
        except (OSError, psutil.Error) as error:
            diagnostics.record(error, "cleanup.finally")
            reason = "monitor-error"
    elapsed = row["wall"] + time.monotonic() - start
    status = (
        "succeeded"
        if reason == "completed"
        else "paused"
        if reason in {"user-pause", "window-closed", "disk-low", "memory-low"}
        else "failed"
    )
    report = {
        "jobId": row["id"],
        "status": status,
        "reason": reason,
        "config": spec.config,
        "seed": spec.seed,
        "dataDigest": spec.data_digest,
        "gitSha": spec.git_sha,
        "jobDigest": spec.digest(),
        "wallSeconds": elapsed,
        "cpuSecondsSampled": sum(cpu.values()),
        "peakRssBytesSampled": peak,
        "peakThreadsSampled": peak_threads,
        "resultDirectory": row["id"],
        "manual": manual,
        "cpuAffinity": cpus,
        "cpuLimit": len(cpus),
        "meanLogicalCpusSampled": sum(cpu.values()) / max(elapsed - row["wall"], 1e-9),
        "peakLogicalCpusSampled": peak_cpu,
        "meanCpuPercentSampled": 100 * sum(cpu.values()) / max(elapsed - row["wall"], 1e-9),
        "peakCpuPercentSampled": 100 * peak_cpu,
        "hostMemorySamples": host_memory,
        "monitorDiagnostics": diagnostics.report(),
        "warnings": (
            ["MEAN_CPU_ABOVE_8"] if sum(cpu.values()) > 8 * (elapsed - row["wall"]) else []
        ),
    }
    queue.record(report)
    queue.update(row["id"], status=status, wall=elapsed, reason=reason, pid=None, born=None)
    return report


def run(queue: Queue, *, manual: bool = False) -> list[dict[str, Any]]:
    reports = []
    with worker_lock():
        recover(queue)
        while not queue.paused() and (manual or in_window()) and disk_ok([queue.root]):
            row = queue.claim()
            if row is None:
                break
            report = execute(queue, row, manual)
            reports.append(report)
            if report["status"] == "paused":
                break
    return reports
