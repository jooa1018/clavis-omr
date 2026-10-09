"""Independent audits of generated MusicXML, not an admission or repair path."""

from collections import Counter, defaultdict
from fractions import Fraction
from typing import Any
from xml.etree import ElementTree as ET

from training.data.pdmx_aggregate import notation_counts
from training.data.production_rhythm import Value


def audit(xml: str) -> dict[str, Any]:
    """Check cursor/voice sums, written durations and tie continuity; count actual marks."""
    root = ET.fromstring(xml)
    features: Counter[str] = Counter()
    measures = root.findall("./part/measure")
    active: dict[tuple[object, ...], Fraction] = {}
    absolute = Fraction()
    divisions = 0
    by_measure: Counter[str] = Counter()
    full = Fraction()
    for raw in measures:
        divisions = int(raw.findtext("attributes/divisions", str(divisions)))
        time = raw.find("attributes/time")
        if time is not None:
            full = Fraction(
                4 * int(time.findtext("beats", "0")), int(time.findtext("beat-type", "0"))
            )
        cursor, length, prior_onset = Fraction(), Fraction(), Fraction()
        previous: ET.Element | None = None
        voices: dict[str, Fraction] = defaultdict(Fraction)
        voice_ends: dict[str, Fraction] = defaultdict(Fraction)
        harmonies = []
        for event in raw:
            if event.tag in ("backup", "forward"):
                cursor += Fraction(int(event.findtext("duration", "0")), divisions) * (
                    -1 if event.tag == "backup" else 1
                )
                if cursor < 0:
                    raise ValueError("Negative cursor")
                previous = None
            elif event.tag == "harmony":
                harmonies.append(cursor + Fraction(int(event.findtext("offset", "0")), divisions))
            elif event.tag == "note":
                voice = event.findtext("voice", "1")
                grace = event.find("grace") is not None
                chord = event.find("chord") is not None
                duration = (
                    Fraction()
                    if grace
                    else Fraction(int(event.findtext("duration", "0")), divisions)
                )
                onset = prior_onset if chord else cursor
                if chord:
                    if (
                        previous is None
                        or previous.findtext("voice", "1") != voice
                        or previous.findtext("duration") != event.findtext("duration")
                    ):
                        raise ValueError("Chord duration/voice mismatch")
                elif not grace:
                    if voice_ends[voice] != onset:
                        raise ValueError("Voice gap or overlap")
                    voice_ends[voice] = onset + duration
                    voices[voice] += duration
                    cursor += duration
                identity = (
                    voice,
                    event.findtext("pitch/step"),
                    event.findtext("pitch/octave"),
                    event.findtext("pitch/alter", "0"),
                )
                if event.find("tie[@type='stop']") is not None:
                    if active.pop(identity, None) != absolute + onset:
                        raise ValueError("Tie pitch/voice/time discontinuity")
                if event.find("tie[@type='start']") is not None:
                    if identity in active:
                        raise ValueError("Unclosed tie start")
                    active[identity] = absolute + onset + duration
                length = max(length, onset + duration)
                prior_onset, previous = onset, event
        if raw.get("implicit") == "yes":
            if not 0 < length < full:
                raise ValueError("Invalid pickup length")
            features["pickup"] += 1
        elif length != full:
            raise ValueError("Invalid full measure length")
        if not voices or any(duration != length for duration in voices.values()):
            raise ValueError("Voice does not fill measure")
        by_measure["two_voice"] += int(len(voices) == 2)
        features["two_voice"] += int(len(voices) == 2)
        features["one_voice"] += int(len(voices) == 1)
        by_measure["slash"] += int(raw.find("note/notehead[.='slash']") is not None)
        by_measure["triplet"] += int(raw.find("note/time-modification") is not None)
        for note in raw.findall("note"):
            grace = note.find("grace") is not None
            rest = note.find("rest")
            if grace:
                features["grace"] += 1
            elif rest is None or rest.get("measure") != "yes":
                value = Value(note.findtext("type", ""), len(note.findall("dot")))
                written = value.quarters * divisions
                tm = note.find("time-modification")
                if tm is not None:
                    written *= Fraction(
                        int(tm.findtext("normal-notes", "0")), int(tm.findtext("actual-notes", "0"))
                    )
                if written != int(note.findtext("duration", "0")):
                    raise ValueError("Written duration mismatch")
            if not grace and note.find("pitch") is not None:
                features[f"duration:{note.findtext('type')}"] += 1
                dots = len(note.findall("dot"))
                if dots:
                    features[f"dots:{dots}"] += 1
            for label, path in {
                "rest": "rest",
                "accidental": "accidental",
                "chord": "chord",
                "triplet": "time-modification",
                "slash": "notehead[.='slash']",
                "fermata": "notations/fermata",
                "tie": "tie[@type='start']",
                "measure_rest": "rest[@measure='yes']",
            }.items():
                features[label] += int(note.find(path) is not None)
        for onset in harmonies:
            if not 0 <= onset < length:
                raise ValueError("Harmony outside measure")
        absolute += length
    if active:
        raise ValueError("Unclosed tie")
    for name, path in {
        "key_signature": ".//key",
        "meter_signature": ".//time",
        "repeat": ".//repeat",
        "volta": ".//ending",
        "segno": ".//segno",
        "coda": ".//coda",
        "dc": ".//sound[@dacapo='yes']",
        "ds": ".//sound[@dalsegno]",
        "fine": ".//sound[@fine]",
        "harmony": ".//harmony",
        "slash_harmony": ".//harmony/bass",
        "lyric": ".//lyric/text",
        "hyphen": ".//lyric/syllabic[.='begin']",
        "extend": ".//lyric/extend",
        "title": "work/work-title",
        "tempo": ".//metronome",
        "section": ".//direction-type/words",
    }.items():
        features[name] = len(root.findall(path))
    for clef in root.findall(".//clef"):
        name = clef.findtext("sign", "") + clef.findtext("line", "")
        if clef.findtext("clef-octave-change") == "-1":
            name += "_8vb"
        features[f"clef:{name}"] += 1
    features["key_meter_change"] = int(
        len(root.findall(".//key")) > 1 and len(root.findall(".//time")) > 1
    )
    features["repeat_volta_navigation"] = sum(features[k] for k in ("repeat", "volta", "dc", "ds"))
    texts = [n.text or "" for n in root.findall(".//lyric/text")]
    features["lyrics_ko"] = sum(any("\uac00" <= c <= "\ud7a3" for c in text) for text in texts)
    features["lyrics_en"] = sum(any("a" <= c.lower() <= "z" for c in text) for text in texts)
    features["multi_verse"] = sum(n.get("number", "1") != "1" for n in root.findall(".//lyric"))
    pitched = root.findall(".//note/pitch")
    return {
        "initial": {
            "key_mode": root.findtext(".//key/fifths", "") + ":" + root.findtext(".//key/mode", ""),
            "meter": root.findtext(".//time/beats", "")
            + "/"
            + root.findtext(".//time/beat-type", ""),
        },
        "features": dict(features),
        "measure_features": dict(by_measure),
        "measures": len(measures),
        "pitched_including_grace": len(pitched),
        "counts": notation_counts(xml.encode("utf-8"), {"4/4", "3/4", "6/8", "2/4", "12/8", "2/2"}),
    }
