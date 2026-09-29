from __future__ import annotations

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from eval.integrity.hardcode_scan import manifest_ids, scan, scan_source
from eval.integrity.leakage import MELODY, PHASH, SCHEMA, check, melody_fingerprint, validate


@pytest.mark.parametrize(
    ("rule", "positive", "negative"),
    [
        ("H1", "x = '" + "a" * 16 + "'", "x = 'abc'"),
        ("H2", "x = 'known-page'", "x = 'new-page'"),
        ("H3", "if image.shape[0] == 1170: pass", "if image.width == expected: pass"),
        ("H4", "if measure_index >= 38: pass", "if measure_index >= count: pass"),
        ("H5", "x = 0.4137", "x = 0.125"),
        ("H6", "p = 'data/manifests/dev/a.json'", "p = 'configs/geometry/constants.yaml'"),
        ("H7", "from urllib import request", "import pathlib"),
        (
            "H8",
            "import numpy as np\nrng = np.random.default_rng()",
            "import numpy as np\nrng = np.random.default_rng(1)\nx = rng.random()",
        ),
        (
            "H9",
            "import time\nt = time.time()\nv = t + 1\nif v > 3: pass",
            "import time\nstart = time.perf_counter()\nprint(time.perf_counter() - start)",
        ),
    ],
)
def test_rules(rule: str, positive: str, negative: str) -> None:
    ids = frozenset({"known-page"})
    assert rule in {f.rule for f in scan_source(positive, "src/clavis/core/sample.py", ids)}
    assert not scan_source(negative, "src/clavis/core/sample.py", ids)


def test_scope_aliases_and_literals() -> None:
    assert not scan_source(
        "if not 0 < image.shape[0] * image.shape[1] <= budget:\n raise ValueError()",
        "training/degrade/x.py",
    )
    assert not scan_source(
        "if image.ndim == 3 and image.shape[2] != 3:\n raise ValueError()", "training/degrade/x.py"
    )
    assert scan_source("if image.shape[0] == 1170:\n raise ValueError()", "training/degrade/x.py")
    assert not scan_source("if page_index == 3: pass", "tests/test_example.py")
    assert not scan_source("x = 0.4137\nimport requests\np = 'eval/gt.json'", "eval/example.py")
    assert {
        f.rule
        for f in scan_source(
            "from random import choice as pick\nx = pick([1])", "training/data/x.py"
        )
    } == {"H8"}
    assert scan_source("x = 0x" + "a" * 16, "eval/x.py")[0].rule == "H1"
    assert (
        scan_source("from datetime import datetime as dt\nassert dt.now()", "eval/x.py")[0].rule
        == "H9"
    )
    assert scan_source("import eval.metrics", "src/clavis/x.py")[0].rule == "H6"
    assert scan_source("import secrets\nx = secrets.randbelow(4)", "eval/x.py")[0].rule == "H8"
    assert manifest_ids({"items": [{"pageId": "a", "imagePath": "dev/p.png"}]}) == {
        "a",
        "dev/p.png",
        "p.png",
    }


def test_repository_and_allowlist(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "eval").mkdir()
    (tmp_path / "eval/x.py").write_text("x = '" + "b" * 16 + "'", encoding="utf-8")
    (tmp_path / "data/manifests").mkdir(parents=True)
    (tmp_path / "data/manifests/test.json").write_text('{"pageId":"sample"}')
    report = scan(tmp_path)
    assert report["byOwner"] == {"W4": 1}
    allow = tmp_path / "configs/integrity/allowlist.yaml"
    allow.parent.mkdir(parents=True)
    entry = {
        **report["findings"][0],
        "reason": "synthetic test only",
        "approvedBy": ["W4", "orchestrator"],
    }
    allow.write_text(json.dumps([entry]))
    assert scan(tmp_path)["status"] == "PASS"
    entry["approvedBy"] = ["W4"]
    allow.write_text(json.dumps([entry]))
    with pytest.raises(ValueError, match="unapproved"):
        scan(tmp_path)
    entry["approvedBy"] = ["W4", "orchestrator"]
    entry["line"] = 9
    allow.write_text(json.dumps([entry]))
    with pytest.raises(ValueError, match="stale"):
        scan(tmp_path)
    out = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.integrity.hardcode_scan",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
        ],
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(out.read_text())["status"] == "ERROR"


def inventory(role: str, phash: int = 0, melody: int = 0) -> dict:
    return {
        "schema": SCHEMA,
        "role": role,
        "phashAlgorithm": PHASH,
        "melodyAlgorithm": MELODY,
        "samples": [
            {
                "sampleId": role,
                "imageSha256": ("a" if role == "train" else "b") * 64,
                "phash": f"{phash:016x}",
                "melodyMinhash": [f"{melody:064x}"] * 64,
            }
        ],
    }


def test_leakage_boundaries_and_admission() -> None:
    training = inventory("train")
    report, admitted = check(training, inventory("reserved", (1 << 6) - 1, 1))
    assert report["excludedCount"] == 1 and admitted["samples"] == []
    assert "reserved" not in json.dumps(report["conflicts"])
    assert check(training, inventory("reserved", (1 << 7) - 1, 1))[0]["status"] == "PASS"
    assert check(training, inventory("reserved", (1 << 7) - 1))[0]["status"] == "FAIL"
    empty = {**inventory("reserved"), "samples": []}
    assert check(training, empty)[0]["status"] == "NOT_RUN"
    assert check(training, empty)[1]["samples"] == []
    duplicate = inventory("reserved", (1 << 7) - 1, 1)
    duplicate["samples"][0]["imageSha256"] = "a" * 64
    assert check(training, duplicate)[0]["conflicts"][0]["reasons"] == ["image-sha256"]


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "role",
        "phashAlgorithm",
        "melodyAlgorithm",
        "phash",
        "melodyMinhash",
        "imageSha256",
        "sampleId",
        "duplicate",
        "path",
    ],
)
def test_inventory_fails_closed(mutation: str) -> None:
    value = inventory("train")
    if mutation in value:
        value[mutation] = None
    elif mutation == "duplicate":
        value["samples"] *= 2
    else:
        value["samples"][0][mutation] = None
    with pytest.raises(ValueError):
        validate(value, "train")


def test_melody_transposition_tempo_and_change() -> None:
    notes = [(60, Fraction(1)), (62, Fraction(1)), (64, Fraction(2)), (65, Fraction(1))]
    expected = melody_fingerprint(notes)
    assert expected == melody_fingerprint([(p + 5, d * 2) for p, d in notes])
    assert expected != melody_fingerprint([*notes[:-1], (66, Fraction(1))])
    assert len(melody_fingerprint(notes[:1])) == 64
    with pytest.raises(ValueError):
        melody_fingerprint([])


def test_leakage_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eval.integrity.leakage import main

    train, reserved, out, admitted = [
        tmp_path / n for n in ("train.json", "reserved.json", "report.json", "admitted.json")
    ]
    train.write_text(json.dumps(inventory("train")))
    reserved.write_text(json.dumps(inventory("reserved")))
    command = [
        sys.executable,
        "-m",
        "eval.integrity.leakage",
        "--train",
        str(train),
        "--reserved",
        str(reserved),
        "--out",
        str(out),
        "--admitted",
        str(admitted),
    ]
    monkeypatch.setattr(sys, "argv", [command[2], *command[3:]])
    assert main() == 1
    assert json.loads(admitted.read_text())["samples"] == []
    reserved.write_text("{}")
    assert main() == 1
    assert json.loads(out.read_text())["status"] == "ERROR"
