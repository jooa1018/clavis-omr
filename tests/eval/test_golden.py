"""Independent hand-authored MusicXML expectations approved in ADR-012."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from eval.report import canonical, evaluate, write_report

FIXTURES = Path(__file__).parent / "fixtures/golden"
CASES = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


def inputs(name: str) -> tuple[bytes, bytes]:
    return tuple(
        (FIXTURES / f"{name}.{side}.musicxml").read_bytes() for side in ("reference", "prediction")
    )  # type: ignore[return-value]


@pytest.mark.parametrize("case", CASES, ids=[case["case"] for case in CASES])
def test_golden(case: dict[str, Any]) -> None:
    report, pairs = evaluate(*inputs(case["case"]))
    schema = json.loads((Path(__file__).parents[2] / "configs/eval/report.schema.json").read_text())
    Draft202012Validator(schema).validate(json.loads(canonical(report)))
    assert report["status"] == "evaluated"
    assert report["k1Operations"] == case["k1Operations"]
    assert report["metrics"]["K1"]["denominator"] == case["eventDenominator"]
    assert report["metrics"]["K1"]["value"] == pytest.approx(
        case["k1Operations"] / case["eventDenominator"] * 100
    )
    for metric, key in (
        ("pitchExactRate", "pitchNumerator"),
        ("durationExactRate", "durationNumerator"),
        ("measureExactMatchRate", "measureNumerator"),
    ):
        assert report["metrics"][metric]["numerator"] == case[key]
    assert report["metrics"]["pitchExactRate"]["denominator"] == case["pitchDenominator"]
    assert report["metrics"]["durationExactRate"]["denominator"] == case["eventDenominator"]
    assert pairs["measures"]


def test_specific_approved_diagnostics() -> None:
    report, _ = evaluate(*inputs("11-onset-cascade"))
    assert report["onsetOnlyMismatch"] == 2
    report, _ = evaluate(*inputs("10-lyric"))
    assert report["metrics"]["measureExactWithLyrics"]["value"] == 0
    assert report["metrics"]["K1-L"]["value"] == 100
    report, _ = evaluate(*inputs("09-chord-alias"))
    assert report["metrics"]["chordSymbolExactRate"]["value"] == 1
    report, _ = evaluate(*inputs("13-no-lyrics"))
    for metric in ("lyricExactRate", "K1-L"):
        assert report["metrics"][metric] == {"numerator": 0, "denominator": 0, "value": None}


@pytest.mark.parametrize("workers", [1, 4])
def test_three_runs_byte_identical(workers: int, tmp_path: Path) -> None:
    a, b = inputs("11-onset-cascade")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        runs = list(pool.map(lambda _: evaluate(a, b), range(3)))
    assert len({canonical(run) for run in runs}) == 1
    for i, (report, pairs) in enumerate(runs):
        write_report(report, pairs, tmp_path / str(i))
    for filename in ("report.json", "pairs.json", "report.md"):
        assert len({(tmp_path / str(i) / filename).read_bytes() for i in range(3)}) == 1
