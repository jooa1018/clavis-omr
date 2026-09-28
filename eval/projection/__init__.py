"""Bounded, offline MusicXML projection for one part/staff/voice."""

import re
import unicodedata
from fractions import Fraction
from xml.etree import ElementTree as ET

from eval.policy import config, limit
from eval.projection.model import (
    Attribute,
    EvaluationUnsupported,
    Event,
    Harmony,
    Measure,
    Score,
    Value,
)


def required(node: ET.Element, path: str) -> str:
    value = node.findtext(path)
    if value is None or not value.strip():
        raise EvaluationUnsupported(f"missing:{path}")
    return value.strip()


def harmony_value(node: ET.Element) -> Value:
    # MusicXML 4.0 harmony: kind@text is typography, kind/degree are semantics.
    kinds = config("chord-degrees.json")["kinds"]
    kind = required(node, "kind")
    if kind not in kinds or len(node.findall("kind")) != 1:
        raise EvaluationUnsupported("harmony-kind-or-stack")
    root = node.findtext("root/root-step", "")
    bass = node.findtext("bass/bass-step", "")
    if (kind != "none" and root not in tuple("ABCDEFG")) or (bass and bass not in tuple("ABCDEFG")):
        raise EvaluationUnsupported("harmony-root-or-bass")
    degrees = {int(key): Fraction(value) for key, value in kinds[kind].items()}
    seen = set()
    for degree in node.findall("degree"):
        number = int(required(degree, "degree-value"))
        change = Fraction(required(degree, "degree-alter"))
        action = required(degree, "degree-type")
        if number in seen or number <= 0:
            raise EvaluationUnsupported("repeated-or-invalid-degree")
        seen.add(number)
        # MusicXML degree-alter: add is relative to dominant; alter is relative
        # to the kind's existing degree (W3C MusicXML 4.0 degree-alter).
        if action == "add" and number not in degrees:
            degrees[number] = change + (-1 if number == 7 else 0)
        elif action == "alter" and number in degrees:
            degrees[number] += change
        elif action == "subtract" and number in degrees and change == 0:
            del degrees[number]
        else:
            raise EvaluationUnsupported("degree-operation")
    if kind == "none":
        if degrees or bass:
            raise EvaluationUnsupported("no-chord-with-degrees-or-bass")
        return ("N.C.",)
    return (
        root,
        str(Fraction(node.findtext("root/root-alter", "0"))),
        bass,
        str(Fraction(node.findtext("bass/bass-alter", "0"))),
        *(f"{degree}:{alter}" for degree, alter in sorted(degrees.items())),
    )


def note_event(
    node: ET.Element, ref: str, onset: Fraction, divisions: Fraction, state: dict[str, Value]
) -> Event:
    grace = node.find("grace") is not None
    duration = Fraction(0) if grace else Fraction(required(node, "duration")) / divisions
    if (not grace and duration <= 0) or (grace and node.find("duration") is not None):
        raise EvaluationUnsupported("note-duration")
    kinds = [k for k in ("pitch", "rest", "unpitched") if node.find(k) is not None]
    if len(kinds) != 1:
        raise EvaluationUnsupported("note-kind")
    pitch = None
    accidental = False
    kind = {"pitch": "note", "rest": "rest", "unpitched": "rhythm"}[kinds[0]]
    if kind == "note":
        step = required(node, "pitch/step")
        if step not in tuple("ABCDEFG"):
            raise EvaluationUnsupported("pitch-step")
        alter = Fraction(node.findtext("pitch/alter", "0"))
        pitch = (step, alter, int(required(node, "pitch/octave")))
        fifths = int(state.get("key", ("0",))[0])
        order = "FCGDAEB" if fifths >= 0 else "BEADGCF"
        default = (1 if fifths >= 0 else -1) if step in order[: abs(fifths)] else 0
        accidental = alter != default or node.find("accidental") is not None
    if kind == "rhythm" and node.findtext("notehead") != "slash":
        raise EvaluationUnsupported("unpitched-nonslash")
    ties = {n.get("type") for n in [*node.findall("tie"), *node.findall("notations/tied")]}
    if not ties <= {"start", "stop"}:
        raise EvaluationUnsupported("tie-type")
    lyrics: list[tuple[str, str, str]] = []
    for lyric in node.findall("lyric"):
        if len(lyric.findall("text")) != 1 or lyric.find("elision") is not None:
            raise EvaluationUnsupported("lyric-elision-or-extension-only")
        verse = lyric.get("number", "1")
        if verse in {item[0] for item in lyrics}:
            raise EvaluationUnsupported("duplicate-verse")
        lyrics.append(
            (
                verse,
                unicodedata.normalize("NFC", required(lyric, "text")),
                lyric.findtext("syllabic", "single"),
            )
        )
    return Event(
        ref,
        kind,
        onset,
        duration,
        pitch,
        "start" in ties,
        "stop" in ties,
        grace,
        node.find("chord") is not None,
        tuple(sorted(lyrics)),
        accidental,
    )


