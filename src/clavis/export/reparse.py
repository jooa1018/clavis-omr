"""Independent minimal output reader; intentionally no W4 evaluator import."""

import xml.etree.ElementTree as ET
from fractions import Fraction

from clavis.contracts.score import ScoreIR


def score_projection(score: ScoreIR) -> tuple[object, ...]:
    result: list[object] = []
    for measure in score.measures:
        staff = measure.staff_measures[0]
        events: list[object] = []
        for voice in staff.voices:
            for e in voice.events:
                events.append(
                    (
                        e.event_id,
                        str(voice.voice),
                        e.kind,
                        Fraction(e.onset.n, e.onset.d),
                        Fraction(e.duration.n, e.duration.d),
                        (e.pitch.step, e.pitch.alter, e.pitch.octave) if e.pitch else None,
                        e.tie.start,
                        e.tie.stop,
                        e.chord_with_prev,
                        e.grace,
                        e.measure_rest,
                        e.slur.start,
                        e.slur.stop,
                        e.fermata,
                        None if e.measure_rest else (e.notated.type, e.notated.dots),
                        (e.notated.tuplet.actual, e.notated.tuplet.normal)
                        if e.notated.tuplet
                        else None,
                        e.accidental_visible,
                    )
                )
        attributes = (
            staff.clef.sign if staff.clef else None,
            staff.key.fifths if staff.key else None,
            (staff.time.beats, staff.time.beat_type, staff.time.symbol) if staff.time else None,
            staff.barline_left.style if staff.barline_left else None,
            staff.barline_right.style if staff.barline_right else None,
        )
        result.append(
            (measure.measure_id, measure.number, measure.implicit, attributes, tuple(events))
        )
    return tuple(result)


def read_projection(data: bytes) -> tuple[object, ...]:
    """Only reads writer output after the mandatory safe parser/XSD validation."""
    root = ET.fromstring(data)
    result: list[object] = []
    divisions = Fraction(1)
    for measure in root.findall("part/measure"):
        cursor = Fraction(0)
        preceding_onset = Fraction(0)
        events: list[object] = []
        for element in measure:
            if element.tag == "attributes":
                divisions = Fraction(element.findtext("divisions", str(divisions)))
            elif element.tag in ("backup", "forward"):
                change = Fraction(element.findtext("duration", "0")) / divisions
                cursor += -change if element.tag == "backup" else change
            elif element.tag == "note":
                chord = element.find("chord") is not None
                grace = element.find("grace")
                onset = preceding_onset if chord else cursor
                length = Fraction(element.findtext("duration", "0")) / divisions
                pitch_element = element.find("pitch")
                pitch = (
                    None
                    if pitch_element is None
                    else (
                        pitch_element.findtext("step"),
                        int(pitch_element.findtext("alter", "0")),
                        int(pitch_element.findtext("octave", "0")),
                    )
                )
                rest = element.find("rest")
                kind = "rest" if rest is not None else "note" if pitch else "rhythm"
                ties = {e.get("type") for e in element.findall("tie")}
                if ties != {e.get("type") for e in element.findall("notations/tied")}:
                    raise ValueError("tie playback/notation mismatch")
                slurs = {e.get("type") for e in element.findall("notations/slur")}
                events.append(
                    (
                        element.get("id"),
                        element.findtext("voice", "1"),
                        kind,
                        onset,
                        length,
                        pitch,
                        "start" in ties,
                        "stop" in ties,
                        chord,
                        None
                        if grace is None
                        else "acciaccatura"
                        if grace.get("slash") == "yes"
                        else "appoggiatura",
                        rest is not None and rest.get("measure") == "yes",
                        "start" in slurs,
                        "stop" in slurs,
                        element.find("notations/fermata") is not None,
                        None
                        if rest is not None and rest.get("measure") == "yes"
                        else (element.findtext("type"), len(element.findall("dot"))),
                        (
                            int(element.findtext("time-modification/actual-notes", "0")),
                            int(element.findtext("time-modification/normal-notes", "0")),
                        )
                        if element.find("time-modification") is not None
                        else None,
                        {"double-sharp": "doubleSharp", "flat-flat": "doubleFlat"}.get(
                            element.findtext("accidental", ""), element.findtext("accidental")
                        ),
                    )
                )
                if not chord:
                    preceding_onset = onset
                    cursor += length
        result.append(
            (
                measure.get("id"),
                measure.get("number"),
                measure.get("implicit") == "yes",
                _attributes(measure),
                tuple(events),
            )
        )
    return tuple(result)


def _attributes(measure: ET.Element) -> tuple[object, ...]:
    clef = measure.find("attributes/clef")
    clef_name = None
    if clef is not None:
        clef_name = str(clef.findtext("sign")) + str(clef.findtext("line"))
        change = int(clef.findtext("clef-octave-change", "0"))
        if change:
            clef_name += "_8va" if change > 0 else "_8vb"
    fifths = measure.findtext("attributes/key/fifths")
    time = measure.find("attributes/time")
    styles = {
        "regular": "regular",
        "light-light": "double",
        "light-heavy": "final",
        "dashed": "dashed",
        "heavy": "heavy",
    }
    bars = {}
    for bar in measure.findall("barline"):
        repeat = bar.find("repeat")
        if repeat is not None:
            value = "repeatStart" if repeat.get("direction") == "forward" else "repeatEnd"
        else:
            value = styles[bar.findtext("bar-style", "regular")]
        bars[bar.get("location", "right")] = value
    return (
        clef_name,
        int(fifths) if fifths is not None else None,
        (int(time.findtext("beats", "0")), int(time.findtext("beat-type", "0")), time.get("symbol"))
        if time is not None
        else None,
        bars.get("left"),
        bars.get("right"),
    )
