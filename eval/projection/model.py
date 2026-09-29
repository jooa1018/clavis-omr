"""Evaluator-owned projection; no engine IR imports (EVALUATION 4.1)."""

from dataclasses import dataclass
from fractions import Fraction

type Pitch = tuple[str, Fraction, int]
type Lyrics = tuple[tuple[str, str, str], ...]
type Value = tuple[str, ...]


class EvaluationUnsupported(ValueError):
    """Input cannot be faithfully evaluated by this evaluator version."""


@dataclass(frozen=True)
class Event:
    ref: str
    kind: str
    onset: Fraction
    duration: Fraction
    pitch: Pitch | None
    tie_start: bool
    tie_stop: bool
    grace: bool
    chord_member: bool
    lyrics: Lyrics
    accidental: bool
    voice: str = "1"


@dataclass(frozen=True)
class Harmony:
    ref: str
    onset: Fraction
    value: Value


@dataclass(frozen=True)
class Attribute:
    ref: str
    name: str
    onset: Fraction
    value: Value


@dataclass(frozen=True)
class Measure:
    ref: str
    events: tuple[Event, ...]
    harmonies: tuple[Harmony, ...]
    changes: tuple[Attribute, ...]
    state: tuple[tuple[str, Value], ...]
    marks: tuple[Value, ...]
    length: Fraction


@dataclass(frozen=True)
class Score:
    measures: tuple[Measure, ...]
