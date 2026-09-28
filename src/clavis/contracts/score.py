"""Score wire structures, with structural validation only (CONTRACTS 3.7)."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, model_validator

from .common import (
    IR,
    Acc,
    Alter,
    Barline,
    Bp,
    Clef,
    Diagnostic,
    Digest,
    Dots,
    Dur,
    Ending,
    Grace,
    Id,
    JoinMarks,
    Key,
    NonnegativeFraction,
    Pitch,
    PitchClass,
    Pos,
    PositiveFraction,
    PositiveInt,
    Status,
    TempoValue,
    Text,
    Time,
    UInt,
    VoiceNumber,
    WireModel,
    references,
    unique,
)

ChordKind = Literal[
    "major",
    "minor",
    "augmented",
    "diminished",
    "dominant",
    "major-seventh",
    "minor-seventh",
    "diminished-seventh",
    "half-diminished",
    "major-minor",
    "major-sixth",
    "minor-sixth",
    "dominant-ninth",
    "major-ninth",
    "minor-ninth",
    "dominant-11th",
    "dominant-13th",
    "suspended-second",
    "suspended-fourth",
    "power",
    "none",
]


class Degree(WireModel):
    value: PositiveInt
    alter: Alter
    type: Literal["add", "alter", "subtract"]


class ChordValue(WireModel):
    root: PitchClass | None = None
    kind: ChordKind
    kind_text: Text
    degrees: list[Degree]
    bass: PitchClass | None = None

    @model_validator(mode="after")
    def root_for_kind(self) -> Self:
        if self.kind == "none":
            if self.root is not None or self.bass is not None or self.degrees:
                raise ValueError("N.C. has no root, bass or degrees")
        elif self.root is None:
            raise ValueError("chord requires root")
        return self


class ChordParseResult(ChordValue):
    normalized: Text

    @model_validator(mode="after")
    def no_chord(self) -> Self:
        if (self.kind == "none") != (self.normalized == "N.C."):
            raise ValueError("N.C. normalized/kind mismatch")
        return self


class Harmony(ChordValue):
    harmony_id: Id
    staff_in_part: PositiveInt = 1
    onset: NonnegativeFraction
    source_text: Text
    text_id: Id
    confidence_bp: Bp
    evidence_ids: list[Id]


class Tuplet(WireModel):
    actual: PositiveInt
    normal: PositiveInt


class Notated(WireModel):
    type: Dur
    dots: Dots
    tuplet: Tuplet | None = None


class Lyric(WireModel):
    verse: PositiveInt
    text: Text
    syllabic: Literal["single", "begin", "middle", "end"]
    extend: StrictBool
    text_id: Id


class Event(WireModel):
    event_id: Id
    kind: Literal["note", "rest", "rhythm"]
    onset: NonnegativeFraction
    duration: NonnegativeFraction
    notated: Notated
    chord_with_prev: StrictBool
    grace: Grace | None = None
    pitch: Pitch | None = None
    pos: Pos | None = None
    accidental_visible: Acc | None = None
    tie: JoinMarks
    slur: JoinMarks
    fermata: StrictBool
    measure_rest: StrictBool
    lyrics: list[Lyric]
    evidence_ids: list[Id]
    confidence_bp: Bp
    flags: list[Text]

    @model_validator(mode="after")
    def shape(self) -> Self:
        if (self.kind == "note") != (self.pitch is not None):
            raise ValueError("pitch is required only for note events")
        unique([lyric.verse for lyric in self.lyrics], "lyric verse")
        return self


class Direction(WireModel):
    direction_id: Id
    onset: NonnegativeFraction
    kind: Literal["tempo", "section", "navigation", "rehearsal", "words"]
    value: TempoValue | Text
    text_id: Id | None = None
    symbol_id: Id | None = None
    confidence_bp: Bp

    @model_validator(mode="after")
    def value_kind(self) -> Self:
        if (self.kind == "tempo") != isinstance(self.value, TempoValue):
            raise ValueError("direction value must match kind")
        return self


class Voice(WireModel):
    voice: VoiceNumber
    events: list[Event]


class StaffMeasure(WireModel):
    staff_measure_id: Id
    staff_id: Id
    clef: Clef | None = None
    key: Key | None = None
    time: Time | None = None
    barline_left: Barline | None = None
    barline_right: Barline | None = None
    ending: Ending | None = None
    voices: list[Voice]
    evidence_ids: list[Id]
    confidence_bp: Bp
    status: Literal["ok", "flagged", "blocked"]

    @model_validator(mode="after")
    def voices_unique(self) -> Self:
        unique([v.voice for v in self.voices], "voice")
        return self


class Measure(WireModel):
    measure_id: Id
    part_id: Id
    index: UInt
    number: Text
    implicit: StrictBool
    page_index: UInt
    system_id: Id
    capacity: PositiveFraction
    staff_measures: list[StaffMeasure]
    harmonies: list[Harmony]
    directions: list[Direction]


class StaffSlot(WireModel):
    staff_in_part: PositiveInt
    staff_ids: list[Id]


class Part(WireModel):
    part_id: Id
    name: Text | None = None
    staff_count: PositiveInt
    staff_slots: list[StaffSlot]

    @model_validator(mode="after")
    def slots(self) -> Self:
        if [s.staff_in_part for s in self.staff_slots] != list(range(1, self.staff_count + 1)):
            raise ValueError("staffSlots must enumerate 1..staffCount")
        unique([s for slot in self.staff_slots for s in slot.staff_ids], "part staff id")
        return self


class Repeat(WireModel):
    start_measure_id: Id
    end_measure_id: Id
    times: Annotated[PositiveInt, Field(ge=2)]


class FlowEnding(WireModel):
    start_measure_id: Id
    end_measure_id: Id
    numbers: Annotated[list[PositiveInt], Field(min_length=1)]


class Navigation(WireModel):
    kind: Literal[
        "segno",
        "coda",
        "toCoda",
        "dalSegno",
        "daCapo",
        "fine",
        "dsAlCoda",
        "dsAlFine",
        "dcAlCoda",
        "dcAlFine",
    ]
    measure_id: Id


class Flow(WireModel):
    repeats: list[Repeat]
    endings: list[FlowEnding]
    navigation: list[Navigation]


class ScoreMeta(WireModel):
    title: Text | None = None
    subtitle: Text | None = None
    tempo: TempoValue | None = None


class ScoreEngine(WireModel):
    version: Text
    build_digest: Digest


class ScoreIR(IR):
    meta: ScoreMeta
    engine: ScoreEngine
    parts: list[Part]
    measures: list[Measure]
    flow: Flow
    status: Status
    diagnostics: list[Diagnostic]

    @model_validator(mode="after")
    def links(self) -> Self:
        if self.id != "score0":
            raise ValueError("ScoreIR id must be score0")
        unique([p.part_id for p in self.parts], "part id")
        parts = {p.part_id: p for p in self.parts}
        references([m.part_id for m in self.measures], set(parts), "measure part")
        ids: list[str] = [p.part_id for p in self.parts]
        for m in self.measures:
            part = parts[m.part_id]
            ids += (
                [m.measure_id]
                + [h.harmony_id for h in m.harmonies]
                + [d.direction_id for d in m.directions]
            )
            staff_ids = {s for slot in part.staff_slots for s in slot.staff_ids}
            references([s.staff_id for s in m.staff_measures], staff_ids, "measure staff")
            for h in m.harmonies:
                if h.staff_in_part > part.staff_count:
                    raise ValueError("harmony staffInPart outside part")
            for sm in m.staff_measures:
                ids.append(sm.staff_measure_id)
                for voice in sm.voices:
                    ids += [e.event_id for e in voice.events]
        unique(ids, "score id")
        ranges: list[Repeat | FlowEnding] = [*self.flow.repeats, *self.flow.endings]
        measure_ids = {m.measure_id for m in self.measures}
        references(
            [x for r in ranges for x in (r.start_measure_id, r.end_measure_id)]
            + [n.measure_id for n in self.flow.navigation],
            measure_ids,
            "flow measure",
        )
        return self
