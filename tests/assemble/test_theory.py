"""Self-authored theory examples and properties, not SYN-Val or recognition data."""

from fractions import Fraction
from itertools import product
from typing import get_args

import pytest
from hypothesis import given
from hypothesis import strategies as st

from clavis.assemble.theory import Accidentals, Rules, duration, key_alter, natural_pitch
from clavis.contracts.common import ClefSign, Dur


@pytest.mark.parametrize(
    "clef,step,octave",
    [
        ("G2", "E", 4),
        ("G2_8vb", "E", 3),
        ("G2_8va", "E", 5),
        ("F4", "G", 2),
        ("F4_8vb", "G", 1),
        ("F3", "B", 2),
        ("C1", "C", 4),
        ("C2", "A", 3),
        ("C3", "F", 3),
        ("C4", "D", 3),
        ("C5", "B", 2),
    ],
)
def test_all_clefs_positions_and_keys(clef, step, octave):
    for pos, fifths in product(range(-14, 23), range(-7, 8)):
        p = Accidentals().pitch(pos, clef, fifths)
        ordinal = "CDEFGAB".index(step) + 7 * octave + pos
        assert (p.step, p.octave) == ("CDEFGAB"[ordinal % 7], ordinal // 7)
        altered = ("FCGDAEB" if fifths > 0 else "BEADGCF")[: abs(fifths)]
        assert p.alter == (0 if p.step not in altered else 1 if fifths > 0 else -1)


@pytest.mark.parametrize(
    "dur,base",
    list(
        zip(
            get_args(Dur),
            [8, 4, 2, 1, Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(1, 16)],
            strict=True,
        )
    ),
)
@pytest.mark.parametrize("dots,factor", [(0, 1), (1, Fraction(3, 2)), (2, Fraction(7, 4))])
@pytest.mark.parametrize("triplet", [False, True])
@pytest.mark.parametrize("grace", [None, "acciaccatura", "appoggiatura"])
def test_all_durations(dur, base, dots, factor, triplet, grace):
    expected = 0 if grace else base * factor * (Fraction(2, 3) if triplet else 1)
    assert duration(dur, dots, triplet=triplet, grace=grace) == expected


@given(st.integers(-14, 15), st.sampled_from(get_args(ClefSign)))
def test_diatonic_octave_property(pos, clef):
    low, high = natural_pitch(pos, clef), natural_pitch(pos + 7, clef)
    assert low.step == high.step
    assert high.octave == low.octave + 1


@given(st.integers(1, 16), st.sampled_from([1, 2, 4, 8, 16, 32]))
def test_measure_rest_capacity(beats, beat_type):
    capacity = Fraction(beats * 4, beat_type)
    assert duration("whole", 0, measure_capacity=capacity) == capacity


def test_accidental_precedence_and_shared_state():
    state = Accidentals()
    assert state.pitch(1, "G2", 1).alter == 1
    assert state.pitch(1, "G2", 1, visible="flat", tied_alter=2).alter == -1
    assert state.pitch(1, "G2", 1, tied_alter=2).alter == 2
    assert state.pitch(1, "G2", 1).alter == -1
    assert state.pitch(8, "G2", 1).alter == 1  # Different octave, same step.
    assert state.pitch(1, "G2", 1, visible="natural").alter == 0
    assert Accidentals().pitch(1, "G2", 1).alter == 1


@pytest.mark.parametrize(
    "acc,alter",
    [("natural", 0), ("sharp", 1), ("flat", -1), ("doubleSharp", 2), ("doubleFlat", -2)],
)
def test_all_visible_accidentals(acc, alter):
    assert Accidentals().pitch(0, "G2", 0, visible=acc).alter == alter


def test_invalid_values_and_disabled_rules():
    with pytest.raises(ValueError, match="fifths"):
        key_alter("C", 8)
    with pytest.raises(ValueError, match="dots"):
        duration("quarter", 3)
    with pytest.raises(ValueError, match="capacity"):
        duration("whole", 0, measure_capacity=Fraction(0))
    for rule, action in [
        ("ASM-PITCH", lambda r: natural_pitch(0, "G2", r)),
        ("ASM-ACCIDENTAL", lambda r: Accidentals().pitch(0, "G2", 0, rules=r)),
        ("ASM-DURATION", lambda r: duration("quarter", 0, rules=r)),
    ]:
        with pytest.raises(ValueError, match=rule):
            action(Rules(frozenset([rule])))


def test_catalog_flags_and_coverage(tmp_path):
    import ast
    import json
    from pathlib import Path

    catalog = Path("configs/assemble/rules.yaml")
    rows = json.loads(catalog.read_text(encoding="utf-8"))
    calls = {
        node.args[0].value
        for path in Path("src/clavis/assemble").glob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "require"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert calls == {row["id"] for row in rows}
    assert Rules.from_catalog(catalog).disabled == frozenset()
    for row in rows:
        row["enabled"] = False
    local = tmp_path / "rules.yaml"
    local.write_text(json.dumps(rows), encoding="utf-8")
    assert Rules.from_catalog(local).disabled == calls
    rows[0]["enabled"] = "false"
    local.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError, match="boolean"):
        Rules.from_catalog(local)
