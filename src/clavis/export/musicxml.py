"""Single-staff MusicXML writer. XSD and independent reparse are mandatory."""

import xml.etree.ElementTree as ET
from fractions import Fraction
from math import lcm

from clavis.assemble.staff import rational
from clavis.contracts.common import Barline
from clavis.contracts.score import Event, ScoreIR

from .reparse import read_projection, score_projection
from .validation import validate_musicxml


def sub(parent: ET.Element, tag: str, text: object | None = None, **attrs: str) -> ET.Element:
    child = ET.SubElement(parent, tag, attrs)
    if text is not None:
        child.text = str(text)
    return child


def _bar(parent: ET.Element, bar: Barline | None, side: str, identifier: str) -> None:
    if bar is None:
        return
    styles = {
        "regular": "regular",
        "double": "light-light",
        "final": "light-heavy",
        "repeatStart": "heavy-light",
        "repeatEnd": "light-heavy",
        "dashed": "dashed",
        "heavy": "heavy",
    }
    if bar.style not in styles:
        raise ValueError("repeatBoth must be resolved into left/right boundaries")
    element = sub(parent, "barline", location=side, id=identifier)
    sub(element, "bar-style", styles[bar.style])
    if bar.style in ("repeatStart", "repeatEnd"):
        sub(element, "repeat", direction="forward" if bar.style == "repeatStart" else "backward")


def _note(parent: ET.Element, event: Event, voice: int, divisions: int) -> None:
    element = sub(parent, "note", id=event.event_id)
    if event.grace:
        sub(element, "grace", slash="yes" if event.grace == "acciaccatura" else "no")
    if event.chord_with_prev:
        sub(element, "chord")
    if event.kind == "rest":
        rest = sub(element, "rest")
        if event.measure_rest:
            rest.set("measure", "yes")
    elif event.pitch is not None:
        pitch = sub(element, "pitch")
        sub(pitch, "step", event.pitch.step)
        sub(pitch, "alter", event.pitch.alter)
        sub(pitch, "octave", event.pitch.octave)
    else:
        unpitched = sub(element, "unpitched")
        # Unpitched display placement does not claim a sounding pitch (8.2).
        sub(unpitched, "display-step", "B")
        sub(unpitched, "display-octave", 4)
    if not event.grace:
        sub(element, "duration", int(rational(event.duration) * divisions))
    for mark in ("stop", "start"):
        if getattr(event.tie, mark):
            sub(element, "tie", type=mark)
    sub(element, "voice", voice)
    if not event.measure_rest:
        sub(element, "type", event.notated.type)
        for _ in range(event.notated.dots):
            sub(element, "dot")
    if event.accidental_visible:
        names = {"doubleSharp": "double-sharp", "doubleFlat": "flat-flat"}
        sub(element, "accidental", names.get(event.accidental_visible, event.accidental_visible))
    if event.notated.tuplet:
        modulation = sub(element, "time-modification")
        sub(modulation, "actual-notes", event.notated.tuplet.actual)
        sub(modulation, "normal-notes", event.notated.tuplet.normal)
    if event.kind == "rhythm":
        sub(element, "notehead", "slash")
    if event.tie.start or event.tie.stop or event.slur.start or event.slur.stop or event.fermata:
        notations = sub(element, "notations")
        for tag, joins in (("tied", event.tie), ("slur", event.slur)):
            for mark in ("stop", "start"):
                if getattr(joins, mark):
                    sub(notations, tag, type=mark)
        if event.fermata:
            sub(notations, "fermata")


