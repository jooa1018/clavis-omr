"""Symbol candidates and lattice payloads; selection is owned by W6/W8."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictInt, TypeAdapter, model_validator

from .common import (
    Box,
    Bp,
    Dots,
    Head,
    Id,
    Point,
    Pos,
    Producer,
    Real,
    StaffIR,
    Stem,
    Text,
    UInt,
    WireModel,
    references,
    unique,
)
from .tokens import LSTLItem

SymbolClass = Literal[
    "noteheadFilled",
    "noteheadHollow",
    "noteheadWhole",
    "noteheadSlash",
    "noteheadX",
    "stem",
    "beam",
    "flag",
    "accSharp",
    "accFlat",
    "accNatural",
    "accDoubleSharp",
    "accDoubleFlat",
    "augDot",
    "restWhole",
    "restHalf",
    "restQuarter",
    "rest8th",
    "rest16th",
    "rest32nd",
    "clefG",
    "clefF",
    "clefC",
    "timeDigit",
    "timeCommon",
    "timeCut",
    "barline",
    "repeatDots",
    "curve",
    "tupletNumber",
    "fermata",
    "ledgerLine",
    "segno",
    "coda",
    "voltaBracket",
    "reject",
]
SourceKind = Literal["fcn", "template", "cc", "vline", "beam", "curve", "ledger"]


class SymbolAttributes(WireModel):
    pos_top_k: list[tuple[Pos, Bp]] | None = None
    stem_dir: list[tuple[Stem, Bp]] | None = None
    beam_count_top_k: list[tuple[UInt, Bp]] | None = None
    flag_count_top_k: list[tuple[UInt, Bp]] | None = None
    dots_top_k: list[tuple[Dots, Bp]] | None = None
    head_type: list[tuple[Head, Bp]] | None = None


class RejectedCandidate(WireModel):
    symbol_id: Id
    sources: Annotated[list[SourceKind], Field(min_length=1)]
    class_top_k: Annotated[list[tuple[SymbolClass, Bp]], Field(min_length=1)]
    box_strip: Box
    center_strip: Point | None = None
    pos_top_k: list[tuple[Pos, Bp]] | None = None
    attrs: SymbolAttributes | None = None


class Symbol(RejectedCandidate):
    center_strip: Point


class Relation(WireModel):
    kind: Literal[
        "stemOf",
        "beamOf",
        "flagOf",
        "dotOf",
        "accidentalOf",
        "tieFrom",
        "tieTo",
        "slurFrom",
        "slurTo",
        "ledgerOf",
        "chordWith",
        "voiceOf",
    ]
    from_id: Id = Field(alias="from")
    to: Id
    prob_bp: Bp


class SymbolGraph(StaffIR):
    strip_id: Id
    producer: Producer
    symbols: list[Symbol]
    relations: list[Relation]
    rejected_candidates: list[RejectedCandidate]

    @model_validator(mode="after")
    def links(self) -> Self:
        ids = [s.symbol_id for s in self.symbols]
        unique(ids + [s.symbol_id for s in self.rejected_candidates], "symbol id")
        references(
            [v for r in self.relations for v in (r.from_id, r.to)], set(ids), "relation symbol"
        )
        if self.id != self.strip_id:
            raise ValueError("graph id must be staff/strip id")
        return self


AttrValue = Text | StrictInt | StrictBool | list[StrictInt]


class LatticeItem(WireModel):
    item: LSTLItem
    attr_top_k: dict[Text, Annotated[list[tuple[AttrValue, Bp]], Field(min_length=1, max_length=3)]]
    span_u: tuple[Real, Real]
    item_prob_bp: Bp
    symbol_ids: list[Id]

    @model_validator(mode="after")
    def alternatives(self) -> Self:
        if self.span_u[1] < self.span_u[0]:
            raise ValueError("spanU must be ordered")
        data = self.item.model_dump(by_alias=True, exclude_none=True)
        for key, candidates in self.attr_top_k.items():
            if key == "type":
                raise ValueError("attrTopK cannot change item type")
            for value, _ in candidates:
                TypeAdapter(LSTLItem).validate_python({**data, key: value})
        return self


class Hypothesis(WireModel):
    rank: UInt
    log_prob_micro: StrictInt
    items: list[LatticeItem]


class StaffLattice(StaffIR):
    strip_id: Id
    producer: Producer
    hypotheses: Annotated[list[Hypothesis], Field(max_length=8)]

    @model_validator(mode="after")
    def ranks(self) -> Self:
        ranks = [h.rank for h in self.hypotheses]
        if ranks != sorted(set(ranks)):
            raise ValueError("hypothesis ranks must strictly increase")
        if self.id != self.strip_id:
            raise ValueError("lattice id must be staff/strip id")
        return self
