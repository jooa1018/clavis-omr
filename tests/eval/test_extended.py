"""Independent musical mutations and public-output/statistical counterexamples."""

import copy
import json
import sys
from fractions import Fraction
from itertools import permutations
from pathlib import Path

import pytest

from eval.aggregate import aggregate
from eval.align import add, assignment
from eval.report import evaluate
from tests.eval.test_edges import note, score

BASE = note() + note("D")
REST = "<note><rest/><duration>1</duration></note>"
CHORD = "<harmony id='h'><root><root-step>C</root-step></root><kind>major</kind></harmony>"
LYRIC = '<lyric number="1"><text>가</text></lyric>'
VOLTA = '<barline location="left"><ending number="1" type="start"/></barline>'
VOICE = (
    note("C", extra="<voice>1</voice>")
    + "<backup><duration>1</duration></backup>"
    + note("G", extra="<voice>2</voice>")
)
MUTATIONS = [
    ("pitch-step", score(BASE), score(note("B") + note("D")), 1, "pitchExactRate", 1),
    (
        "pitch-alter",
        score(BASE),
        score(BASE.replace("<step>C</step>", "<step>C</step><alter>1</alter>")),
        1,
        "pitchExactRate",
        1,
    ),
    (
        "pitch-octave",
        score(BASE),
        score(BASE.replace("<octave>4</octave>", "<octave>5</octave>", 1)),
        1,
        "pitchExactRate",
        1,
    ),
    ("duration", score(BASE), score(note(duration="2") + note("D")), 1, "durationExactRate", 1),
    (
        "dot-add",
        score(BASE),
        score(note(duration="1.5", extra="<dot/>") + note("D")),
        1,
        "durationExactRate",
        1,
    ),
    (
        "dot-remove",
        score(note(duration="1.5", extra="<dot/>") + note("D")),
        score(BASE),
        1,
        "durationExactRate",
        1,
    ),
    ("event-delete", score(BASE), score(note("D")), 1, "pitchExactRate", 1),
    ("event-insert", score(BASE), score(BASE + note("E")), 1, "pitchExactRate", 2),
    ("rest-to-note", score(REST + note("D")), score(BASE), 1, "restExactRate", 0),
    ("note-to-rest", score(BASE), score(REST + note("D")), 1, "pitchExactRate", 1),
    (
        "tie-start",
        score(BASE),
        score(note(extra='<tie type="start"/>') + note("D")),
        1,
        "tieExactRate",
        0,
    ),
    (
        "tie-stop",
        score(BASE),
        score(note(extra='<tie type="stop"/>') + note("D")),
        1,
        "tieExactRate",
        0,
    ),
    (
        "voice-permutation",
        score(VOICE),
        score(
            VOICE.replace("<voice>1", "<voice>x")
            .replace("<voice>2", "<voice>1")
            .replace("<voice>x", "<voice>2")
        ),
        0,
        "measureExactMatchRate",
        1,
    ),
    ("measure-split", score(BASE), score(note(), note("D")), 1, "measureExactMatchRate", 0),
    ("measure-merge", score(note(), note("D")), score(BASE), 1, "measureExactMatchRate", 0),
    (
        "key",
        score(BASE),
        score(BASE).replace(b"<fifths>0", b"<fifths>1"),
        1,
        "keySignatureExactRate",
        0,
    ),
    (
        "time",
        score(BASE),
        score(BASE).replace(b"<beats>4", b"<beats>3"),
        1,
        "timeSignatureExactRate",
        0,
    ),
    (
        "clef",
        score(BASE),
        score(BASE).replace(b"<sign>G", b"<sign>F"),
        1,
        "measureExactMatchRate",
        0,
    ),
    (
        "chord-value",
        score(CHORD + BASE),
        score(CHORD.replace("major", "minor") + BASE),
        1,
        "chordSymbolExactRate",
        0,
    ),
    (
        "chord-position",
        score(CHORD + BASE),
        score(note() + CHORD + note("D")),
        1,
        "chordSymbolExactRate",
        0,
    ),
    (
        "lyric-replace",
        score(note(extra=LYRIC)),
        score(note(extra=LYRIC.replace("가", "나"))),
        0,
        "lyricExactRate",
        0,
    ),
    ("lyric-delete", score(note(extra=LYRIC)), score(note()), 0, "lyricExactRate", 0),
    ("volta-delete", score(VOLTA + BASE), score(BASE), 0, "measureExactMatchRate", 0),
    (
        "onset-only",
        score(BASE),
        score("<forward><duration>1</duration></forward>" + BASE),
        0,
        "measureExactMatchRate",
        0,
    ),
    (
        "compound-object",
        score(note()),
        score(note("D", "2", '<tie type="start"/>')),
        1,
        "durationExactRate",
        0,
    ),
    (
        "grace-pitch",
        score("<note><grace/><pitch><step>C</step><octave>4</octave></pitch></note>" + BASE),
        score("<note><grace/><pitch><step>D</step><octave>4</octave></pitch></note>" + BASE),
        1,
        "graceExact",
        0,
    ),
    (
        "rhythm-to-note",
        score("<note><unpitched/><duration>1</duration><notehead>slash</notehead></note>"),
        score(note()),
        1,
        "durationExactRate",
        1,
    ),
]


