"""Semantic counterexamples, safety bounds and independent DP optimality checks."""

import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest

from eval.align import Budget, add, align_items, event_errors
from eval.policy import limit
from eval.projection import project
from eval.projection.model import EvaluationUnsupported, Event
from eval.report import canonical, evaluate

ATTRS = (
    "<attributes><divisions>1</divisions><key><fifths>0</fifths></key>"
    "<time><beats>4</beats><beat-type>4</beat-type></time>"
    "<clef><sign>G</sign><line>2</line></clef></attributes>"
)


def note(step: str = "C", duration: str = "1", extra: str = "") -> str:
    return (
        f"<note><pitch><step>{step}</step><octave>4</octave></pitch>"
        f"<duration>{duration}</duration>{extra}</note>"
    )


def score(*bodies: str) -> bytes:
    measures = "".join(
        f'<measure number="{i}">{ATTRS}{body}</measure>' for i, body in enumerate(bodies)
    )
    return (
        f'<score-partwise version="4.0"><part-list><score-part id="P">'
        f"<part-name>Fixture</part-name></score-part></part-list>"
        f'<part id="P">{measures}</part></score-partwise>'
    ).encode()


@pytest.mark.parametrize("reverse", [False, True])
def test_barline_split_merge(reverse: bool) -> None:
    a, b = score(note() + note("D")), score(note(), note("D"))
    report, pairs = evaluate(*((b, a) if reverse else (a, b)))
    assert report["k1Operations"] == 1
    assert report["metrics"]["pitchExactRate"]["value"] == 1
    assert report["metrics"]["durationExactRate"]["value"] == 1
    assert report["onsetOnlyMismatch"] == 0
    assert report["metrics"]["measureExactMatchRate"]["value"] == 0
    assert pairs["measures"][0]["operation"] == ("merge" if reverse else "split")


def test_empty_measure_gap_and_zero_denominators() -> None:
    report, _ = evaluate(score(""), score("", ""))
    assert report["k1Operations"] == 1
    for name in ("K1", "pitchExactRate", "durationExactRate", "tieExactRate", "K1-L"):
        assert report["metrics"][name]["value"] is None
        assert report["metrics"][name]["denominator"] == 0


@pytest.mark.parametrize(
    "extra",
    [
        "<backup><duration>1</duration></backup><forward><duration>1</duration></forward>",
        '<print new-system="yes"/>',
    ],
)
def test_cursor_and_layout_equivalence(extra: str) -> None:
    report, _ = evaluate(score(note() + note("D")), score(note() + extra + note("D")))
    assert report["k1Operations"] == 0
    assert report["metrics"]["measureExactMatchRate"]["value"] == 1


def test_onset_only_and_code_value_position_object() -> None:
    report, _ = evaluate(score(note()), score("<forward><duration>1</duration></forward>" + note()))
    assert report["k1Operations"] == 0
    assert report["onsetOnlyMismatch"] == 1
    assert report["metrics"]["measureExactMatchRate"]["value"] == 0
    h = "<harmony><root><root-step>C</root-step></root><kind>major</kind></harmony>"
    moved = h.replace("C</root-step>", "D</root-step>").replace(
        "</harmony>", "<offset>1</offset></harmony>"
    )
    report, pairs = evaluate(score(h + note()), score(moved + note()))
    assert report["k1Operations"] == 1
    assert pairs["measures"][0]["harmonies"][0]["errors"] == ("value", "onset")


def test_grace_chord_and_tuplet_duration() -> None:
    grace = "<note><grace/><pitch><step>D</step><octave>4</octave></pitch></note>"
    chord = note("E").replace("<note>", "<note><chord/>")
    tuplet = note(
        "F",
        "2",
        "<time-modification><actual-notes>3</actual-notes>"
        "<normal-notes>2</normal-notes></time-modification>",
    )
    xml = (
        score(grace + note() + chord + tuplet)
        .replace(b"<divisions>1", b"<divisions>3")
        .replace(b"<duration>1", b"<duration>3")
    )
    events = project(xml).measures[0].events
    assert [e.onset for e in events] == [0, 0, 0, 1]
    assert events[-1].duration == Fraction(2, 3)
    report, _ = evaluate(xml, xml)
    assert report["metrics"]["pitchExactRate"]["denominator"] == 3
    assert report["metrics"]["durationExactRate"]["denominator"] == 3
    assert report["metrics"]["graceExact"]["value"] == 1


def test_lyrics_nfc_verse_attachment() -> None:
    lyric = '<lyric number="2"><syllabic>single</syllabic><text>가</text></lyric>'
    a = score(note(extra=lyric) + note("D"))
    b = score(note() + note("D", extra=lyric))
    report, _ = evaluate(a, b)
    assert report["k1Operations"] == 0
    assert report["metrics"]["lyricExactRate"]["value"] == 0
    assert report["metrics"]["K1-L"]["numerator"] == 2
    same, _ = evaluate(a, a.replace("가".encode(), "\u1100\u1161".encode()))
    assert same["metrics"]["lyricExactRate"]["value"] == 1


@pytest.mark.parametrize(
    "old,new", [("<fifths>0", "<fifths>1"), ("<beats>4", "<beats>3"), ("<sign>G", "<sign>F")]
)
def test_attribute_error_charged_at_change_only(old: str, new: str) -> None:
    a = score(note(), note())
    report, _ = evaluate(a, a.replace(old.encode(), new.encode()))
    assert report["k1Operations"] == 1
    assert report["metrics"]["measureExactMatchRate"]["numerator"] == 0


