"""One overnight window, entirely driven by an isolated logical clock."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from training.jobs.clock import Clock
from training.jobs.runner import run
from training.jobs.store import Queue, worker_lock
from training.jobs.window import Window


class LogicalClock(Clock):
    def __init__(self, now):
        self.value = now
        self.waits = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.value += timedelta(hours=1)


@pytest.mark.parametrize("hour,opening_day", [(0, 9), (1, 9), (6, 9), (7, 10), (23, 10)])
def test_window_boundaries(hour, opening_day):
    w = Window.next(datetime(2026, 10, 9, hour))
    assert w.opens == datetime(2026, 10, opening_day, 1)
    assert w.closes == datetime(2026, 10, opening_day, 7)
    assert w.active(w.opens)
    assert not w.active(w.closes)


def test_wait_holds_lock_runs_only_window_and_waits_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("training.jobs.store.home", lambda: tmp_path / "jobs")
    queue = Queue(tmp_path / "queue")
    clock = LogicalClock(datetime(2026, 10, 9, 0))
    calls = []

    def claim():
        with pytest.raises(OSError), worker_lock():
            pass
        calls.append(clock.now())
        return None

    with (
        patch.object(queue, "claim", side_effect=claim),
        patch("training.jobs.runner.disk_ok", return_value=True),
    ):
        assert run(queue, wait=True, clock=clock) == []
    assert [d.hour for d in calls] == [1, 2, 3, 4, 5, 6]
    assert clock.now().hour == 7
    with worker_lock():
        pass


def test_busy_wait_exits_without_sleep(tmp_path, monkeypatch):
    monkeypatch.setattr("training.jobs.store.home", lambda: tmp_path / "jobs")
    clock = LogicalClock(datetime(2026, 10, 9, 0))
    with worker_lock(), pytest.raises(OSError):
        run(Queue(tmp_path), wait=True, clock=clock)
    assert clock.waits == []


def test_pause_ends_wait_and_manual_is_incompatible(tmp_path, monkeypatch):
    monkeypatch.setattr("training.jobs.store.home", lambda: tmp_path / "jobs")
    queue = Queue(tmp_path)
    queue.pause()
    clock = LogicalClock(datetime(2026, 10, 9, 0))
    assert run(queue, wait=True, clock=clock) == []
    assert clock.waits == []
    with pytest.raises(ValueError):
        run(queue, manual=True, wait=True, clock=clock)


def test_window_deadline_reaches_job_even_after_sleep_across_day(tmp_path, monkeypatch):
    monkeypatch.setattr("training.jobs.store.home", lambda: tmp_path / "jobs")
    queue = Queue(tmp_path)
    clock = LogicalClock(datetime(2026, 10, 9, 6))

    def execute(queue, row, manual, *, deadline_reached):
        assert not deadline_reached()
        clock.value += timedelta(days=1)
        assert deadline_reached()
        return {"status": "paused", "reason": "window-closed"}

    with (
        patch.object(queue, "claim", return_value={}),
        patch("training.jobs.runner.execute", execute),
        patch("training.jobs.runner.disk_ok", return_value=True),
    ):
        assert run(queue, wait=True, clock=clock)[0]["reason"] == "window-closed"