@pytest.mark.parametrize(
    ("name", "reference", "prediction", "operations", "metric", "correct"),
    MUTATIONS,
    ids=[m[0] for m in MUTATIONS],
)
def test_mutation(
    name: str, reference: bytes, prediction: bytes, operations: int, metric: str, correct: int
) -> None:
    report, _ = evaluate(reference, prediction)
    assert report["status"] == "evaluated", name
    assert report["k1Operations"] == operations
    assert report["metrics"][metric]["numerator"] == correct
    perfect, _ = evaluate(reference, reference)
    assert perfect["k1Operations"] == 0
    assert perfect["metrics"]["measureExactMatchRate"]["value"] == 1


def test_voice_assignment_independent_optimum() -> None:
    for size in range(1, 5):
        costs = [
            [((i * 3 + j * 7) % 5, (i + j) % 2, Fraction(i * j, 3)) for j in range(size)]
            for i in range(size)
        ]

        def cost(
            order: tuple[int, ...] | list[int], matrix: list = costs
        ) -> tuple[int, int, Fraction]:
            result = (0, 0, Fraction(0))
            for i, j in enumerate(order):
                result = add(result, matrix[i][j])
            return result

        assert cost(assignment(costs)) == min(cost(order) for order in permutations(range(size)))
    reordered = (
        note("G", extra="<voice>8</voice>")
        + "<backup><duration>1</duration></backup>"
        + note("C", extra="<voice>9</voice>")
    )
    report, _ = evaluate(score(VOICE), score(reordered))
    assert report["k1Operations"] == 0
    assert report["metrics"]["measureExactMatchRate"]["value"] == 1
    report, _ = evaluate(score(VOICE), score(note("C")))
    assert report["k1Operations"] == 1


def confidence(*flagged: str, key: bool = False) -> bytes:
    entries = [
        {
            "id": name,
            "kind": "measure" if name == "m" else "event",
            "confidenceBp": 5000,
            "flagged": name in flagged,
        }
        for name in ("m", "n")
    ]
    if key:
        entries.append(
            {
                "id": "k",
                "kind": "key",
                "confidenceBp": 5000,
                "flagged": "k" in flagged,
                "parentId": "m",
                "path": "attributes[1]/key[1]",
            }
        )
    return json.dumps({"schema": "clavis-confidence-0.1", "elements": entries}).encode()


def identified(xml: bytes) -> bytes:
    return xml.replace(b'<measure number="0"', b'<measure id="m" number="0"').replace(
        b"<note>", b'<note id="n">', 1
    )


@pytest.mark.parametrize("flagged", [(), ("n",), ("m",), ("m", "n")])
def test_k2_element_or_measure_flag(flagged: tuple[str, ...]) -> None:
    report, _ = evaluate(
        score(note()),
        identified(score(note("D", "2", '<tie type="start"/>'))),
        confidence(*flagged),
    )
    assert report["status"] == "evaluated"
    assert report["metrics"]["K2"]["numerator"] == (0 if flagged else 1)
    assert report["metrics"]["errorRecall"]["denominator"] == 1
    assert report["metrics"]["flagPrecision"]["numerator"] == len(flagged)


def test_k2_missing_lyrics_onset_and_attribute_path() -> None:
    report, _ = evaluate(score(BASE), identified(score(note("D"))), confidence("m"))
    assert report["metrics"]["K2"]["numerator"] == 0
    report, _ = evaluate(
        score(note(extra=LYRIC)),
        identified(score("<forward><duration>1</duration></forward>" + note())),
        confidence(),
    )
    assert report["metrics"]["K2"]["numerator"] == 0
    assert report["onsetOnlyMismatch"] == 1
    prediction = identified(score(note()).replace(b"<fifths>0", b"<fifths>2"))
    report, _ = evaluate(score(note()), prediction, confidence("k", key=True))
    assert report["metrics"]["K2"]["numerator"] == 0
    assert evaluate(score(note()), prediction, b"{}")[0]["status"] == "evaluation-unsupported"


