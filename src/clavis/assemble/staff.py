"""First oracle path: one staff/system, rank-zero LSTL, no text or search."""

from dataclasses import dataclass
from fractions import Fraction

from clavis.contracts.common import (
    Barline,
    Clef,
    Diagnostic,
    JoinMarks,
    Key,
    Target,
    Time,
)
from clavis.contracts.common import (
    Fraction as WireFraction,
)
from clavis.contracts.lstl import State, advance
from clavis.contracts.outputs import ReviewHint
from clavis.contracts.score import (
    Event,
    Flow,
    Measure,
    Notated,
    Part,
    ScoreEngine,
    ScoreIR,
    ScoreMeta,
    StaffMeasure,
    StaffSlot,
    Tuplet,
    Voice,
)
from clavis.contracts.symbols import LatticeItem, StaffLattice
from clavis.contracts.tokens import NoteItem, RestItem

from .theory import DEFAULT_RULES, Accidentals, Rules, duration


def wire(value: Fraction) -> WireFraction:
    return WireFraction(n=value.numerator, d=value.denominator)


def rational(value: WireFraction) -> Fraction:
    return Fraction(value.n, value.d)


@dataclass
class Assembly:
    score: ScoreIR
    hints: list[ReviewHint]
    sources: dict[str, tuple[str, ...]]


def _columns(items: list[LatticeItem]) -> list[list[LatticeItem]]:
    state = State()
    columns: list[list[LatticeItem]] = []
    for entry in items:
        next_state = advance(state, entry.item)
        if next_state.column != state.column:
            columns.append([])
        columns[-1].append(entry)
        state = next_state
    return columns


