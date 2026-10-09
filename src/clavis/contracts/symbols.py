"""Symbol candidates and lattice payloads; selection is owned by W6/W8."""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import AfterValidator, Field, StrictBool, StrictInt, TypeAdapter, model_validator

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
    TopK,
    UInt,
    VoiceNumber,
    WireModel,
    references,
    top_k_value_key,
    unique,
    validate_top_k,
)
from .lstl.automaton import validate_sequence
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
    voice_top_k: TopK[VoiceNumber] | None = None
    stem_dir: TopK[Stem] | None = None
    beam_count_top_k: TopK[UInt] | None = None
    flag_count_top_k: TopK[UInt] | None = None
    dots_top_k: TopK[Dots] | None = None
    head_type: TopK[Head] | None = None


class RejectedCandidate(WireModel):
    omitted_defaults: ClassVar[tuple[tuple[str, object], ...]] = (("attrs", {}),)

    symbol_id: Id
    sources: Annotated[list[SourceKind], Field(min_length=1)]
    class_top_k: Annotated[
        list[tuple[SymbolClass, Bp]],
        Field(min_length=1, max_length=5),
        AfterValidator(validate_top_k),
    ]
    box_strip: Box
    center_strip: Point | None = None
    pos_top_k: TopK[Pos] | None = None
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
    ]
    from_id: Id = Field(alias="from")
    to: Id
    prob_bp: Bp

    @model_validator(mode="after")
    def chord_order(self) -> Self:
        if self.kind == "chordWith" and self.from_id >= self.to:
            raise ValueError("chordWith requires from id < to id")
        return self


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
    attr_top_k: dict[Text, TopK[AttrValue]]
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
            fields = type(self.item).model_fields
            field_name = next(
                (name for name, field in fields.items() if (field.alias or name) == key), None
            )
            if field_name is None:
                raise ValueError("attrTopK must name an attribute of the item")
            field = fields[field_name]
            attribute_type = (
                Annotated[field.annotation, *field.metadata] if field.metadata else field.annotation
            )
            adapter: TypeAdapter[object] = TypeAdapter(attribute_type)
            for value, _ in candidates:
                adapter.validate_python(value)
            defaults = dict(self.item.omitted_defaults)
            current = data.get(key, defaults.get(field_name))
            if top_k_value_key(current) not in [top_k_value_key(v) for v, _ in candidates]:
                raise ValueError("attrTopK must include the current/default item value")
        return self


class Hypothesis(WireModel):
    rank: UInt
    log_prob_micro: StrictInt
    items: list[LatticeItem]

    @model_validator(mode="after")
    def printed_order(self) -> Self:
        validate_sequence(entry.item for entry in self.items)
        # Non-time items are separate printed columns (4.2.1); notes/rests can
        # share a musical column whose voice/pos order belongs to T1.4.
        for previous, current in zip(self.items, self.items[1:], strict=False):
            if previous.item.type in ("note", "rest", "mrest") or current.item.type in (
                "note",
                "rest",
                "mrest",
            ):
                continue
            if current.span_u[1] < previous.span_u[0]:
                raise ValueError("disjoint lattice columns must follow printed x order")
        return self


class StaffLattice(StaffIR):
    strip_id: Id
    producer: Producer
    hypotheses: Annotated[list[Hypothesis], Field(max_length=8)]

    @model_validator(mode="after")
    def ranks(self) -> Self:
        ranks = [h.rank for h in self.hypotheses]
        if ranks != list(range(len(ranks))):
            raise ValueError("hypothesis ranks must be consecutive from zero")
        probabilities = [h.log_prob_micro for h in self.hypotheses]
        if any(b > a for a, b in zip(probabilities, probabilities[1:], strict=False)):
            raise ValueError("logProbMicro must not increase with rank")
        if self.id != self.strip_id:
            raise ValueError("lattice id must be staff/strip id")
        return self
