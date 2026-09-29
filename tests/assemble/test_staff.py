from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

import pytest

from clavis.assemble.staff import assemble_staff, rational
from clavis.assemble.theory import Rules
from clavis.contracts.canonical import canonical_json
from clavis.contracts.symbols import StaffLattice

from .helpers import assemble, bar, events, note, prefix


def test_initial_repeat_and_consecutive_bars_never_create_empty_measure():
    a = assemble(
        prefix()
        + [
            bar("repeatStart"),
            note(dur="whole"),
            bar("repeatEnd"),
            dict(type="key", fifths=-1),
            dict(type="time", beats=3, beatType=4),
            bar("repeatStart"),
            note(dur="half", dots=1),
            bar("final"),
            dict(type="clef", sign="F4", courtesy=True),
        ]
    )
    assert len(a.score.measures) == 2
    one, two = [m.staff_measures[0] for m in a.score.measures]
    assert one.barline_left.style == two.barline_left.style == "repeatStart"
    assert one.barline_right.style == "repeatEnd"
    assert two.barline_right.style == "final"
    assert two.key.fifths == -1
    assert two.time.beats == 3
    assert two.clef.sign == "G2"


def test_boundary_clef_belongs_to_next_measure():
    a = assemble(
        prefix()
        + [note(dur="whole"), dict(type="clef", sign="F4"), bar(), note(dur="whole"), bar("final")]
    )
    assert [(e.pitch.step, e.pitch.octave) for e in events(a)] == [("E", 4), ("G", 2)]


@pytest.mark.parametrize(
    "styles",
    [
        ("regular", "double"),
        ("repeatEnd", "repeatStart"),
        ("repeatBoth",),
        ("regular", "regular", "final"),
    ],
)
def test_eventless_bars_are_one_boundary(styles):
    a = assemble(prefix() + [note(dur="whole"), *[bar(s) for s in styles], note(dur="whole")])
    assert len(a.score.measures) == 2
    assert len(events(a)) == 2


def test_chord_and_voices_have_independent_time_axes():
    a = assemble(
        prefix()
        + [
            note(dur="half"),
            note(dur="half", pos=2, chord=1),
            note(dur="whole", v=2),
            note(dur="half", pos=4),
            bar("final"),
        ]
    )
    voices = a.score.measures[0].staff_measures[0].voices
    assert [rational(e.onset) for e in voices[0].events] == [0, 0, 2]
    assert [rational(e.onset) for e in voices[1].events] == [0]
    assert not a.hints


def test_accidentals_grace_ties_and_bar_reset():
    a = assemble(
        prefix()
        + [
            note(pos=1, grace="acciaccatura", acc="flat"),
            note(pos=1, dur="whole", tie="start"),
            bar(),
            note(pos=1, dur="half", tie="stop"),
            note(pos=1, dur="half"),
            bar("final"),
        ]
    )
    assert [e.pitch.alter for e in events(a)] == [-1, -1, -1, 0]
    assert [rational(e.duration) for e in events(a)] == [0, 4, 2, 2]
    assert all(not e.flags for e in events(a))


def test_rest_rhythm_triplet_and_pickup():
    a = assemble(
        prefix()
        + [
            note(dur="eighth", head="slash"),
            bar(),
            dict(type="rest", dur="whole", dots=0, v=1, measureRest=True),
            bar("final"),
        ]
    )
    assert a.score.measures[0].implicit and a.score.measures[0].number == "0"
    assert a.score.measures[1].number == "1"
    assert events(a)[0].pitch is None and events(a)[0].kind == "rhythm"
    assert rational(events(a)[1].duration) == 4
    triplet = assemble(
        prefix(1) + [note(dur="eighth", tup3=mark) for mark in ("start", "continue", "stop")]
    )
    assert [rational(e.onset) for e in events(triplet)] == [0, Fraction(1, 3), Fraction(2, 3)]


def test_unfilled_and_overfull_measures_preserve_every_event():
    a = assemble(prefix() + [note(dur="whole"), bar(), note(), bar(), note(dur="breve")])
    assert len(events(a)) == 3
    assert [rational(e.duration) for e in events(a)] == [4, 1, 8]
    assert len(a.hints) == 2
    assert all(h.reason_code == "DURATION_MISMATCH" and not h.alternatives for h in a.hints)
    assert a.score.status == "partial"
    assert len(a.sources) == 3