def write_musicxml(score: ScoreIR) -> tuple[bytes, dict[str, int]]:
    """Return checked XML and non-deterministic timings; does not publish a bundle."""
    if len(score.parts) != 1 or score.parts[0].staff_count != 1 or not score.measures:
        raise ValueError("first writer requires one nonempty part/staff")
    if score.meta.model_dump(exclude_none=True) or score.flow.endings or score.flow.navigation:
        raise ValueError("text/ending/navigation unsupported in first writer")
    divisions = lcm(
        *(
            value.d
            for measure in score.measures
            for value in [
                measure.capacity,
                *(
                    v
                    for staff in measure.staff_measures
                    for voice in staff.voices
                    for e in voice.events
                    for v in (e.onset, e.duration)
                ),
            ]
        )
    )
    root = ET.Element("score-partwise", version="4.0")
    encoding = sub(sub(root, "identification"), "encoding")
    sub(encoding, "software", f"Clavis {score.engine.version}")
    listed = sub(sub(root, "part-list"), "score-part", id=score.parts[0].part_id)
    sub(listed, "part-name", score.parts[0].name or "")
    part = sub(root, "part", id=score.parts[0].part_id)
    prior_system: str | None = None
    prior_page: int | None = None
    for measure in score.measures:
        if len(measure.staff_measures) != 1 or measure.harmonies or measure.directions:
            raise ValueError("first writer excludes multiple staves/harmony/direction")
        staff = measure.staff_measures[0]
        if staff.ending is not None:
            raise ValueError("ending unsupported in first writer")
        element = sub(part, "measure", number=measure.number, id=measure.measure_id)
        if measure.implicit:
            element.set("implicit", "yes")
        if prior_page is not None and prior_page != measure.page_index:
            sub(element, "print", **{"new-page": "yes"})
        elif prior_system is not None and prior_system != measure.system_id:
            sub(element, "print", **{"new-system": "yes"})
        prior_system, prior_page = measure.system_id, measure.page_index
        attrs = sub(element, "attributes")
        sub(attrs, "divisions", divisions)
        if staff.key:
            sub(sub(attrs, "key"), "fifths", staff.key.fifths)
        if staff.time:
            time = sub(attrs, "time")
            if staff.time.symbol:
                time.set("symbol", staff.time.symbol)
            sub(time, "beats", staff.time.beats)
            sub(time, "beat-type", staff.time.beat_type)
        if staff.clef:
            clef = sub(attrs, "clef")
            sub(clef, "sign", staff.clef.sign[0])
            sub(clef, "line", staff.clef.sign[1])
            if "_" in staff.clef.sign:
                sub(clef, "clef-octave-change", 1 if staff.clef.sign.endswith("8va") else -1)
        _bar(element, staff.barline_left, "left", f"{staff.staff_measure_id}-barlineLeft")
        cursor = Fraction(0)
        capacity = rational(measure.capacity)
        if not staff.voices or any(not voice.events for voice in staff.voices):
            raise ValueError("empty voice/measure has no visual events")
        for voice in staff.voices:
            if cursor:
                sub(sub(element, "backup"), "duration", int(cursor * divisions))
            cursor = Fraction(0)
            previous: Event | None = None
            for event in voice.events:
                if event.lyrics:
                    raise ValueError("unsupported lyric")
                onset, length = rational(event.onset), rational(event.duration)
                if onset + length > capacity:
                    raise ValueError("overfull voice cannot be exported as valid")
                if event.chord_with_prev:
                    if previous is None or previous.kind == "rest" or event.kind == "rest":
                        raise ValueError("chord without preceding note")
                    if onset != rational(previous.onset) or onset + length > cursor:
                        raise ValueError("invalid chord timeline")
                else:
                    if onset < cursor:
                        raise ValueError("overlapping non-chord events")
                    if onset > cursor:
                        sub(sub(element, "forward"), "duration", int((onset - cursor) * divisions))
                    cursor = onset + length
                _note(element, event, voice.voice, divisions)
                previous = event
            if not measure.implicit and cursor < capacity:
                sub(sub(element, "forward"), "duration", int((capacity - cursor) * divisions))
                cursor = capacity
        _bar(element, staff.barline_right, "right", f"{staff.staff_measure_id}-barlineRight")
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    timings = validate_musicxml(data)
    if read_projection(data) != score_projection(score):
        raise ValueError("MusicXML reparse differs from ScoreIR")
    return data, timings
