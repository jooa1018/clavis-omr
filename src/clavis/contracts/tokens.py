"""Typed LSTL 0.1.1 items (CCR-0003); no recognition logic."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

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

LSTL_DEFAULTS = (
    ("acc", "none"),
    ("acc_paren", False),
    ("tie", "none"),
    ("slur", "none"),
    ("chord", 0),
    ("join", 0),
    ("grace", "none"),
    ("tup3", "none"),
    ("fermata", False),
    ("stem", "none"),
    ("beam", "none"),
    ("measure_rest", False),
    ("courtesy", False),
    ("cancel", 0),
)


class TokenDefaults(WireModel):
    omitted_defaults = LSTL_DEFAULTS


class ClefItem(Clef, TokenDefaults):
    type: Literal["clef"]
    courtesy: StrictBool | None = None


class KeyItem(Key, TokenDefaults):
    type: Literal["key"]
    cancel: Annotated[StrictInt, Field(ge=0, le=7)] | None = None
    courtesy: StrictBool | None = None


class TimeItem(Time, TokenDefaults):
    type: Literal["time"]
    courtesy: StrictBool | None = None


class BarItem(Barline):
    type: Literal["bar"]


class NoteItem(TokenDefaults):
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
    chord: Annotated[StrictInt, Field(ge=0, le=1)] | None = None
    join: Annotated[StrictInt, Field(ge=0, le=1)] | None = None
    grace: Grace | None = None
    tup3: Tup3 | None = None
    fermata: StrictBool | None = None
    stem: Stem | None = None
    beam: Beam | None = None

    @model_validator(mode="after")
    def column_marker(self) -> Self:
        if self.join is not None and (self.chord == 1 or self.grace is not None):
            raise ValueError("join is forbidden on chord continuations and grace notes")
        return self


class RestItem(TokenDefaults):
    type: Literal["rest"]
    dur: Dur
    dots: Dots
    v: VoiceNumber
    join: Annotated[StrictInt, Field(ge=0, le=1)] | None = None
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