def assemble_staff(
    lattice: StaffLattice,
    *,
    engine: ScoreEngine,
    clef: Clef | None = None,
    key: Key | None = None,
    time: Time | None = None,
    rules: Rules = DEFAULT_RULES,
) -> Assembly:
    """No guessed clef/meter. Absent key means no alterations (CONTRACTS 5.2).

    This deliberately does not publish a complete result: evidence geometry,
    calibrated confidence and the export validation gate are subsequent stages.
    """
    rules.require("ASM-BOUNDARY")
    rules.require("ASM-TIMELINE")
    if not lattice.hypotheses:
        raise ValueError("no lattice hypothesis")
    columns = _columns(lattice.hypotheses[0].items)
    measures: list[Measure] = []
    sources: dict[str, tuple[str, ...]] = {}
    hints: list[ReviewHint] = []
    voices: dict[int, list[Event]] = {}
    cursors: dict[int, Fraction] = {}
    accidental = Accidentals()
    active_clef, active_key, active_time = clef, key, time
    pending_clef: Clef | None = None
    left: Barline | None = None
    current: StaffMeasure | None = None
    column_onset = Fraction(0)
    capacity = Fraction(0)
    absolute = Fraction(0)
    # Previous timed/chord group per voice; ties may cross a measure boundary.
    previous: dict[int, list[tuple[Event, Fraction]]] = {}
    tie_candidates: dict[int, list[tuple[Event, Fraction]]] = {}
    diagnostics = [
        Diagnostic(code="ORACLE_EXPORT_VALIDATION_PENDING", severity="warning"),
        Diagnostic(code="CONFIDENCE_UNCALIBRATED", severity="info"),
    ]

    def finish(right: Barline | None) -> None:
        nonlocal voices, cursors, accidental, current, absolute, left, active_clef, pending_clef
        nonlocal column_onset
        if current is None:
            return
        current.barline_right = right
        length = max(cursors.values(), default=Fraction(0))
        pickup = not measures and 0 < length < capacity
        mismatch = any(end != capacity for end in cursors.values()) and not pickup
        current.status = "flagged" if mismatch else "ok"
        mid = f"P1-m{len(measures)}"
        if mismatch:
            hints.append(
                ReviewHint(
                    hint_id=f"hint-{mid}-DURATION_MISMATCH",
                    target=Target(kind="measure", id=mid),
                    reason_code="DURATION_MISMATCH",
                    severity="blocking",
                    confidence_bp=current.confidence_bp,
                    alternatives=[],
                    evidence_ids=[],
                )
            )
        current.voices = [Voice(voice=v, events=voices[v]) for v in sorted(voices)]
        measures.append(
            Measure(
                measure_id=mid,
                part_id="P1",
                index=len(measures),
                number="0"
                if pickup
                else str(len(measures) + (0 if measures and measures[0].implicit else 1)),
                implicit=pickup,
                page_index=int(lattice.id.split("-")[0][2:]),
                system_id=lattice.id.rsplit("-", 1)[0],
                capacity=wire(capacity),
                staff_measures=[current],
                harmonies=[],
                directions=[],
            )
        )
        absolute += length if pickup else capacity
        voices, cursors, accidental, current, left = {}, {}, Accidentals(), None, None
        column_onset = Fraction(0)
        if pending_clef is not None:
            active_clef, pending_clef = pending_clef, None

    def consume(entry: LatticeItem, onset: Fraction) -> None:
        nonlocal current, capacity
        item = entry.item
        assert isinstance(item, NoteItem | RestItem)
        if pending_clef is not None:
            raise ValueError("mid-measure clef unsupported in first oracle path")
        if active_clef is None or active_time is None:
            raise ValueError("clef and time context are required")
        if current is None:
            capacity = Fraction(active_time.beats * 4, active_time.beat_type)
            current = StaffMeasure(
                staff_measure_id=f"P1-m{len(measures)}-s1",
                staff_id=lattice.id,
                clef=active_clef,
                key=active_key,
                time=active_time,
                barline_left=left,
                voices=[],
                evidence_ids=[],
                confidence_bp=entry.item_prob_bp,
                status="ok",
            )
        current.confidence_bp = min(current.confidence_bp, entry.item_prob_bp)
        if not isinstance(item, NoteItem) or not item.chord:
            tie_candidates[item.v] = previous.get(item.v, [])
        event = _event(
            entry,
            len(measures),
            len(voices.get(item.v, [])),
            capacity,
            accidental,
            active_clef,
            active_key,
            onset,
            voices,
            tie_candidates,
            absolute,
            rules,
        )
        voices.setdefault(item.v, []).append(event)
        sources[event.event_id] = tuple(entry.symbol_ids)
        onset, length = rational(event.onset), rational(event.duration)
        cursors[item.v] = max(cursors.get(item.v, Fraction(0)), onset + length)
        if not event.chord_with_prev:
            previous[item.v] = []
        previous.setdefault(item.v, []).append((event, absolute + onset + length))

    for column in columns:
        entry = column[0]
        item = entry.item
        if isinstance(item, NoteItem | RestItem):
            # Earliest onset satisfying voice availability and printed column order.
            # Delayed voices retain gaps; export represents them with forward, never rests.
            column_onset = max(
                column_onset,
                *(
                    cursors.get(e.item.v, Fraction(0))
                    for e in column
                    if isinstance(e.item, NoteItem | RestItem)
                ),
            )
            for member in column:
                if not member.symbol_ids:
                    raise ValueError("oracle item requires visual symbol references")
                consume(member, column_onset)
            continue
        if getattr(item, "courtesy", False):
            continue
        if not entry.symbol_ids:
            raise ValueError("oracle item requires visual symbol references")
        if item.type == "clef":
            if current is None:
                active_clef = Clef(sign=item.sign)
            else:
                pending_clef = Clef(sign=item.sign)
            continue
        if item.type in ("key", "time"):
            if current is not None:
                raise ValueError("mid-measure key/time unsupported in first oracle path")
            if item.type == "key":
                active_key = Key(fifths=item.fifths)
            else:
                active_time = Time(beats=item.beats, beat_type=item.beat_type, symbol=item.symbol)
            continue
        if item.type == "bar":
            if item.style == "repeatStart":
                finish(None)
                left = Barline(style="repeatStart")
            else:
                right = Barline(style="repeatEnd" if item.style == "repeatBoth" else item.style)
                if current is not None:
                    finish(right)
                elif measures:
                    measures[-1].staff_measures[0].barline_right = right
                else:
                    left = right
                if item.style == "repeatBoth":
                    left = Barline(style="repeatStart")
            continue
        if item.type == "mrest":
            rules.require("ASM-MREST")
            if current is not None:
                raise ValueError("multi-rest must occupy complete measures")
            rest = entry.model_copy(
                update={
                    "item": RestItem(type="rest", dur="whole", dots=0, v=1, measure_rest=True),
                    "attr_top_k": {},
                }
            )
            for rest_index in range(item.count):
                consume(rest, Fraction(0))
                if rest_index + 1 < item.count:
                    finish(None)
            continue
        raise ValueError(f"first oracle path does not support {item.type}")
    finish(None)
    for measure in measures:
        for voice in measure.staff_measures[0].voices:
            for event in voice.events:
                for reason in event.flags:
                    if reason == "TIE_SLUR_AMBIGUOUS":
                        hints.append(
                            ReviewHint(
                                hint_id=f"hint-{event.event_id}-{reason}",
                                target=Target(kind="event", id=event.event_id),
                                reason_code="TIE_SLUR_AMBIGUOUS",
                                severity="blocking",
                                confidence_bp=event.confidence_bp,
                                alternatives=[],
                                evidence_ids=[],
                            )
                        )
                        measure.staff_measures[0].status = "flagged"
    locations = {
        target: m.index
        for m in measures
        for target in [
            m.measure_id,
            *(e.event_id for v in m.staff_measures[0].voices for e in v.events),
        ]
    }
    hints.sort(key=lambda h: (locations[h.target.id], h.target.id, h.reason_code))
    return Assembly(
        score=ScoreIR(
            schema="clavis-ir-0.1.1",
            id="score0",
            meta=ScoreMeta(),
            engine=engine,
            parts=[
                Part(
                    part_id="P1",
                    staff_count=1,
                    staff_slots=[StaffSlot(staff_in_part=1, staff_ids=[lattice.id])],
                )
            ],
            measures=measures,
            flow=Flow(repeats=[], endings=[], navigation=[]),
            status="partial" if measures else "blocked",
            diagnostics=diagnostics,
        ),
        hints=hints,
        sources=sources,
    )


