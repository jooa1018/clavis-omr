"""Queue admission, checkpoints, limits and crash recovery with synthetic jobs."""

import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest
from pydantic import ValidationError

from training.jobs import __main__ as cli
from training.jobs.context import Context
from training.jobs.model import JobSpec
from training.jobs.runner import disk_ok, execute, in_window, recover, run, sample
from training.jobs.store import Queue, worker_lock

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_machine_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("training.jobs.store.home", lambda: tmp_path / "default-queue")
    monkeypatch.setattr(
        "training.jobs.runner.snapshot",
        lambda: {
            "physicalTotalBytes": 24_000_000_000,
            "physicalAvailableBytes": 8_000_000_000,
            "commitAvailableBytes": 8_000_000_000,
            "pagefileTotalBytes": 4_000_000_000,
        },
    )


def spec(**values: object) -> JobSpec:
    return JobSpec.model_validate(
        {
            "module": "training.jobs.example",
            "cwd": str(ROOT),
            "config": {"steps": 4},
            "seed": 1,
            "data_digest": "0" * 64,
            "git_sha": "1" * 40,
            **values,
        }
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("threads", 9),
        ("threads", 0),
        ("ram_bytes", 3000000001),
        ("wall_seconds", 14401),
        ("wall_seconds", 0),
        ("data_digest", "invalid"),
        ("module", "bad-module"),
        ("unknown", True),
    ],
)
def test_admission(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        spec(**{field: value})


@pytest.mark.parametrize(
    "hour,minute,expected", [(0, 59, False), (1, 0, True), (6, 59, True), (7, 0, False)]
)
def test_window(hour: int, minute: int, expected: bool) -> None:
    assert in_window(datetime(2026, 1, 1, hour, minute)) == expected


def test_queue_persistence_lock_and_pause(tmp_path: Path) -> None:
    q = Queue(tmp_path)
    identity = q.submit(spec())
    q.pause()
    assert q.claim() is None
    q.resume()
    assert q.claim()["id"] == identity
    assert q.claim() is None
    assert Queue(tmp_path).rows()[0]["status"] == "running"
    with pytest.raises(ValueError):
        q.update(identity, spec="wrong")
    with pytest.raises(ValueError):
        q.submit(spec(cwd="relative"))
    with worker_lock(tmp_path / "worker.lock"), pytest.raises(OSError):
        with worker_lock(tmp_path / "worker.lock"):
            pass


def test_disk_and_window_block_start(tmp_path: Path) -> None:
    q = Queue(tmp_path)
    q.submit(spec())
    with patch("training.jobs.runner.in_window", return_value=False):
        assert run(q) == []
    with patch("training.jobs.runner.disk_ok", return_value=False):
        assert run(q, manual=True) == []
    assert q.rows()[0]["status"] == "queued"
    with patch("training.jobs.runner.shutil.disk_usage") as usage:
        usage.return_value.free = 2999999999
        assert not disk_ok([tmp_path])
        usage.return_value.free = 3000000000
        assert disk_ok([tmp_path])


def test_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAVIS_JOB_DIR", str(tmp_path))
    monkeypatch.setenv("CLAVIS_JOB_DIGEST", "digest")
    c = Context()
    assert c.load() is None
    c.save({"step": 7})
    assert c.load() == {"step": 7}
    assert not c.stopping()
    (tmp_path / "stop").touch()
    assert c.stopping()
    monkeypatch.setenv("CLAVIS_JOB_DIGEST", "different")
    with pytest.raises(ValueError):
        Context().load()


def test_checkpoint_pause_resume_and_fifo(tmp_path: Path) -> None:
    q = Queue(tmp_path)
    first = q.submit(spec(config={"steps": 20}))
    second = q.submit(spec())

    def pause_after_checkpoint() -> None:
        for _ in range(100):
            if (tmp_path / first / "checkpoint.json").exists():
                q.pause()
                return
            time.sleep(0.02)

    watcher = threading.Thread(target=pause_after_checkpoint)
    watcher.start()
    with patch("training.jobs.runner.disk_ok", return_value=True):
        reports = run(q, manual=True)
    watcher.join(timeout=3)
    assert reports[0]["reason"] == "user-pause"
    step = json.loads((tmp_path / first / "checkpoint.json").read_text())["state"]["step"]
    assert 0 < step < 20
    assert q.rows()[1]["status"] == "queued"
    q.resume()
    with patch("training.jobs.runner.disk_ok", return_value=True):
        reports = run(q, manual=True)
    assert [r["jobId"] for r in reports] == [first, second]
    assert all(r["status"] == "succeeded" for r in reports)
    assert json.loads((tmp_path / first / "checkpoint.json").read_text())["state"]["total"] == 190
    assert len((tmp_path / "experiments.jsonl").read_text().splitlines()) == 6
    assert run(q, manual=True) == []


@pytest.mark.parametrize(
    "reason",
    [
        "ram-limit",
        "wall-limit",
        "window-closed",
        "disk-low",
        "command-failed",
        "monitor-error",
    ],
)
def test_limits(tmp_path: Path, reason: str) -> None:
    q = Queue(tmp_path)
    q.submit(
        spec(
            module="does_not_exist" if reason == "command-failed" else "training.jobs.example",
            config={"steps": 50},
        )
    )
    row = q.claim()
    assert row is not None
    if reason == "wall-limit":
        row["wall"] = 14400
    with (
        patch("training.jobs.runner.sample", wraps=sample) as sampler,
        patch("training.jobs.runner.in_window", return_value=reason != "window-closed"),
        patch("training.jobs.runner.disk_ok", return_value=reason != "disk-low"),
    ):
        if reason == "ram-limit":
            sampler.side_effect = lambda p, c: (3000000001, 1)
        if reason == "monitor-error":
            sampler.side_effect = psutil.AccessDenied()
        result = execute(q, row, manual=False)
    assert result["reason"] == reason


def test_recovery_and_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    q = Queue(tmp_path)
    identity = q.submit(spec())
    q.claim()
    recover(q)
    assert q.rows()[0]["status"] == "paused"
    for action in ("pause", "resume", "status"):
        monkeypatch.setattr(sys, "argv", ["jobs", "--root", str(tmp_path), action])
        assert cli.main() == 0
        assert capsys.readouterr().out
    request = tmp_path / "request.json"
    request.write_text(spec().model_dump_json())
    monkeypatch.setattr(sys, "argv", ["jobs", "--root", str(tmp_path), "submit", str(request)])
    assert cli.main() == 0
    assert identity in {r["id"] for r in q.rows()}
    monkeypatch.setattr(sys, "argv", ["jobs", "--root", str(tmp_path), "run"])
    with patch.object(cli, "run", return_value=[]):
        assert cli.main() == 0


def test_affinity_and_environment_inherit_to_child(tmp_path: Path) -> None:
    q = Queue(tmp_path)
    identity = q.submit(spec(config={"steps": 2, "probe": True}))
    # Positive unit scenario uses a synthetic disk budget; admission failure is tested separately.
    with patch("training.jobs.runner.disk_ok", return_value=True):
        report = run(q, manual=True)[0]
    assert report["status"] == "succeeded"
    probe = json.loads((tmp_path / identity / "probe.json").read_text())
    assert probe["cpus"] == probe["child"]["cpus"] == report["cpuAffinity"]
    assert int(probe["omp"]) == int(probe["child"]["omp"]) == report["cpuLimit"]
    assert probe["priority"] == probe["child"]["priority"]
    assert len(report["hostMemorySamples"]) > 1
    assert report["hostMemorySamples"][-1]["pagefileTotalBytes"] == 4_000_000_000
    assert report["meanLogicalCpusSampled"] >= 0
    assert report["peakLogicalCpusSampled"] >= 0


def test_cpu_budget_selection() -> None:
    from training.jobs.resources import allowed_cpus

    assert allowed_cpus(8, list(range(12))) == list(range(8))
    assert allowed_cpus(8, list(range(8))) == list(range(7))
    assert allowed_cpus(8, [2, 4]) == [2]
    for request, available in [(9, [0, 1]), (0, [0, 1]), (1, [0])]:
        with pytest.raises(ValueError):
            allowed_cpus(request, available)


def test_job_object_does_not_need_descendant_affinity_queries(tmp_path: Path) -> None:
    """Windows enforces affinity in-kernel; unguarded failures still stop jobs."""
    original = psutil.Process.cpu_affinity

    def affinity(process: psutil.Process, cpus: list[int] | None = None) -> list[int] | None:
        if cpus is None and process.pid != os.getpid():
            raise psutil.AccessDenied(process.pid)
        return original(process, cpus)

    q = Queue(tmp_path)
    q.submit(spec(config={"steps": 2}))
    with patch.object(psutil.Process, "cpu_affinity", affinity):
        report = run(q, manual=True)[0]
    if sys.platform == "win32":
        assert report["status"] == "succeeded"
    else:
        assert report["reason"] == "monitor-error"


def test_library_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from training.jobs.resources import THREAD_ENV, configure, configure_library

    torch = SimpleNamespace(set_num_threads=Mock(), set_num_interop_threads=Mock())
    configure_library("torch", torch, 4)
    torch.set_num_threads.assert_called_once_with(4)
    torch.set_num_interop_threads.assert_called_once_with(1)
    cv = SimpleNamespace(setNumThreads=Mock(), ocl=SimpleNamespace(setUseOpenCL=Mock()))
    configure_library("cv2", cv, 4)
    cv.setNumThreads.assert_called_once_with(4)
    original = Mock()
    ort = SimpleNamespace(InferenceSession=original, SessionOptions=SimpleNamespace)
    configure_library("onnxruntime", ort, 4)
    ort.InferenceSession("model", providers=["bad"])
    assert original.call_args.kwargs["sess_options"].intra_op_num_threads == 4
    assert original.call_args.kwargs["sess_options"].inter_op_num_threads == 1
    assert original.call_args.kwargs["providers"] == ["CPUExecutionProvider"]
    ort.InferenceSession("model", SimpleNamespace(), ["bad"], [{}])
    assert original.call_args.args[2] == ["CPUExecutionProvider"]

    class Booster:
        def __init__(self, params=None):
            self.params = params

        def reset_parameter(self, params):
            self.params = params

    class Dataset:
        def __init__(self, data, params=None):
            self.params = params

    lgb = SimpleNamespace(Booster=Booster, Dataset=Dataset)
    configure_library("lightgbm", lgb, 4)
    model = lgb.Booster({"n_jobs": 64, "device_type": "gpu"})
    assert model.params == {"num_threads": 4, "device_type": "cpu"}
    model.reset_parameter({"num_threads": 99})
    assert model.params["num_threads"] == 4
    assert lgb.Dataset([]).params["num_threads"] == 4
    monkeypatch.setenv("CLAVIS_CPU_LIMIT", "4")
    with patch("training.jobs.resources.importlib.util.find_spec", return_value=None):
        result = configure()
    assert result["torch"] == "not-installed"
    assert all(os.environ[name] == "4" for name in THREAD_ENV)
    with (
        patch("training.jobs.resources.configure_library") as injected,
        patch("training.jobs.resources.importlib.util.find_spec", return_value=True),
        patch("training.jobs.resources.importlib.import_module", return_value=cv),
    ):
        configure()
    assert injected.call_count == 4
    monkeypatch.setenv("CLAVIS_CPU_LIMIT", "9")
    with pytest.raises(ValueError):
        configure()


def test_memory_admission_and_telemetry(tmp_path: Path) -> None:
    from training.jobs.memory import can_start, snapshot

    actual = snapshot()
    assert actual["physicalTotalBytes"] > 0
    assert all(value >= 0 for value in actual.values())
    assert can_start({"commitAvailableBytes": 4_000_000_000}, 3_000_000_000)
    assert not can_start({"commitAvailableBytes": 3_999_999_999}, 3_000_000_000)
    queue = Queue(tmp_path)
    queue.submit(spec())
    with (
        patch("training.jobs.runner.snapshot", return_value={"commitAvailableBytes": 0}),
        patch("training.jobs.runner.subprocess.Popen") as spawn,
    ):
        result = execute(queue, queue.claim(), manual=True)
    spawn.assert_not_called()
    assert result["reason"] == "memory-low"
    assert result["status"] == "paused"
    assert result["hostMemorySamples"][0]["commitAvailableBytes"] == 0
