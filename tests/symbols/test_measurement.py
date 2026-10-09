"""Queue provenance and interrupted-trial recovery without optional trainers."""

import hashlib
import json

import numpy as np
import pytest

from training.jobs.context import Context
from training.models.symbols import measurement


@pytest.fixture
def queued(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    np.savez_compressed(data / "patches.npz", patches=np.zeros((8, 2, 48, 48), np.uint8))
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "purpose": "measurement-only",
                "threads": [4, 8],
                "sample_sizes": [8],
                "repeats": 2,
                "fcn_batch": 8,
                "seed": 6,
                "memory_configuration": "test",
            }
        )
    )
    manifest = {
        "purpose": "measurement-only",
        "patch_shape": [2, 48, 48],
        "patches_sha256": hashlib.sha256((data / "patches.npz").read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
    }
    (data / "manifest.json").write_text(json.dumps(manifest))
    request = {
        "config": {},
        "data_digest": hashlib.sha256((data / "manifest.json").read_bytes()).hexdigest(),
    }
    (tmp_path / "request.json").write_text(json.dumps(request))
    monkeypatch.setenv("CLAVIS_JOB_DIR", str(tmp_path))
    monkeypatch.setenv("CLAVIS_JOB_DIGEST", "0" * 64)
    monkeypatch.setenv("CLAVIS_CPU_LIMIT", "4")
    monkeypatch.setattr(measurement, "version", lambda name: "test")
    return data, config, tmp_path


def test_completed_trials_survive_interruption_and_no_weights_are_written(queued, monkeypatch):
    data, config, directory = queued
    seeds = []

    def trial(patches, cfg, seed):
        seeds.append(seed)
        if len(seeds) == 2:
            raise InterruptedError("simulated process interruption")
        return {"fit_seconds": 1, "effective_threads": 4, "cpu_only": True}

    monkeypatch.setattr(measurement, "fcn_trial", trial)
    with pytest.raises(InterruptedError):
        measurement.run(data, config, "fcn")
    assert len(Context().load()["trials"]) == 1
    result = measurement.run(data, config, "fcn")
    assert seeds == [6, 7, 7]
    assert len(result["trials"]) == 2
    assert result["purpose"] == "measurement-only"
    assert not list(directory.rglob("*.pt"))
    assert not result["probe"]


@pytest.mark.parametrize("tamper", ["patches", "config", "manifest", "cpu", "code"])
def test_queue_guard_rejects_changed_inputs_before_fitting(queued, monkeypatch, tamper):
    data, config, directory = queued
    monkeypatch.setattr(measurement, "fcn_trial", lambda *args: pytest.fail("must not train"))
    if tamper == "patches":
        (data / "patches.npz").write_bytes(b"corrupt")
    elif tamper == "config":
        config.write_text(config.read_text() + " ")
    elif tamper == "manifest":
        (data / "manifest.json").write_text((data / "manifest.json").read_text() + " ")
    elif tamper == "cpu":
        monkeypatch.setenv("CLAVIS_CPU_LIMIT", "2")
    else:
        path = directory / "request.json"
        request = json.loads(path.read_text())
        request["config"]["measurement_code_sha256"] = "f" * 64
        path.write_text(json.dumps(request))
    with pytest.raises(ValueError):
        measurement.run(data, config, "fcn")


def test_stop_request_leaves_pending_trial_unstarted(queued, monkeypatch):
    data, config, directory = queued
    (directory / "stop").touch()
    monkeypatch.setattr(measurement, "fcn_trial", lambda *args: pytest.fail("must not train"))
    assert measurement.run(data, config, "fcn")["trials"] == []