def _event(
    entry: LatticeItem,
    measure: int,
    index: int,
    capacity: Fraction,
    accidental: Accidentals,
    clef: Clef,
    key: Key | None,
    onset: Fraction,
    voices: dict[int, list[Event]],
    previous: dict[int, list[tuple[Event, Fraction]]],
    absolute: Fraction,
    rules: Rules,
) -> Event:
    item = entry.item
    assert isinstance(item, NoteItem | RestItem)
    note = item if isinstance(item, NoteItem) else None
    chord = bool(note and note.chord)
    voice = voices.get(item.v, [])
    if chord:
        if not voice or voice[-1].kind == "rest":
            raise ValueError("chord requires a preceding note in the same voice/measure")
        if bool(voice[-1].grace) != bool(note and note.grace):
            raise ValueError("grace and timed notes cannot share a chord")
        if onset != rational(voice[-1].onset):
            raise ValueError("chord onset differs from its column")
    measure_rest = bool(isinstance(item, RestItem) and item.measure_rest)
    length = duration(
        item.dur,
        item.dots,
        triplet=bool(item.tup3),
        grace=note.grace if note else None,
        measure_capacity=capacity if measure_rest else None,
        rules=rules,
    )
    pitch = None
    ties = JoinMarks(
        start=bool(note and note.tie in ("start", "both")),
        stop=bool(note and note.tie in ("stop", "both")),
    )
    flags: list[str] = []
    slurs = JoinMarks(
        start=bool(note and note.slur in ("start", "both")),
        stop=bool(note and note.slur in ("stop", "both")),
    )
    if note is not None and note.head != "slash":
        if ties.start or ties.stop:
            rules.require("ASM-TIE")
        candidates = [
            e for e, end in previous.get(item.v, []) if e.tie.start and end == absolute + onset
        ]
        tied = next(
            (
                e
                for e, end in previous.get(item.v, [])
                if e.pos == note.pos and e.tie.start and end == absolute + onset
            ),
            None,
        )
        pitch = accidental.pitch(
            note.pos,
            clef.sign,
            key.fifths if key else 0,
            visible=note.acc,
            tied_alter=tied.pitch.alter if ties.stop and tied and tied.pitch else None,
            rules=rules,
        )
        if ties.stop and (tied is None or tied.pitch != pitch):
            origin = tied if tied is not None else candidates[0] if len(candidates) == 1 else None
            if origin is None or origin.pitch is None or origin.pitch == pitch:
                raise ValueError("tie stop has no unambiguous adjacent visual origin")
            # CONTRACTS 5.4 explicitly reinterprets the same observed curve as a slur.
            origin.tie.start = False
            origin.slur.start = True
            origin.flags.append("TIE_SLUR_AMBIGUOUS")
            ties.stop = False
            slurs.stop = True
            flags.append("TIE_SLUR_AMBIGUOUS")
    if note is not None and note.head == "slash" and (ties.start or ties.stop):
        raise ValueError("pitched tie on rhythm slash unsupported")
    fields = dict(
        event_id=f"P1-m{measure}-s1-v{item.v}-e{index}",
        kind="rest" if note is None else "rhythm" if note.head == "slash" else "note",
        onset=wire(onset),
        duration=wire(length),
        notated=Notated(
            type=item.dur, dots=item.dots, tuplet=Tuplet(actual=3, normal=2) if item.tup3 else None
        ),
        chord_with_prev=chord,
        pitch=pitch,
        pos=item.pos,
        tie=ties,
        slur=slurs,
        fermata=bool(item.fermata),
        measure_rest=measure_rest,
        lyrics=[],
        evidence_ids=[],
        confidence_bp=entry.item_prob_bp,
        flags=flags,
    )
    # Explicit null/defaults are forbidden for these two optional wire fields.
    if note and note.grace:
        fields["grace"] = note.grace
    if note and note.acc:
        fields["accidental_visible"] = note.acc
    return Event.model_validate(fields)
