"""Self-authored MusicXML notation helpers for LeadGen production candidates."""

import copy
import xml.etree.ElementTree as ET
from fractions import Fraction
from typing import Any

import numpy as np

from training.data.production_rhythm import Value


def child(parent: ET.Element, tag: str, content: object | None = None, **attrs: str) -> ET.Element:
    element = ET.SubElement(parent, tag, attrs)
    if content is not None:
        element.text = str(content)
    return element


def pitch(degree: int, fifths: int, chromatic: int = 0) -> tuple[str, int, int]:
    step = "CDEFGAB"[degree % 7]
    changed = ("FCGDAEB" if fifths > 0 else "BEADGCF")[: abs(fifths)]
    alter = (1 if fifths > 0 else -1) if step in changed else 0
    return step, degree // 7, alter + chromatic


def attributes(
    measure: ET.Element,
    fifths: int,
    mode: str,
    meter: str,
    *,
    divisions: int | None = None,
    clef: str | None = None,
) -> None:
    attrs = ET.Element("attributes")
    measure.insert(0, attrs)
    if divisions is not None:
        child(attrs, "divisions", divisions)
    key = child(attrs, "key")
    child(key, "fifths", fifths)
    child(key, "mode", mode)
    beats, beat_type = meter.split("/")
    time = child(attrs, "time")
    child(time, "beats", beats)
    child(time, "beat-type", beat_type)
    if clef is not None:
        cg = child(attrs, "clef")
        child(cg, "sign", "F" if clef == "F4" else "G")
        child(cg, "line", 4 if clef == "F4" else 2)
        if clef == "G2_8vb":
            child(cg, "clef-octave-change", -1)


def note(
    measure: ET.Element,
    value: Value,
    pitch_value: tuple[str, int, int] | None,
    divisions: int,
    *,
    voice: int = 1,
    slash: bool = False,
    triplet: bool = False,
    grace: bool = False,
    accidental: bool = False,
) -> ET.Element:
    event = child(measure, "note")
    if grace:
        child(event, "grace", slash="yes")
    if slash:
        unpitched = child(event, "unpitched")
        child(unpitched, "display-step", "B")
        child(unpitched, "display-octave", 4)
    elif pitch_value is None:
        child(event, "rest")
    else:
        step, octave, alter = pitch_value
        pc = child(event, "pitch")
        child(pc, "step", step)
        child(pc, "alter", alter)
        child(pc, "octave", octave)
    duration = value.quarters * divisions * (Fraction(2, 3) if triplet else 1)
    if duration.denominator != 1:
        raise ValueError("Divisions cannot express written rhythm exactly")
    if not grace:
        child(event, "duration", int(duration))
    child(event, "voice", voice)
    child(event, "type", value.kind)
    for _ in range(value.dots):
        child(event, "dot")
    if accidental and pitch_value is not None and not slash:
        names = {-2: "flat-flat", -1: "flat", 0: "natural", 1: "sharp", 2: "double-sharp"}
        child(event, "accidental", names[pitch_value[2]])
    if triplet:
        tm = child(event, "time-modification")
        child(tm, "actual-notes", 3)
        child(tm, "normal-notes", 2)
        child(tm, "normal-type", value.kind)
    if pitch_value is not None or slash:
        child(event, "stem", "down" if voice == 2 else "up")
    if slash:
        child(event, "notehead", "slash")
    return event


def notation(event: ET.Element) -> ET.Element:
    existing = event.find("notations")
    return existing if existing is not None else child(event, "notations")


def tie_pair(first: ET.Element, second: ET.Element) -> None:
    source = first.find("pitch")
    destination = second.find("pitch")
    if source is None or destination is None:
        raise ValueError("Ties require explicit pitches")
    second.remove(destination)
    second.insert(0, copy.deepcopy(source))
    accidental = second.find("accidental")
    if accidental is not None:
        second.remove(accidental)
    for event, kind in ((first, "start"), (second, "stop")):
        duration = event.find("duration")
        if duration is None:
            raise ValueError("Ties require duration-bearing notes")
        offset = list(event).index(duration) + 1
        event.insert(offset, ET.Element("tie", type=kind))
        child(notation(event), "tied", type=kind)


def harmony(
    measure: ET.Element,
    root: tuple[str, int, int],
    spec: dict[str, Any],
    offset: int,
    bass: tuple[str, int, int] | None,
) -> None:
    h = child(measure, "harmony")
    r = child(h, "root")
    child(r, "root-step", root[0])
    child(r, "root-alter", root[2])
    child(h, "kind", spec["kind"], text=spec["text"])
    if bass is not None:
        b = child(h, "bass")
        child(b, "bass-step", bass[0])
        child(b, "bass-alter", bass[2])
    for degree in spec.get("degrees", []):
        d = child(h, "degree")
        child(d, "degree-value", degree["value"])
        child(d, "degree-alter", degree["alter"])
        child(d, "degree-type", degree["type"])
    child(h, "offset", offset)


