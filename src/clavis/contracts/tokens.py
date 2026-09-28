"""Typed LSTL items for lattice payloads. Sequence automaton belongs to T1.4."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt

from .common import (
    Acc,
    Barline,
    Beam,
    Clef,
    Dots,
    Dur,
    Ending,
    Grace,
    Head,
    Join,
    Key,
    Pos,
    Stem,
    Time,
    Tup3,
    VoiceNumber,
    WireModel,
)


class ClefItem(Clef):
    type: Literal["clef"]
    courtesy: StrictBool | None = None


class KeyItem(Key):
    type: Literal["key"]
    cancel: Annotated[StrictInt, Field(ge=0, le=7)] | None = None
    courtesy: StrictBool | None = None


class TimeItem(Time):
    type: Literal["time"]
    courtesy: StrictBool | None = None


class BarItem(Barline):
    type: Literal["bar"]


class NoteItem(WireModel):
    type: Literal["note"]
    dur: Dur
    dots: Dots
    pos: Pos
    head: Head
    v: VoiceNumber
    acc: Acc | None = None
    acc_paren: StrictBool | None = None
    tie: Join | None = None
    slur: Join | None = None
    chord: Literal[0, 1] | None = None
    grace: Grace | None = None
    tup3: Tup3 | None = None
    fermata: StrictBool | None = None
    stem: Stem | None = None
    beam: Beam | None = None


class RestItem(WireModel):
    type: Literal["rest"]
    dur: Dur
    dots: Dots
    v: VoiceNumber
    pos: Pos | None = None
    measure_rest: StrictBool | None = None
    fermata: StrictBool | None = None
    tup3: Tup3 | None = None


class MultiRestItem(WireModel):
    type: Literal["mrest"]
    count: Annotated[StrictInt, Field(ge=2, le=64)]


class EndingItem(Ending):
    type: Literal["ending"]


class SegnoItem(WireModel):
    type: Literal["segno"]


class CodaItem(WireModel):
    type: Literal["coda"]


LSTLItem = Annotated[
    ClefItem
    | KeyItem
    | TimeItem
    | BarItem
    | NoteItem
    | RestItem
    | MultiRestItem
    | EndingItem
    | SegnoItem
    | CodaItem,
    Field(discriminator="type"),
]
