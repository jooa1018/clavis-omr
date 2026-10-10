"""Measurement aggregation and frozen input checks; no performance budget test in CI."""

import hashlib
import json

import pytest

from training.models.staff.benchmark import verify_manifest
from training.models.staff.smoke import latency_summary


def test_first_and_repeated_do_not_overlap():
    result = latency_summary(
        [
            {"strip_ms": 100, "strip_ms_repeated": [100, 1, 2, 3, 4]},
            {"strip_ms": 200, "strip_ms_repeated": [200, 5, 6, 7, 8]},
        ]
    )
    assert result["first_call"] == {"count": 2, "p50_ms": 150, "p95_ms": 195}
    assert result["subsequent_calls"]["count"] == 8
    assert result["subsequent_calls"]["p50_ms"] == 4.5
    assert result["subsequent_calls"]["p95_ms"] == pytest.approx(7.65)
    assert latency_summary([])["first_call"]["p95_ms"] is None


def test_manifest_pins_bytes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "sample"
    sample.write_bytes(b"synthetic")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"files": [{"path": "sample", "sha256": hashlib.sha256(b"synthetic").hexdigest()}]}
        )
    )
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    verify_manifest(manifest, digest)
    sample.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        verify_manifest(manifest, digest)
    with pytest.raises(ValueError, match="manifest changed"):
        verify_manifest(manifest, "0" * 64)