def direction(measure: ET.Element, text: str, **sound: str) -> None:
    d = child(measure, "direction")
    child(child(d, "direction-type"), "words", text)
    if sound:
        child(d, "sound", **sound)


def navigation(measures: list[ET.Element], rng: np.random.Generator) -> None:
    """Self-contained repeats/endings plus one consistent DC-Fine or DS-Coda route."""
    start, ending, repeat_end, final = measures[0], measures[-3], measures[-2], measures[-1]
    route = int(rng.integers(3))
    if route == 0:
        child(child(start, "barline", location="left"), "repeat", direction="forward")
        child(child(ending, "barline", location="left"), "ending", number="1", type="start")
        right = child(repeat_end, "barline", location="right")
        child(right, "ending", number="1", type="stop")
        child(right, "repeat", direction="backward")
        child(child(final, "barline", location="left"), "ending", number="2", type="start")
        child(child(final, "barline", location="right"), "ending", number="2", type="discontinue")
    elif route == 1:
        direction(ending, "Fine", fine="yes")
        direction(final, "D.C. al Fine", dacapo="yes")
    else:
        d = ET.Element("direction")
        child(child(d, "direction-type"), "segno")
        child(d, "sound", segno="S")
        insertion = next((i for i, event in enumerate(start) if event.tag == "note"), len(start))
        start.insert(insertion, d)
        direction(ending, "To Coda", tocoda="C", **{"time-only": "2"})
        direction(repeat_end, "D.S. al Coda", dalsegno="S")
        d = ET.Element("direction")
        child(child(d, "direction-type"), "coda")
        child(d, "sound", coda="C")
        insertion = next((i for i, event in enumerate(final) if event.tag == "note"), len(final))
        final.insert(insertion, d)


def lyrics(events: list[ET.Element], config: dict[str, Any], rng: np.random.Generator) -> None:
    candidates = [
        event
        for event in events
        if event.find("rest") is None
        and event.find("grace") is None
        and event.find("chord") is None
        and not any(t.get("type") == "stop" for t in event.findall("tie"))
    ]
    verses = int(rng.integers(1, config["max_verses"] + 1))
    for verse in range(1, verses + 1):
        syllables = config["lyric_syllables"][int(rng.integers(len(config["lyric_syllables"])))]
        extending = False
        syllable_position = 0
        for position, event in enumerate(candidates):
            lyric = child(event, "lyric", number=str(verse))
            if extending:
                child(lyric, "extend", type="stop")
                extending = False
                continue
            text, syllabic = syllables[syllable_position % len(syllables)]
            child(lyric, "syllabic", syllabic)
            child(lyric, "text", text)
            syllable_position += 1
            if syllable_position % len(syllables) == 0 and position + 1 < len(candidates):
                child(lyric, "extend", type="start")
                extending = True


def spell_accidentals(part: ET.Element) -> None:
    """Spell final authored pitches after ties/chords/graces have changed the notes.

    MusicXML pitch/alter is sounding truth; accidental is its printed spelling.
    State is shared by voices at the same staff pitch and resets at a barline.
    Conflicting simultaneous alterations are explicit and leave state unknown.
    """
    fifths = 0
    names = {-2: "flat-flat", -1: "flat", 0: "natural", 1: "sharp", 2: "double-sharp"}
    for measure in part.findall("measure"):
        fifths = int(measure.findtext("attributes/key/fifths", str(fifths)))
        groups: dict[tuple[int, bool], list[ET.Element]] = {}
        cursor, onset = 0, 0
        for event in measure:
            if event.tag in ("backup", "forward"):
                cursor += int(event.findtext("duration", "0")) * (
                    -1 if event.tag == "backup" else 1
                )
            elif event.tag == "note":
                if event.find("chord") is None:
                    onset = cursor
                grace = event.find("grace") is not None
                if event.find("pitch") is not None:
                    groups.setdefault((onset, not grace), []).append(event)
                if not grace and event.find("chord") is None:
                    cursor += int(event.findtext("duration", "0"))
        state: dict[tuple[str, int], int | None] = {}
        for moment in sorted(groups):
            by_pitch: dict[tuple[str, int], list[ET.Element]] = {}
            for event in groups[moment]:
                key = (event.findtext("pitch/step", "C"), int(event.findtext("pitch/octave", "4")))
                by_pitch.setdefault(key, []).append(event)
            for (step, octave), events in by_pitch.items():
                alters = {int(event.findtext("pitch/alter", "0")) for event in events}
                prior = state.get(
                    (step, octave), pitch("CDEFGAB".index(step) + 7 * octave, fifths)[2]
                )
                for event in events:
                    for old in event.findall("accidental"):
                        event.remove(old)
                    alter = int(event.findtext("pitch/alter", "0"))
                    if alter != prior or len(alters) != 1:
                        mark = ET.Element("accidental")
                        mark.text = names[alter]
                        insert = next(
                            i + 1
                            for i in reversed(range(len(event)))
                            if event[i].tag in ("type", "dot")
                        )
                        event.insert(insert, mark)
                state[(step, octave)] = next(iter(alters)) if len(alters) == 1 else None
