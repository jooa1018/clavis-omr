"""Transient child races do not abort a job or leak exception text."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest

from training.jobs.monitor import Diagnostics, enforce_affinity, sample


def process(pid):
    item = Mock(pid=pid)
    item.oneshot.side_effect = nullcontext
    item.memory_info.return_value = SimpleNamespace(rss=10)
    item.num_threads.return_value = 2
    item.cpu_times.return_value = SimpleNamespace(user=1.0, system=0.5)
    item.children.return_value = []
    item.cpu_affinity.return_value = [0, 1]
    return item


@pytest.mark.parametrize("kind", [psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess])
@pytest.mark.parametrize("site", ["memory_info", "num_threads", "cpu_times"])
def test_child_sample_failure_is_atomic_and_diagnostic(kind, site):
    root, child, healthy = process(1), process(2), process(3)
    root.children.return_value = [child, healthy]
    getattr(child, site).side_effect = kind(2, msg="PRIVATE_SENTINEL")
    cpu = {2: 0.25}
    diagnostics = Diagnostics()
    assert sample(root, cpu, diagnostics) == (20, 4)
    assert cpu == {1: 1.5, 2: 0.25, 3: 1.5}
    assert diagnostics.report() == [
        {
            "exceptionType": kind.__name__,
            "site": "sample." + site,
            "skippedChild": True,
            "count": 1,
        }
    ]
    sample(root, cpu, diagnostics)
    assert diagnostics.report()[0]["count"] == 2
    assert "PRIVATE_SENTINEL" not in str(diagnostics.report())


def test_root_failure_is_not_hidden():
    root = process(1)
    root.memory_info.side_effect = psutil.AccessDenied(1)
    diagnostics = Diagnostics()
    with pytest.raises(psutil.AccessDenied):
        sample(root, {}, diagnostics)
    assert diagnostics.report()[0]["skippedChild"] is False


@pytest.mark.parametrize("kind", [psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess])
def test_child_affinity_failure_does_not_abort(kind):
    root, child = process(1), process(2)
    root.children.return_value = [child]
    child.cpu_affinity.side_effect = kind(2)
    diagnostics = Diagnostics()
    enforce_affinity(root, [0, 1], diagnostics)
    assert diagnostics.report()[0]["site"] == "affinity.child"


def test_affinity_is_restored():
    root, child = process(1), process(2)
    root.children.return_value = [child]
    child.cpu_affinity.return_value = [0, 1, 2]
    enforce_affinity(root, [0, 1], Diagnostics())
    child.cpu_affinity.assert_called_with([0, 1])


def test_enumeration_failure_remains_fatal():
    root = process(1)
    root.children.side_effect = psutil.AccessDenied(1)
    with pytest.raises(psutil.AccessDenied):
        sample(root, {})
