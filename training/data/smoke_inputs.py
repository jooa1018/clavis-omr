"""Small deterministic self-authored MusicXML fixtures, not a training corpus."""

import hashlib
import xml.etree.ElementTree as ET

import numpy as np


def score(seed: str, *, fifths: int, beats: int, staves: int) -> str:
    """Enumerate simple variants for renderer tests; no imported tune or lyrics."""
    if not seed.startswith("train-"):
        raise ValueError("Only train-* namespaces are permitted")
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed.encode()).digest(), "big"))
    degrees = [int(rng.integers(2, 6)) for _ in range(staves)]
    altered_steps = ("FCGDAEB" if fifths > 0 else "BEADGCF")[: abs(fifths)]
    root = ET.Element("score-partwise", version="4.0")
    parts = ET.SubElement(root, "part-list")
    part_info = ET.SubElement(parts, "score-part", id="P1")
    ET.SubElement(part_info, "part-name").text = ""
    part = ET.SubElement(root, "part", id="P1")
    for measure_index in range(4):
        measure = ET.SubElement(part, "measure", number=str(measure_index + 1))
        if measure_index == 2:
            ET.SubElement(measure, "print", {"new-system": "yes"})
        if measure_index == 0:
            attrs = ET.SubElement(measure, "attributes")
            ET.SubElement(attrs, "divisions").text = "1"
            ET.SubElement(ET.SubElement(attrs, "key"), "fifths").text = str(fifths)
            time = ET.SubElement(attrs, "time")
            ET.SubElement(time, "beats").text = str(beats)
            ET.SubElement(time, "beat-type").text = "4"
            ET.SubElement(attrs, "staves").text = str(staves)
            for staff in range(1, staves + 1):
                clef = ET.SubElement(attrs, "clef", number=str(staff))
                ET.SubElement(clef, "sign").text = "G"
                ET.SubElement(clef, "line").text = "2"
        for staff in range(1, staves + 1):
            if staff > 1:
                ET.SubElement(ET.SubElement(measure, "backup"), "duration").text = str(beats)
            for _ in range(beats):
                degrees[staff - 1] = int(np.clip(degrees[staff - 1] + rng.integers(-2, 3), 0, 13))
                degree = degrees[staff - 1]
                step = "CDEFGAB"[degree % 7]
                note = ET.SubElement(measure, "note")
                pitch = ET.SubElement(note, "pitch")
                ET.SubElement(pitch, "step").text = step
                if step in altered_steps:
                    ET.SubElement(pitch, "alter").text = "1" if fifths > 0 else "-1"
                ET.SubElement(pitch, "octave").text = str(4 + degree // 7)
                ET.SubElement(note, "duration").text = "1"
                ET.SubElement(note, "voice").text = str(staff)
                ET.SubElement(note, "type").text = "quarter"
                ET.SubElement(note, "staff").text = str(staff)
    return ET.tostring(root, encoding="unicode")
