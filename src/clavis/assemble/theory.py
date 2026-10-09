"""Exact theory arithmetic from CONTRACTS 5.1–5.3; no recognition or search."""

import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Literal, cast

from clavis.contracts.common import Acc, ClefSign, Dur, Grace, Pitch


@dataclass(frozen=True)
class Rules:
    """A disabled foundational rule fails closed instead of inventing semantics."""

    disabled: frozenset[str] = frozenset()

    @classmethod
    def from_catalog(cls, path: Path) -> "Rules":
        """Read the catalog's JSON-compatible YAML subset, with no YAML dependency."""
        rows = json.loads(path.read_text(encoding="utf-8"))
        if any(type(row["enabled"]) is not bool for row in rows):
            raise ValueError("rule enabled flag must be boolean")
        return cls(frozenset(row["id"] for row in rows if not row["enabled"]))

    def require(self, name: str) -> None:
        if name in self.disabled:
            raise ValueError(f"assembly rule disabled: {name}")


DEFAULT_RULES = Rules()


def natural_pitch(pos: int, clef: ClefSign, rules: Rules = DEFAULT_RULES) -> Pitch:
    """CONTRACTS 5.1: diatonic steps from the sounding bottom-line pitch."""
    rules.require("ASM-PITCH")
    # These are musical unit definitions, not fitted recognition constants.
    bases: dict[ClefSign, tuple[str, int]] = {
        "G2": ("E", 4),
        "G2_8vb": ("E", 3),
        "G2_8va": ("E", 5),
        "F4": ("G", 2),
        "F4_8vb": ("G", 1),
        "F3": ("B", 2),
        "C1": ("C", 4),
        "C2": ("A", 3),
        "C3": ("F", 3),
        "C4": ("D", 3),
        "C5": ("B", 2),
    }
    steps = "CDEFGAB"
    step, octave = bases[clef]
    octave, index = divmod(octave * len(steps) + steps.index(step) + pos, len(steps))
    return Pitch(
        step=cast(Literal["A", "B", "C", "D", "E", "F", "G"], steps[index]), alter=0, octave=octave
    )


def key_alter(step: str, fifths: int) -> int:
    """Circle-of-fifths order, CONTRACTS 5.2; state is position-specific."""
    if not -7 <= fifths <= 7:
        raise ValueError("fifths outside contract")
    order = "FCGDAEB" if fifths >= 0 else "BEADGCF"
    return (1 if fifths > 0 else -1) if step in order[: abs(fifths)] else 0


@dataclass
class Accidentals:
    """One staff's measure state, shared by voices and grace notes."""

    values: dict[int, int] = field(default_factory=dict)

    def pitch(
        self,
        pos: int,
        clef: ClefSign,
        fifths: int,
        *,
        visible: Acc | None = None,
        tied_alter: int | None = None,
        rules: Rules = DEFAULT_RULES,
    ) -> Pitch:
        rules.require("ASM-ACCIDENTAL")
        pitch = natural_pitch(pos, clef, rules)
        alterations = {"natural": 0, "sharp": 1, "flat": -1, "doubleSharp": 2, "doubleFlat": -2}
        if visible is not None and visible != "none":
            alter = alterations[visible]
            self.values[pos] = alter
        elif tied_alter is not None:
            alter = tied_alter
        else:
            alter = self.values.get(pos, key_alter(pitch.step, fifths))
        return Pitch(step=pitch.step, alter=alter, octave=pitch.octave)


def duration(
    dur: Dur,
    dots: int,
    *,
    triplet: bool = False,
    grace: Grace | None = None,
    measure_capacity: Fraction | None = None,
    rules: Rules = DEFAULT_RULES,
) -> Fraction:
    """Quarter-note units; whole-measure rests override the printed note type."""
    rules.require("ASM-DURATION")
    if dots not in (0, 1, 2):
        raise ValueError("dots outside contract")
    if grace not in (None, "none"):
        return Fraction(0)
    if measure_capacity is not None:
        if measure_capacity <= 0:
            raise ValueError("measure capacity must be positive")
        return measure_capacity
    bases = {
        "breve": Fraction(8),
        "whole": Fraction(4),
        "half": Fraction(2),
        "quarter": Fraction(1),
        "eighth": Fraction(1, 2),
        "16th": Fraction(1, 4),
        "32nd": Fraction(1, 8),
        "64th": Fraction(1, 16),
    }
    return bases[dur] * (2 - Fraction(1, 2**dots)) * (Fraction(2, 3) if triplet else 1)
