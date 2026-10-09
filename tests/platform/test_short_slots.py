"""Cross-process slot limits, queue exclusion and bounded execution."""

import json
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from training.jobs import short, slots, store
from training.jobs.runner import execute


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "home", lambda: tmp_path / "jobs")


def test_three_slots_and_queue_exclusion() -> None:
    assert slots.slot_count() == 3
    with ExitStack() as stack:
        assert [stack.enter_context(slots.short_slot()) for _ in range(3)] == [0, 1, 2]
        with pytest.raises(OSError), slots.short_slot():
            pass
        with pytest.raises(OSError), store.worker_lock():
            pass
        with pytest.raises(OSError):
            slots.configure_slots(1)
    with store.worker_lock(), pytest.raises(OSError), slots.short_slot():
        pass
    slots.configure_slots(1)
    with slots.short_slot(), pytest.raises(OSError), slots.short_slot():
        pass
    slots.configure_slots(4)
    with ExitStack() as stack:
        assert len([stack.enter_context(slots.short_slot()) for _ in range(4)]) == 4


def test_cross_process_crash_releases_slot(tmp_path: Path) -> None:
    slots.configure_slots(1)
    code = (
        "import sys; from pathlib import Path; from training.jobs import store,slots; "
        "store.home=lambda:Path(sys.argv[1])/'jobs'; "
        "lease=slots.short_slot(); lease.__enter__(); "
        "print('ready',flush=True); input()"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(OSError), slots.short_slot():
            pass
        with pytest.raises(OSError), store.worker_lock():
            pass
    finally:
        child.kill()
        child.communicate(timeout=10)
    with slots.short_slot() as index:
        assert index == 0
    with store.worker_lock():
        pass


def test_task_exception_releases_slot() -> None:
    with pytest.raises(RuntimeError), slots.short_slot():
        raise RuntimeError("synthetic task error")
    with store.worker_lock():
        pass


@pytest.mark.parametrize("count", [0, -1, True])
def test_invalid_configuration(count: int, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        slots.configure_slots(count)
    (tmp_path / "short-slots.json").write_text(json.dumps({"slots": count}))
    with pytest.raises(ValueError):
        slots.slot_count()


@pytest.mark.parametrize(
    "values", [{"items": 101}, {"items": -1}, {"wall_seconds": 601}, {"wall_seconds": 0}]
)
def test_request_limits(values: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        short.run_short("training.jobs.example", [], **values)


def test_execution_reuses_queue_limits() -> None:
    with patch.object(short, "execute", wraps=execute) as runner:
        result = short.run_short("training.jobs.example", [], wall_seconds=30, items=100)
    spec = json.loads(runner.call_args.args[1]["spec"])
    assert spec["threads"] == 2
    assert spec["ram_bytes"] == 3_000_000_000
    assert spec["wall_seconds"] == 30
    assert result["status"] == "succeeded"
    assert 1 <= result["cpuLimit"] <= 2
    assert "cwd" not in result
    with store.worker_lock():
        pass


def test_cli_and_busy_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["short", "configure", "--slots", "2"])
    assert short.main() == 0
    monkeypatch.setattr(sys, "argv", ["short", "status"])
    assert short.main() == 0
    monkeypatch.setattr(sys, "argv", ["short", "run", "--items", "101", "pytest"])
    assert short.main() == 2
    monkeypatch.setattr(sys, "argv", ["short", "run", "pytest"])
    with store.worker_lock():
        assert short.main() == 75
    for status, code in [("succeeded", 0), ("failed", 1)]:
        with patch.object(short, "run_short", return_value={"status": status}):
            assert short.main() == code
    assert "slot-or-worker-unavailable" in capsys.readouterr().out
