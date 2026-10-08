import copy
import json
import sys
from pathlib import Path

import pytest

from eval.aggregate import slices
from eval.integrity.protection import admit, inventories, recheck, reverse_screen
from eval.sealed.__main__ import main
from tests.eval.test_extended import page
from tests.eval.test_integrity import inventory


def bundle() -> dict:
    return {
        "schema": "clavis-protected-set-1",
        "version": 1,
        "sources": {
            name: {"complete": True, "inventory": inventory("reserved", (1 << 64) - 1, 1)}
            for name in ("eval-pool", "lieder")
        },
    }


def test_admission_no_sealed_dependency_and_incomplete_rejection() -> None:
    source = bundle()
    report, receipt = admit(inventory("train"), source)
    assert report["status"] == "PASS" and report["admittedCount"] == 1
    assert len(receipt["protectedSetDigest"]) == 64
    empty = {**inventory("train"), "samples": []}
    assert admit(empty, source)[0]["status"] == "NOT_RUN"
    for change in ("sealed", "missing", "incomplete", "empty"):
        broken = copy.deepcopy(source)
        if change == "sealed":
            broken["sources"]["sealed"] = broken["sources"]["lieder"]
        elif change == "missing":
            del broken["sources"]["lieder"]
        elif change == "incomplete":
            broken["sources"]["lieder"]["complete"] = False
        else:
            broken["sources"]["lieder"]["inventory"]["samples"] = []
        with pytest.raises(ValueError):
            inventories(broken)


def test_growth_recheck_contamination_and_one_percent_boundary() -> None:
    train = inventory("train")
    train["samples"] = [
        {**train["samples"][0], "sampleId": f"train-{i}", "melodyMinhash": [f"{i + 10:064x}"] * 64}
        for i in range(100)
    ]
    _, receipt = admit(train, bundle())
    source = bundle()
    source["version"] = 2
    dev = inventory("reserved", (1 << 64) - 1, 10)
    dev["samples"][0]["sampleId"] = "dev-page"
    source["sources"]["dev-melodies"] = {"complete": True, "inventory": dev}
    song_ids = {s["sampleId"]: s["sampleId"] for s in train["samples"]}
    frozen = copy.deepcopy(receipt)
    result = recheck(receipt, source, song_ids)
    assert result["status"] == "PASS" and result["newlyExcludedSongCount"] == 1
    assert result["contaminatedDevPageIds"] == ["dev-page"] and receipt == frozen
    dev["samples"].append(
        {**dev["samples"][0], "sampleId": "dev-two", "melodyMinhash": [f"{11:064x}"] * 64}
    )
    assert recheck(receipt, source, song_ids)["status"] == "ESCALATE"
    with pytest.raises(ValueError):
        recheck(receipt, source, {})
    with pytest.raises(ValueError):
        recheck(receipt, bundle(), song_ids)
    record = page(0, 1)
    record["metadata"]["contaminated"] = True
    assert slices(record)["contamination"] == "contaminated"


def test_reverse_count_only_and_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = inventory("reserved", (1 << 64) - 1, 0)
    dev = inventory("reserved", (1 << 64) - 1, 1)
    report, accepted = reverse_screen(candidate, inventory("train"), dev)
    assert report == {"candidateCount": 1, "excludedCount": 1}
    assert accepted["samples"] == []
    assert set(report) == {"candidateCount", "excludedCount"}
    monkeypatch.setenv("CLAVIS_PRIVATE_ROOT", str(tmp_path))
    for name, data in (("candidate", candidate), ("train", inventory("train")), ("dev", dev)):
        (tmp_path / f"{name}.json").write_text(json.dumps(data))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sealed",
            "reverse-screen",
            "--candidates",
            "candidate.json",
            "--frozen-train",
            "train.json",
            "--frozen-dev",
            "dev.json",
            "--local-accepted",
            "local/accepted.json",
            "--out",
            "counts.json",
        ],
    )
    assert main() == 0
    assert json.loads((tmp_path / "counts.json").read_text()) == report
    assert main() == 1