def page(index: int, numerator: int, denominator: int = 2) -> dict:
    return {
        "pageId": f"p{index}",
        "metadata": {
            "tier": "SYN",
            "devPartition": "Dev-Check",
            "sourceKind": "digital-pdf",
            "captureChannel": "synthetic",
            "engravingTool": "test",
            "musicFont": "test",
            "measuredInterlinePx": 10,
            "notationFeatures": ["ties"],
            "chordDensity": "none",
        },
        "report": {
            "status": "evaluated",
            "evaluatorVersion": "test",
            "evaluatorDigest": "synthetic",
            "protocol": "clavis-evaluation-1.1",
            "metrics": {
                "K1": {
                    "numerator": numerator,
                    "denominator": denominator,
                    "value": numerator / denominator * 100 if denominator else None,
                }
            },
        },
    }


def test_bootstrap_paired_and_slices() -> None:
    records = [page(i, 1) for i in range(5)]
    same = aggregate(records, records)
    assert same == aggregate(list(reversed(records)), records)
    assert same["overall"]["metrics"]["K1"]["ci95"] == [0.0, 0.0]
    assert same["overall"]["insufficientSample"] is False
    better = aggregate(records, [page(i, 0) for i in range(5)])
    assert better["overall"]["metrics"]["K1"]["ci95"] == [-50.0, -50.0]
    assert {s["field"] for s in better["slices"]} >= {
        "tier",
        "interline",
        "two-voices",
        "chordDensity",
        "lyrics-ko",
    }
    single = aggregate([page(0, 0, 0)])
    assert single["overall"]["insufficientSample"] is True
    assert single["overall"]["metrics"]["K1"]["ci95"] is None
    assert single["overall"]["metrics"]["K1"]["undefinedReplicates"] == 10000
    with pytest.raises(ValueError, match="complete page set"):
        aggregate(records, records[:-1])
    bad = copy.deepcopy(records)
    bad[0]["report"]["status"] = "evaluation-unsupported"
    assert aggregate(bad)["overall"]["status"] == "PARTIAL"
    assert aggregate(bad)["overall"]["metrics"] == {}


def test_k2_rejects_unresolved_and_duplicate_targets() -> None:
    xml = identified(score(note()))
    assert (
        evaluate(score(note()), xml, confidence().replace(b'"n"', b'"absent"'))[0]["status"]
        == "evaluation-unsupported"
    )
    assert evaluate(score(BASE), xml + b" ", b"bad-json")[0]["status"] == "evaluation-unsupported"
    empty = b'{"schema":"clavis-confidence-0.1","elements":[]}'
    result, _ = evaluate(score(note(), note("D")), score(note()), empty)
    assert result["metrics"]["K2"]["numerator"] == result["k1Operations"]
    duplicate = xml.replace(b'<part id="P">', b'<part id="m">')
    assert evaluate(score(note()), duplicate, confidence())[0]["reason"] == "duplicate-xml-id"


def test_aggregate_metadata_and_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eval.aggregate import main

    records = [page(1, 1)]
    bad = copy.deepcopy(records)
    bad[0]["metadata"]["tier"] = "R-TGT"
    with pytest.raises(ValueError, match="metadata"):
        aggregate(records, bad)
    with pytest.raises(ValueError, match="duplicate"):
        aggregate(records * 2)
    bad = copy.deepcopy(records)
    bad[0]["report"]["evaluatorVersion"] = "different"
    with pytest.raises(ValueError, match="evaluator"):
        aggregate(records, bad)
    missing = copy.deepcopy(records)
    missing[0]["report"]["metrics"] = {}
    assert aggregate(records, missing)["overall"]["metrics"]["K1"]["status"] == "NOT_RUN"
    src, out = tmp_path / "pages.json", tmp_path / "aggregate.json"
    src.write_text(json.dumps(records))
    monkeypatch.setattr(sys, "argv", ["aggregate", str(src), "--out", str(out)])
    assert main() == 0
    assert json.loads(out.read_text())["overall"]["replicates"] == 10000
    src.write_text("[]")
    assert main() == 1
