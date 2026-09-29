import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from eval.aggregate import aggregate
from eval.integrity.hashes import image_phash, phash_pixels, produce
from eval.integrity.leakage import check
from eval.report import evaluate
from eval.sealed import append_ledger, preflight, release
from eval.sealed.__main__ import main
from tests.eval.test_edges import note, score
from tests.eval.test_extended import page


def test_phash_and_hash_only_export(tmp_path: Path) -> None:
    flat = np.zeros((32, 32), dtype=np.float64)
    assert phash_pixels(flat) == phash_pixels(flat + 255) == "0" * 16
    axis = np.pi * (2 * np.arange(32) + 1) / 64
    single_frequency = 128 + 64 * np.outer(np.cos(axis), np.cos(2 * axis))
    # Analytic DCT has one positive AC coefficient at row 1, column 2.
    assert phash_pixels(single_frequency) == f"{1 << (63 - 10):016x}"
    pixels = np.random.default_rng(42).integers(0, 200, size=(32, 32)).astype(np.float64)
    assert phash_pixels(pixels) == phash_pixels(pixels + 17)
    with pytest.raises(ValueError):
        phash_pixels(np.zeros((3, 3)))
    Image.fromarray(pixels.astype(np.uint8)).save(tmp_path / "private-image.png")
    (tmp_path / "private-gt.musicxml").write_bytes(score(note() + note("D") + note("E")))
    local = {
        "role": "reserved",
        "samples": [
            {
                "sampleId": "opaque-001",
                "imagePath": "private-image.png",
                "musicXmlPath": "private-gt.musicxml",
                "voice": "1",
            }
        ],
    }
    result = produce(tmp_path, local)
    assert image_phash(tmp_path / "private-image.png") == result["samples"][0]["phash"]
    assert "private-image" not in json.dumps(result) and "private-gt" not in json.dumps(result)
    assert check({**result, "role": "train"}, result)[0]["excludedCount"] == 1
    assert produce(tmp_path, local) == result
    local["samples"][0]["voice"] = "absent"
    with pytest.raises(ValueError):
        produce(tmp_path, local)


def artifact() -> dict:
    return {
        "schema": "clavis-threshold-artifact-0.1",
        "engineBuildDigest": "a" * 64,
        "configDigest": "b" * 64,
        "devManifestDigest": "c" * 64,
        "models": [],
        "evaluatorVersion": "0.2.0",
        "reviewThresholds": {"event": 8500, "harmony": 8000, "measure": 8000},
        "frozenTargets": {"K1": {"ge10": 6}},
        "approvedBy": "orchestrator",
        "frozenAt": "2026-09-01",
    }


def test_artifact_preflight_is_not_an_execution() -> None:
    expected = artifact()
    receipt = {
        key: expected[key]
        for key in ("engineBuildDigest", "configDigest", "models", "evaluatorVersion")
    }
    assert preflight(expected, receipt)["execution"] == "NOT_RUN"
    receipt["engineBuildDigest"] = "d" * 64
    with pytest.raises(ValueError):
        preflight(expected, receipt)
    with pytest.raises(ValueError):
        preflight({}, receipt)
    expected["approvedBy"] = "worker"
    with pytest.raises(ValueError):
        preflight(expected, receipt)


def test_release_suppresses_small_groups_and_arbitrary_payload() -> None:
    report = aggregate([page(i, 1) for i in range(5)])
    report["pageDetails"] = ["private-title"]
    report["overall"]["metrics"]["K1"]["details"] = "private-lyrics"
    private = copy.deepcopy(report["slices"][0])
    private.update(pageCount=1, field="tier", value="R-TGT", extra="private-path")
    report["slices"].append(private)
    public = release(report, {"tier": ["SYN", "R-TGT"]})
    assert public["status"] == "AGGREGATE_ONLY"
    assert "private" not in json.dumps(public) and "R-TGT" not in json.dumps(public)
    assert len(public["slices"]) == 1
    report["overall"]["pageCount"] = 4
    assert release(report, {})["status"] == "SUPPRESSED"
    with pytest.raises(ValueError):
        release({**report, "paired": True}, {})


def test_error_histogram_only_releases_counts() -> None:
    result, pairs = evaluate(score(note()), score(note("D")))
    pages = [{**page(i, 1), "report": result} for i in range(5)]
    public = release(aggregate(pages), {}, [pairs] * 5)
    assert public["errorHistogram"] == {"events.pitch": 5}
    with pytest.raises(ValueError):
        release(aggregate(pages), {}, [pairs] * 4)


def test_ledger_two_runs_and_chain(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    entry = {
        "date": "2026-09-01",
        "sealedSetDigest": "a" * 64,
        "buildDigest": "b" * 64,
        "artifactDigest": "c" * 64,
        "resultDigest": "d" * 64,
        "verdict": "FAIL",
    }
    first = append_ledger(path, entry)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="duplicate"):
        append_ledger(path, entry)
    assert path.read_bytes() == original
    second = append_ledger(path, {**entry, "resultDigest": "e" * 64, "verdict": "PASS"})
    assert second["previousEntryDigest"] == first["entryDigest"] and second["officialRunIndex"] == 2
    with pytest.raises(ValueError, match="limit"):
        append_ledger(path, {**entry, "resultDigest": "f" * 64})
    path.write_text(path.read_text().replace('"verdict": "FAIL"', '"verdict": "PASS"'))
    with pytest.raises(ValueError, match="chain"):
        append_ledger(path, {**entry, "sealedSetDigest": "f" * 64})


def test_cli_no_private_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLAVIS_PRIVATE_ROOT", str(tmp_path))
    (tmp_path / "artifact.json").write_text(json.dumps(artifact()))
    (tmp_path / "observed.json").write_text(json.dumps(artifact()))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sealed",
            "preflight",
            "--artifact",
            "artifact.json",
            "--observed-digests",
            "observed.json",
            "--out",
            "receipt.json",
        ],
    )
    assert main() == 0
    assert main() == 1
    assert str(tmp_path) not in capsys.readouterr().out
