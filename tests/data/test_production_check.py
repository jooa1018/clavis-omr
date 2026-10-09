import copy
import json

import pytest

from training.data import production_check as checker
from training.data.production_audit import audit


class MemoryContext:
    def __init__(self):
        self.state = None
        self.interrupt = False

    def save(self, state):
        self.state = copy.deepcopy(state)

    def load(self):
        return copy.deepcopy(self.state)

    def stopping(self):
        return self.interrupt and self.state is not None and self.state["next"] >= 2


def test_empirical_preview_resumes_to_identical_report(tmp_path, monkeypatch):
    profile, notation, rhythm, target = checker.load()
    profile["block_acceptance"]["songs"] = 12
    rhythm.update(fit_iterations=10, mixed_patterns_per_grouping=2)
    monkeypatch.setattr(checker, "load", lambda: (profile, notation, rhythm, target))
    complete, interrupted = MemoryContext(), MemoryContext()
    direct = checker.run(tmp_path / "direct", "train-audit-test", 6, complete)
    interrupted.interrupt = True
    assert checker.run(tmp_path / "resumed", "train-audit-test", 6, interrupted) is None
    interrupted.interrupt = False
    resumed = checker.run(tmp_path / "resumed", "train-audit-test", 6, interrupted)
    assert resumed == direct
    assert (tmp_path / "direct/report.json").read_bytes() == (
        tmp_path / "resumed/report.json"
    ).read_bytes()
    assert (tmp_path / "direct/fitted-profile.json").read_bytes() == (
        tmp_path / "resumed/fitted-profile.json"
    ).read_bytes()
    assert direct["status"] == "PREVIEW"
    assert direct["state"]["invalid"] == {}
    assert direct["training_admission"] == "BLOCKED_OR_003"
    assert json.loads((tmp_path / "direct/report.json").read_bytes())["state"]["next"] == 6
    for xml in (tmp_path / "direct").glob("*.musicxml"):
        bad = xml.read_text(encoding="utf-8").replace("<duration>", "<duration>9", 1)
        with pytest.raises(ValueError):
            audit(bad)


def test_target_digest_checked_before_fit(tmp_path, monkeypatch):
    import yaml

    profile, _, _, _ = checker.load()
    profile["rhythm"]["target_sha256"] = "0" * 64
    original = yaml.safe_load

    def changed(text):
        value = original(text)
        return profile if "mode_weights" in value else value

    monkeypatch.setattr(yaml, "safe_load", changed)
    with pytest.raises(ValueError, match="digest"):
        checker.load()


def test_source_digest_normalizes_line_endings_and_detects_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "training/data").mkdir(parents=True)
    (tmp_path / "configs/data").mkdir(parents=True)
    source = tmp_path / "training/data/example.py"
    source.write_bytes(b"a = 1\n")
    (tmp_path / "uv.lock").write_bytes(b"version = 1\n")
    original = checker.source_digest()
    source.write_bytes(b"a = 1\r\n")
    assert checker.source_digest() == original
    source.write_bytes(b"a = 2\n")
    assert checker.source_digest() != original


def test_cli_rejects_stale_queued_source_before_generation(tmp_path, monkeypatch):
    import sys

    (tmp_path / "request.json").write_text(
        json.dumps({"config": {"sourceDigest": "0" * 64}}), encoding="utf-8"
    )
    context = MemoryContext()
    context.directory = tmp_path
    monkeypatch.setattr(checker, "Context", lambda: context)
    monkeypatch.setattr(
        sys, "argv", ["check", "--output", str(tmp_path / "out"), "--seed", "train-stale"]
    )
    monkeypatch.setattr(checker, "run", lambda *args: pytest.fail("stale source executed"))
    with pytest.raises(ValueError, match="source digest"):
        checker.main()