@pytest.mark.parametrize(
    "items,match",
    [
        ([note(chord=1)], "preceding note"),
        ([note(), dict(type="time", beats=3, beatType=4)], "mid-measure"),
        ([note(), dict(type="clef", sign="F4"), note()], "mid-measure"),
        ([dict(type="segno")], "does not support"),
        ([note(grace="acciaccatura"), note(chord=1)], "cannot share"),
        ([note(head="slash", tie="start")], "rhythm slash"),
    ],
)
def test_unsupported_input_fails_explicitly(items, match):
    with pytest.raises(ValueError, match=match):
        assemble(prefix() + items)


def test_context_empty_and_rule_ablation():
    with pytest.raises(ValueError, match="context"):
        assemble([note()])
    assert assemble(prefix()).score.status == "blocked"
    for name in ("ASM-BOUNDARY", "ASM-TIMELINE"):
        with pytest.raises(ValueError, match=name):
            assemble(prefix() + [note()], rules=Rules(frozenset([name])))


def test_contract_mock_and_determinism():
    fixture = Path("tests/fixtures/contracts/valid/lattice-0.json").read_bytes()
    lattice = StaffLattice.model_validate_json(fixture)
    engine = assemble(prefix() + [note()]).score.engine

    def run(_):
        a = assemble_staff(lattice, engine=engine)
        assert len(a.score.measures) == 2 and len(events(a)) == 7
        return canonical_json(a.score)

    outputs = []
    for workers in (1, 4):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outputs.extend(pool.map(run, range(3)))
    assert len(set(outputs)) == 1


@pytest.mark.parametrize("count", range(2, 65))
def test_multi_rest_expands_only_its_observed_count(count):
    a = assemble(prefix(3) + [dict(type="mrest", count=count), bar("final")])
    assert len(a.score.measures) == count
    assert len(events(a)) == count
    assert all(e.measure_rest and rational(e.duration) == 3 for e in events(a))
    assert len(set(a.sources.values())) == 1
    assert a.score.measures[-1].staff_measures[0].barline_right.style == "final"


def test_multi_rest_and_tie_rule_ablation():
    with pytest.raises(ValueError, match="complete measures"):
        assemble(prefix() + [note(), dict(type="mrest", count=2)])
    with pytest.raises(ValueError, match="ASM-MREST"):
        assemble(prefix() + [dict(type="mrest", count=2)], rules=Rules(frozenset(["ASM-MREST"])))
    with pytest.raises(ValueError, match="ASM-TIE"):
        assemble(prefix() + [note(tie="start")], rules=Rules(frozenset(["ASM-TIE"])))


def test_tied_chord_carries_each_accidental_over_boundary():
    a = assemble(
        prefix()
        + [
            note(dur="whole", acc="sharp", tie="start"),
            note(dur="whole", pos=2, acc="flat", chord=1, tie="start"),
            bar(),
            note(dur="whole", tie="stop"),
            note(dur="whole", pos=2, chord=1, tie="stop"),
        ]
    )
    assert [e.pitch.alter for e in events(a)] == [1, -1, 1, -1]
    assert not a.hints


def test_observed_curve_with_changed_pitch_is_flagged_slur():
    a = assemble(prefix(2) + [note(tie="start"), note(pos=1, tie="stop")])
    first, last = events(a)
    assert first.slur.start and last.slur.stop
    assert not first.tie.start and not last.tie.stop
    assert len(a.hints) == 2
    assert all(h.reason_code == "TIE_SLUR_AMBIGUOUS" for h in a.hints)
    with pytest.raises(ValueError, match="unambiguous"):
        assemble(prefix() + [note(tie="stop")])


def test_json_schema_output():
    import json

    import jsonschema

    from clavis.contracts.outputs import ReviewHints

    a = assemble(prefix(2) + [note(tie="start"), note(pos=1, tie="stop")])
    for model, name in [
        (a.score, "ScoreIR"),
        (
            ReviewHints(schema="clavis-hints-0.1", threshold_artifact_digest=None, hints=a.hints),
            "ReviewHints",
        ),
    ]:
        schema = json.loads(Path(f"src/clavis/contracts/schemas/{name}.json").read_bytes())
        jsonschema.validate(json.loads(canonical_json(model)), schema)


def test_no_hypothesis_or_visual_evidence_is_rejected():
    from .helpers import lattice

    engine = assemble(prefix()).score.engine
    empty = lattice(prefix())
    empty.hypotheses = []
    with pytest.raises(ValueError, match="no lattice"):
        assemble_staff(empty, engine=engine)
    missing = lattice(prefix() + [note()])
    missing.hypotheses[0].items[-1].symbol_ids = []
    with pytest.raises(ValueError, match="visual"):
        assemble_staff(missing, engine=engine)
