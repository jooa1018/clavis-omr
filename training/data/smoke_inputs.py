"""Small deterministic self-authored MusicXML fixtures, not a training corpus."""

import xml.etree.ElementTree as ET


def score(seed: str, *, fifths: int, beats: int, staves: int) -> str:
    """Enumerate simple variants for renderer tests; no imported tune or lyrics."""
    if not seed.startswith("train-"):
        raise ValueError("Only train-* namespaces are permitted")
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
            for beat in range(beats):
                note = ET.SubElement(measure, "note")
                pitch = ET.SubElement(note, "pitch")
                ET.SubElement(pitch, "step").text = "CDEFGAB"[(beat + measure_index + staff) % 7]
                ET.SubElement(pitch, "octave").text = "4"
                ET.SubElement(note, "duration").text = "1"
                ET.SubElement(note, "voice").text = str(staff)
                ET.SubElement(note, "type").text = "quarter"
                ET.SubElement(note, "staff").text = str(staff)
    return ET.tostring(root, encoding="unicode")