def attribute_value(node: ET.Element) -> Value:
    if node.tag == "key":
        fifths = int(required(node, "fifths"))
        if abs(fifths) > len("FCGDAEB"):
            raise EvaluationUnsupported("nontraditional-key")
        return (str(fifths), node.findtext("mode", "major"))
    if node.tag == "time":
        if len(node.findall("beats")) != 1 or len(node.findall("beat-type")) != 1:
            raise EvaluationUnsupported("composite-meter")
        return (required(node, "beats"), required(node, "beat-type"))
    return (
        required(node, "sign"),
        node.findtext("line", ""),
        node.findtext("clef-octave-change", "0"),
    )


def _project(root: ET.Element) -> Score:
    if root.tag != "score-partwise" or len(root.findall("part")) != 1:
        raise EvaluationUnsupported("partwise-single-part-required")
    measures = root.findall("part/measure")
    if not measures or len(measures) > limit("maxMeasures"):
        raise EvaluationUnsupported("measure-limit-or-empty-score")
    # These change evaluated semantics beyond the first-PR projection scope.
    forbidden = {
        "transpose",
        "measure-style",
        "cue",
        "instrument",
        "function",
        "numeral",
        "key-step",
        "key-alter",
        "senza-misura",
        "direction",
        "sound",
    }
    if any(n.tag in forbidden for n in root.iter()):
        raise EvaluationUnsupported("semantic-element-outside-v0")
    state: dict[str, Value] = {}
    divisions: Fraction | None = None
    voices: set[str] = set()
    result = []
    for mi, measure in enumerate(measures):
        ref = f"m{mi}"
        cursor = Fraction(0)
        length = Fraction(0)
        events: list[Event] = []
        harmonies: list[Harmony] = []
        changes: list[Attribute] = []
        marks: list[Value] = []
        previous: Event | None = None
        for node in measure:
            if node.tag == "attributes":
                if node.findtext("staves", "1") != "1":
                    raise EvaluationUnsupported("multiple-staves")
                if node.find("divisions") is not None:
                    divisions = Fraction(required(node, "divisions"))
                    if divisions <= 0:
                        raise EvaluationUnsupported("divisions")
                for attr in node:
                    if attr.tag in {"key", "time", "clef"}:
                        if attr.get("number", "1") != "1":
                            raise EvaluationUnsupported("multiple-staves")
                        if cursor != 0:
                            raise EvaluationUnsupported("mid-measure-attributes")
                        value = attribute_value(attr)
                        if state.get(attr.tag) != value:
                            changes.append(Attribute(f"{ref}/{attr.tag}", attr.tag, cursor, value))
                            state[attr.tag] = value
            elif node.tag in {"note", "forward", "backup", "harmony"}:
                if divisions is None:
                    raise EvaluationUnsupported("missing-divisions")
                if node.findtext("staff", "1") != "1":
                    raise EvaluationUnsupported("multiple-staves")
                if node.tag in {"forward", "backup"}:
                    if node.find("voice") is not None:
                        voices.add(required(node, "voice"))
                        if len(voices) > 1:
                            raise EvaluationUnsupported("multiple-voices")
                    amount = Fraction(required(node, "duration")) / divisions
                    if amount <= 0:
                        raise EvaluationUnsupported("cursor-duration")
                    cursor += amount if node.tag == "forward" else -amount
                    if cursor < 0:
                        raise EvaluationUnsupported("negative-backup")
                    length = max(length, cursor)
                    previous = None
                elif node.tag == "harmony":
                    onset = cursor + Fraction(node.findtext("offset", "0")) / divisions
                    if onset < 0:
                        raise EvaluationUnsupported("negative-harmony-onset")
                    harmonies.append(
                        Harmony(f"{ref}/h{len(harmonies)}", onset, harmony_value(node))
                    )
                else:
                    voices.add(node.findtext("voice", "1"))
                    if len(voices) != 1:
                        raise EvaluationUnsupported("multiple-voices")
                    onset = cursor
                    if node.find("chord") is not None:
                        if previous is None:
                            raise EvaluationUnsupported("orphan-chord")
                        onset = previous.onset
                    event = note_event(node, f"{ref}/e{len(events)}", onset, divisions, state)
                    if event.chord_member:
                        if previous is None or event.duration > previous.duration:
                            raise EvaluationUnsupported("chord-duration")
                    else:
                        if any(e.onset + e.duration > onset for e in events if not e.grace):
                            raise EvaluationUnsupported("overlapping-single-voice")
                        cursor += event.duration
                    events.append(event)
                    length = max(length, cursor, event.onset + event.duration)
                    previous = event
            elif node.tag == "barline":
                for mark in node:
                    if mark.tag == "repeat":
                        marks.append(
                            (
                                node.get("location", "right"),
                                "repeat",
                                mark.get("direction", ""),
                                mark.get("times", "2"),
                            )
                        )
                    elif mark.tag == "ending":
                        marks.append(
                            (
                                node.get("location", "right"),
                                "ending",
                                mark.get("number", ""),
                                mark.get("type", ""),
                            )
                        )
            elif node.tag != "print":
                raise EvaluationUnsupported("measure-element-outside-v0")
        if max(len(events), len(harmonies)) > limit("maxEventsPerMeasure"):
            raise EvaluationUnsupported("events-per-measure-limit")
        result.append(
            Measure(
                ref,
                tuple(sorted(events, key=lambda e: e.onset)),
                tuple(sorted(harmonies, key=lambda h: h.onset)),
                tuple(changes),
                tuple(sorted(state.items())),
                tuple(marks),
                length,
            )
        )
    return Score(tuple(result))


def project(xml: bytes) -> Score:
    """Parse UTF-8 XML; never resolve DTDs, external entities or filesystem paths."""
    if len(xml) > limit("maxXmlBytes"):
        raise EvaluationUnsupported("xml-byte-limit")
    try:
        text = xml.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise EvaluationUnsupported("xml-dtd-or-entity")
        body = re.sub(r"^\s*<\?xml\s[^?]*\?>", "", text, count=1)
        if "<?" in body:
            raise EvaluationUnsupported("xml-processing-instruction")
        root = ET.fromstring(text)
        if sum(1 for _ in root.iter()) > limit("maxXmlNodes"):
            raise EvaluationUnsupported("xml-node-limit")
        for node in root.iter():
            if node.tag in {
                "duration",
                "divisions",
                "offset",
                "alter",
                "root-alter",
                "bass-alter",
                "degree-alter",
            } and not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", (node.text or "").strip()):
                raise EvaluationUnsupported("invalid-decimal")
        return _project(root)
    except (ET.ParseError, ValueError, ZeroDivisionError) as exc:
        if isinstance(exc, EvaluationUnsupported):
            raise
        raise EvaluationUnsupported("invalid-musicxml") from None
