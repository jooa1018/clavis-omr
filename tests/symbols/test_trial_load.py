"""Load exclusion and recorder lifecycle without performing model training."""

import pytest

from training.models.symbols import trial_load


@pytest.fixture
def quiet_host(monkeypatch):
    monkeypatch.setattr(
        trial_load, "sample", lambda process, cpu, diagnostics: cpu.update({0: 0.0})
    )
    host = {
        "systemLogicalCpus": 0.0,
        "availablePhysicalBytes": 8_000_000_000,
        "acConnected": True,
        "windowsPowerMode": "test",
    }
    monkeypatch.setattr(trial_load, "host_sample", lambda: dict(host))
    return host


def test_valid_load_keeps_ram_cpu_and_samples(quiet_host):
    with trial_load.observe_load() as result:
        pass
    assert result["comparisonEligible"]
    assert result["minimumAvailablePhysicalBytes"] == 8_000_000_000
    assert result["meanExternalLogicalCpus"] == 0
    assert result["samples"]


def test_external_load_excludes_trial_without_erasing_evidence(quiet_host):
    quiet_host["systemLogicalCpus"] = 2.0
    with trial_load.observe_load() as result:
        pass
    assert not result["comparisonEligible"]
    assert "external-mean-load" in result["invalidReasons"]
    assert result["samples"]


def test_sampler_error_fails_comparison_closed(quiet_host, monkeypatch):
    def fail():
        raise OSError("private diagnostic must not escape")

    monkeypatch.setattr(trial_load, "host_sample", fail)
    with trial_load.observe_load() as result:
        pass
    assert not result["comparisonEligible"]
    assert result["samplingErrors"] == ["OSError"]
    assert "private" not in repr(result)


def test_training_exception_is_preserved_and_collector_finishes(quiet_host):
    with pytest.raises(RuntimeError, match="training interrupted"):
        with trial_load.observe_load() as result:
            raise RuntimeError("training interrupted")
    assert result["samples"]
