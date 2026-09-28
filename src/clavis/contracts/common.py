"""Shared wire types from CONTRACTS 1, 4 and CCR-0001; no recognition logic."""

from math import gcd
from typing import Annotated, Literal, Self
from unicodedata import is_normalized

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)
from pydantic.alias_generators import to_camel


def nfc(value: str) -> str:
    if not is_normalized("NFC", value):
        raise ValueError("text must be NFC")
    return value


Text = Annotated[str, Field(strict=True), AfterValidator(nfc)]
Id = Annotated[Text, Field(min_length=1)]
Digest = Annotated[Text, Field(pattern=r"^[0-9a-f]{64}$")]
UInt = Annotated[StrictInt, Field(ge=0)]
PositiveInt = Annotated[StrictInt, Field(ge=1)]
Bp = Annotated[StrictInt, Field(ge=0, le=10000)]
Real = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveReal = Annotated[Real, Field(gt=0)]
NonnegativeReal = Annotated[Real, Field(ge=0)]
Point = tuple[Real, Real]
Box = tuple[Real, Real, NonnegativeReal, NonnegativeReal]
Polyline = Annotated[list[Point], Field(min_length=2)]
Polygon = Annotated[list[Point], Field(min_length=3)]
Dur = Literal["breve", "whole", "half", "quarter", "eighth", "16th", "32nd", "64th"]
Dots = Annotated[StrictInt, Field(ge=0, le=2)]
Pos = Annotated[StrictInt, Field(ge=-14, le=22)]
VoiceNumber = Annotated[StrictInt, Field(ge=1, le=4)]
Alter = Annotated[StrictInt, Field(ge=-2, le=2)]
ClefSign = Literal["G2", "G2_8vb", "G2_8va", "F4", "F4_8vb", "F3", "C1", "C2", "C3", "C4", "C5"]
BarStyle = Literal[
    "regular", "double", "final", "repeatStart", "repeatEnd", "repeatBoth", "dashed", "heavy"
]
Acc = Literal["none", "sharp", "flat", "natural", "doubleSharp", "doubleFlat"]
Grace = Literal["none", "acciaccatura", "appoggiatura"]
Head = Literal["normal", "slash", "x", "diamond"]
Join = Literal["none", "start", "stop", "both"]
Stem = Literal["none", "up", "down"]
Beam = Literal["none", "begin", "continue", "end"]
Tup3 = Literal["none", "start", "continue", "stop"]
Severity = Literal["blocking", "warning", "info"]
Status = Literal["complete", "partial", "blocked"]


class WireModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        validate_default=True,
        allow_inf_nan=False,
    )


class IR(WireModel):
    schema_version: Literal["clavis-ir-0.1"] = Field(alias="schema")
    id: Id


class PageIR(IR):
    id: Annotated[Id, Field(pattern=r"^pg[0-9]+$")]


class StaffIR(IR):
    id: Annotated[Id, Field(pattern=r"^pg[0-9]+-sy[0-9]+-st[0-9]+$")]


class Fraction(WireModel):
    n: StrictInt
    d: PositiveInt

    @model_validator(mode="after")
    def reduced(self) -> Self:
        if gcd(self.n, self.d) != 1:
            raise ValueError("fraction must be reduced")
        return self


def nonnegative_fraction(value: Fraction) -> Fraction:
    if value.n < 0:
        raise ValueError("fraction must be nonnegative")
    return value


def positive_fraction(value: Fraction) -> Fraction:
    if value.n <= 0:
        raise ValueError("fraction must be positive")
    return value


NonnegativeFraction = Annotated[Fraction, AfterValidator(nonnegative_fraction)]
PositiveFraction = Annotated[Fraction, AfterValidator(positive_fraction)]


class PitchClass(WireModel):
    step: Literal["A", "B", "C", "D", "E", "F", "G"]
    alter: Alter


class Pitch(PitchClass):
    octave: StrictInt


class Clef(WireModel):
    sign: ClefSign


class Key(WireModel):
    fifths: Annotated[StrictInt, Field(ge=-7, le=7)]


class Time(WireModel):
    beats: Annotated[StrictInt, Field(ge=1, le=16)]
    beat_type: Literal[1, 2, 4, 8, 16, 32]
    symbol: Literal["common", "cut"] | None = None


class Barline(WireModel):
    style: BarStyle


class Ending(WireModel):
    numbers: Annotated[list[PositiveInt], Field(min_length=1)]
    mark: Literal["start", "stop", "discontinue"]


class Producer(WireModel):
    name: Text
    version: Text
    sha256: Digest


class TempoValue(WireModel):
    text: Text | None = None
    beat_unit: Dur | None = None
    dots: Dots | None = None
    per_minute: PositiveFraction | None = None

    @model_validator(mode="after")
    def tempo_fields(self) -> Self:
        if self.text is None and self.per_minute is None:
            raise ValueError("tempo needs text or perMinute")
        if self.per_minute is not None and self.beat_unit is None:
            raise ValueError("perMinute requires beatUnit")
        return self


class Target(WireModel):
    kind: Literal[
        "event", "measure", "measureStart", "measureEnd", "harmony", "lyric", "text", "flow"
    ]
    id: Id


class Diagnostic(WireModel):
    code: Text
    severity: Severity
    target: Target | None = None


def unique(values: list[str] | list[int], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


def references(values: list[str], available: set[str], label: str) -> None:
    if not set(values) <= available:
        raise ValueError(f"dangling {label}")


class JoinMarks(WireModel):
    start: StrictBool
    stop: StrictBool
