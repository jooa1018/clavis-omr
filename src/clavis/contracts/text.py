"""Text observations and optional parsed chords (CONTRACTS 3.6)."""

from typing import Literal, Self

from pydantic import StrictBool, model_validator

from .common import (
    Box,
    Bp,
    Id,
    NonnegativeReal,
    PageIR,
    Polygon,
    PositiveInt,
    Text,
    UInt,
    WireModel,
    unique,
)
from .score import ChordParseResult

Role = Literal[
    "chord",
    "lyric",
    "title",
    "subtitle",
    "tempo",
    "section",
    "navigation",
    "rehearsal",
    "credit",
    "pageNumber",
    "other",
]


class TextAlternative(WireModel):
    text: Text
    prob_bp: Bp


class Glyph(WireModel):
    char: Text
    box: Box
    prob_bp: Bp


class Syllable(WireModel):
    text: Text
    box: Box
    hyphen_after: StrictBool
    extender: StrictBool


class StaffLink(WireModel):
    staff_id: Id
    relation: Literal["above", "below"]
    distance_spaces: NonnegativeReal


class TextItem(WireModel):
    text_id: Id
    page_index: UInt
    box_processed: Box
    polygon: Polygon | None = None
    role: Role
    role_probs: dict[Role, Bp]
    text: Text
    alternatives: list[TextAlternative]
    confidence_bp: Bp
    glyphs: list[Glyph] | None = None
    syllables: list[Syllable] | None = None
    verse: PositiveInt | None = None
    staff_link: StaffLink
    chord: ChordParseResult | None = None

    @model_validator(mode="after")
    def chord_role(self) -> Self:
        if self.chord is not None and self.role != "chord":
            raise ValueError("parsed chord requires chord role")
        return self


class TextIR(PageIR):
    items: list[TextItem]

    @model_validator(mode="after")
    def ids(self) -> Self:
        unique([t.text_id for t in self.items], "text id")
        return self