def test_accidental_and_rest_denominators() -> None:
    f = note("F").replace("</step>", "</step><alter>1</alter>")
    natural = note("C", extra="<accidental>natural</accidental>")
    rest = "<note><rest/><duration>1</duration></note>"
    xml = score(f + natural + rest).replace(b"<fifths>0", b"<fifths>1")
    report, _ = evaluate(xml, xml)
    assert report["metrics"]["accidentalExactRate"]["denominator"] == 1
    assert report["metrics"]["restExactRate"]["denominator"] == 1
    assert report["metrics"]["pitchExactRate"]["denominator"] == 2


@pytest.mark.parametrize(
    "mark",
    [
        '<barline><repeat direction="backward"/></barline>',
        '<barline><ending number="1" type="stop"/></barline>',
    ],
)
def test_repeat_volta_exactness(mark: str) -> None:
    report, _ = evaluate(score(note() + mark), score(note()))
    assert report["metrics"]["measureExactMatchRate"]["value"] == 0


def test_native_chord_degree_semantics() -> None:
    h = "<harmony><root><root-step>C</root-step></root><kind>half-diminished</kind></harmony>"
    altered = h.replace("half-diminished", "minor-seventh").replace(
        "</harmony>",
        "<degree><degree-value>5</degree-value><degree-alter>-1</degree-alter>"
        "<degree-type>alter</degree-type></degree></harmony>",
    )
    report, _ = evaluate(score(h + note()), score(altered + note()))
    assert report["k1Operations"] == 0
    assert report["metrics"]["chordSymbolExactRate"]["value"] == 1


@pytest.mark.parametrize(
    "body",
    [
        "<note><rest/><duration>0</duration></note>",
        "<backup><duration>1</duration></backup>",
        "<note><chord/><rest/><duration>1</duration></note>",
        "<direction><direction-type><segno/></direction-type></direction>",
        note(extra="<staff>2</staff>"),
        note(extra="<voice>1</voice>") + note(extra="<voice>2</voice>"),
        "<note><unpitched/><duration>1</duration></note>",
        "<harmony><root><root-step>C</root-step></root><kind>other</kind></harmony>",
        "<harmony><root><root-step>C</root-step></root><kind>major</kind>"
        "<inversion>1</inversion></harmony>",
        note() + "<attributes><clef><sign>F</sign><line>4</line></clef></attributes>",
        "<forward><duration>0</duration></forward>",
        note() + "<backup><duration>1</duration></backup>" + note(),
    ],
)
def test_unsupported_is_never_a_score(body: str) -> None:
    report, pairs = evaluate(score(note()), score(body))
    assert report["status"] == pairs["status"] == "evaluation-unsupported"
    assert report["metrics"] == {} and pairs["measures"] == []


@pytest.mark.parametrize(
    "xml",
    [
        b"<score-timewise/>",
        b"<bad",
        b"\xff",
        b'<!DOCTYPE score-partwise SYSTEM "file:///no-read">',
        b"<?instruction secret?>" + score(note()),
        score(note()).replace(b"<divisions>1", b"<divisions>0"),
    ],
)
def test_invalid_xml_and_external_entities(xml: bytes) -> None:
    report, _ = evaluate(xml, score(note()))
    assert report["status"] == "evaluation-unsupported"


def test_resource_bounds_and_serializer() -> None:
    with pytest.raises(EvaluationUnsupported, match="cell-budget"):
        align_items([], [], event_errors, Budget(remaining=0))
    with pytest.raises(EvaluationUnsupported, match="xml-byte-limit"):
        project(b" " * (limit("maxXmlBytes") + 1))
    with pytest.raises(TypeError):
        canonical(object())


def test_dp_matches_exhaustive_objective() -> None:
    base = project(score(note())).measures[0].events[0]
    for letters in product("CD", repeat=4):
        a = [
            replace(base, pitch=(s, Fraction(0), 4), onset=Fraction(i))
            for i, s in enumerate(letters[:2])
        ]
        b = [
            replace(base, pitch=(s, Fraction(0), 4), onset=Fraction(i + 1))
            for i, s in enumerate(letters[2:])
        ]
        candidates = []

        def paths(
            i: int,
            j: int,
            cost: tuple[int, int, Fraction],
            a: list[Event] = a,
            b: list[Event] = b,
            candidates: list[tuple[int, int, Fraction]] = candidates,
        ) -> None:
            if i == len(a) and j == len(b):
                candidates.append(cost)
            if i < len(a) and j < len(b):
                fields = event_errors(a[i], b[j])
                paths(
                    i + 1,
                    j + 1,
                    add(cost, (int(bool(fields)), len(fields), abs(a[i].onset - b[j].onset))),
                )
            if i < len(a):
                paths(i + 1, j, add(cost, (1, 0, Fraction(0))))
            if j < len(b):
                paths(i, j + 1, add(cost, (1, 0, Fraction(0))))

        paths(0, 0, (0, 0, Fraction(0)))
        cost, pairs = align_items(a, b, event_errors, Budget())
        assert cost == min(candidates)
        assert sum(p.reference is not None for p in pairs) == len(a)
        assert sum(p.prediction is not None for p in pairs) == len(b)


def test_cli_outputs_and_unsupported_exit(tmp_path: Path) -> None:
    a, b = tmp_path / "a.musicxml", tmp_path / "b.musicxml"
    a.write_bytes(score(note()))
    b.write_bytes(score(note()))
    command = [sys.executable, "-m", "eval", str(a), str(b), "--out", str(tmp_path / "out")]
    assert subprocess.run(command, check=False).returncode == 0
    b.write_bytes(b"<score-timewise/>")
    assert subprocess.run(command, check=False).returncode == 2
    result = json.loads((tmp_path / "out/report.json").read_text(encoding="utf-8"))
    assert result["status"] == "evaluation-unsupported"
