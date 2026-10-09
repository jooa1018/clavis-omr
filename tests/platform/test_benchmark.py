"""Exclusive benchmarks: admission, resource policy and contamination boundaries."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psutil
import pytest
from pydantic import ValidationError

from training.jobs import benchmark, slots, store
from training.jobs import benchmark_monitor as bm
from training.jobs.model import JobSpec
from training.jobs.power import power_state
from training.jobs.runner import execute


def host(load=0.0, ram=8_000_000_000, ac=True):
    return {
        "systemLogicalCpus": load,
        "availablePhysicalBytes": ram,
        "acConnected": ac,
        "windowsPowerMode": "synthetic-balanced",
    }


def test_policy_and_old_checkpoint_digest():
    limits = bm.policy()
    assert limits["threads"] == 4
    assert limits["mean_external_cpus"] == 0.5
    spec = JobSpec(
        module="training.jobs.example",
        cwd=str(Path.cwd()),
        config={},
        seed=0,
        data_digest="0" * 64,
        git_sha="1" * 40,
    )
    import hashlib

    assert (
        spec.digest() == hashlib.sha256(spec.model_dump_json(exclude={"kind"}).encode()).hexdigest()
    )
    with pytest.raises(ValidationError):
        JobSpec.model_validate({**spec.model_dump(), "kind": "benchmark"})


@pytest.mark.parametrize("load,valid", [(0.5, True), (0.5001, False)])
def test_mean_boundary(load, valid):
    monitor = bm.LoadMonitor(bm.policy())
    monitor.observe(2, 4, host(load + 2))
    assert (monitor.report()["validity"] == "valid") == valid
    assert monitor.report()["meanExternalLogicalCpus"] == pytest.approx(load)


def test_weighted_window_and_latched_spike():
    monitor = bm.LoadMonitor(bm.policy())
    monitor.observe(2, 0, host(0))
    monitor.observe(3, 0, host(2))
    monitor.observe(20, 0, host(0))
    report = monitor.report()
    assert report["meanExternalLogicalCpus"] == pytest.approx(6 / 25)
    assert report["maxFiveSecondExternalLogicalCpus"] == pytest.approx(1.2)
    assert report["invalidReasons"] == ["external-window-load"]


@pytest.mark.parametrize(
    "ram,ac,invalid",
    [
        (2_000_000_000, True, False),
        (1_999_999_999, True, True),
        (8_000_000_000, False, True),
        (8_000_000_000, None, True),
    ],
)
def test_memory_power_boundaries(ram, ac, invalid):
    monitor = bm.LoadMonitor(bm.policy())
    monitor.observe(1, 0, host(ram=ram, ac=ac))
    assert (monitor.report()["validity"] == "invalid") == invalid


def test_no_samples_invalid_and_short_window_unavailable():
    monitor = bm.LoadMonitor(bm.policy())
    assert monitor.report()["validity"] == "invalid"
    monitor.observe(1, 0, host())
    assert monitor.report()["maxFiveSecondExternalLogicalCpus"] is None


def test_window_peak_inside_long_sample():
    monitor = bm.LoadMonitor(bm.policy())
    monitor.observe(1, 0, host(0))
    monitor.observe(1, 0, host(4))
    monitor.observe(10, 0, host(0.5))
    assert monitor.report()["maxFiveSecondExternalLogicalCpus"] == pytest.approx(1.2)


class Clock:
    value = 0.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


@pytest.mark.parametrize(
    "bad", [host(0.51), host(ram=3_999_999_999), host(ac=False), host(ac=None)]
)
def test_preflight_busy_retries_and_never_launches(bad):
    clock = Clock()
    with (
        patch.object(bm.time, "monotonic", clock.now),
        patch.object(bm.time, "sleep", clock.sleep),
        patch.object(bm, "host_sample", return_value=bad),
    ):
        result = bm.preflight(bm.policy(), lambda: False)
    assert result["status"] == "busy"
    assert len(result["attempts"]) == 11  # initial check plus ten retries
    assert clock.value >= 610


def test_preflight_ready_boundary_and_cancel():
    clock = Clock()
    with (
        patch.object(bm.time, "monotonic", clock.now),
        patch.object(bm.time, "sleep", clock.sleep),
        patch.object(bm, "host_sample", return_value=host(0.5, 4_000_000_000)),
    ):
        assert bm.preflight(bm.policy(), lambda: False)["status"] == "ready"
        assert clock.value >= 10
        assert bm.preflight(bm.policy(), lambda: True)["status"] == "cancelled"


@pytest.mark.parametrize("cancel_after", [1, 11])
def test_pause_during_sampling_or_retry(cancel_after):
    clock = Clock()
    with (
        patch.object(bm.time, "monotonic", clock.now),
        patch.object(bm.time, "sleep", clock.sleep),
        patch.object(bm, "host_sample", return_value=host(2)),
    ):
        result = bm.preflight(bm.policy(), lambda: clock.value >= cancel_after)
    assert result["status"] == "cancelled"
    assert clock.value < cancel_after + 1


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "home", lambda: tmp_path / "jobs")
    monkeypatch.setattr("training.jobs.runner.disk_ok", lambda paths: True)
    monkeypatch.setattr(
        "training.jobs.runner.snapshot",
        lambda: {"commitAvailableBytes": 8_000_000_000, "physicalAvailableBytes": 8_000_000_000},
    )
    monkeypatch.setattr(
        "training.jobs.runner.preflight", lambda *args: {"status": "ready", "attempts": []}
    )
    monkeypatch.setattr("training.jobs.runner.host_sample", lambda: host())


def test_queue_and_slot_block_benchmark(isolated):
    with store.worker_lock():
        assert benchmark.run_benchmark("training.jobs.example", [])["reason"] == "machine-occupied"
    with slots.short_slot():
        assert benchmark.run_benchmark("training.jobs.example", [])["status"] == "busy"


def test_benchmark_excludes_slots_during_admission(isolated):
    def admission(*args):
        with pytest.raises(OSError), slots.short_slot():
            pass
        with pytest.raises(OSError), store.worker_lock():
            pass
        return {"status": "busy", "attempts": []}

    with (
        patch("training.jobs.runner.preflight", admission),
        patch("training.jobs.runner.subprocess.Popen") as spawn,
        patch(
            "training.jobs.benchmark.subprocess.run", return_value=SimpleNamespace(stdout="1" * 40)
        ),
    ):
        assert benchmark.run_benchmark("training.jobs.example", [])["status"] == "busy"
    spawn.assert_not_called()


def test_four_threads_full_affinity_normal_priority_and_evidence(isolated, tmp_path):
    queue = store.Queue(tmp_path / "queue")
    spec = JobSpec(
        kind="benchmark",
        module="training.jobs.example",
        cwd=str(Path.cwd()),
        config={"steps": 2, "probe": True},
        seed=0,
        data_digest="0" * 64,
        git_sha="1" * 40,
        threads=4,
    )
    identity = queue.submit(spec)
    # A containing short-run Job Object cannot be escaped in local full-suite validation.
    # Normal priority is verified by the real call and by clean CI outside that outer job.
    with (
        store.worker_lock(),
        patch(
            "training.jobs.runner.constrain",
            wraps=__import__("training.jobs.resources", fromlist=["constrain"]).constrain,
        ) as constrain,
    ):
        report = execute(queue, queue.claim(), True)
    assert report["status"] == "succeeded"
    assert report["cpuLimit"] == 4
    assert report["cpuAffinity"] == psutil.Process().cpu_affinity()
    assert constrain.call_args.kwargs["normal_priority"] is True
    probe = json.loads((queue.root / identity / "probe.json").read_text())
    assert probe["omp"] == probe["child"]["omp"] == "4"
    assert probe["cpus"] == probe["child"]["cpus"] == report["cpuAffinity"]
    assert probe["priority"] == probe["child"]["priority"]
    if psutil.Process().nice() == (psutil.NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 0):
        assert probe["priority"] == (
            int(psutil.NORMAL_PRIORITY_CLASS) if sys.platform == "win32" else 0
        )
    assert report["benchmark"]["validity"] == "valid"


def test_invalid_result_retained(isolated):
    with patch("training.jobs.runner.host_sample", return_value=host(ac=False)):
        report = benchmark.run_benchmark("training.jobs.example", [])
    assert report["status"] == "invalid"
    assert report["benchmark"]["invalidReasons"] == ["ac-power-lost-or-unknown"]
    root = store.home().parent / "benchmark-runs" / report["runId"]
    assert (
        json.loads((root / "experiments.jsonl").read_text().splitlines()[-1])["status"] == "invalid"
    )


def test_power_telemetry_shape():
    result = power_state()
    assert result["acConnected"] in (True, False, None)
    assert isinstance(result["windowsPowerMode"], str)


def test_admission_timing_does_not_change_job_bytes(isolated, tmp_path):
    outputs = []
    spec = JobSpec(
        kind="benchmark",
        module="training.jobs.example",
        cwd=str(Path.cwd()),
        config={"steps": 2},
        seed=0,
        data_digest="0" * 64,
        git_sha="1" * 40,
        threads=4,
    )
    for attempt in (1, 2):
        queue = store.Queue(tmp_path / str(attempt))
        identity = queue.submit(spec)
        with (
            store.worker_lock(),
            patch(
                "training.jobs.runner.preflight",
                return_value={
                    "status": "ready",
                    "attempts": [{"synthetic": True}] * attempt,
                },
            ),
        ):
            assert execute(queue, queue.claim(), True)["status"] == "succeeded"
        outputs.append((queue.root / identity / "checkpoint.json").read_bytes())
    assert outputs[0] == outputs[1]


def test_preflight_monitor_error_is_safe(isolated, tmp_path):
    queue = store.Queue(tmp_path / "failure")
    identity = queue.submit(
        JobSpec(
            kind="benchmark",
            module="training.jobs.example",
            cwd=str(Path.cwd()),
            config={},
            seed=0,
            data_digest="0" * 64,
            git_sha="1" * 40,
            threads=4,
        )
    )
    with patch("training.jobs.runner.preflight", side_effect=OSError("PRIVATE_SENTINEL")):
        result = execute(queue, queue.claim(), True)
    assert result["jobId"] == identity
    assert result["reason"] == "monitor-error"
    assert "PRIVATE_SENTINEL" not in json.dumps(result)
