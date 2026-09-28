import json
import xml.etree.ElementTree as ET
from dataclasses import asdict

import pytest

from training.data.staff_svg import SVG, extract, label_document


def fixture_svg(*, staves: int = 2, systems: int = 2) -> str:
    root = ET.Element(SVG + "svg", viewBox="0 0 200 400")
    inner = ET.SubElement(root, SVG + "svg", viewBox="0 0 2000 4000")
    for system in range(systems):
        group = ET.SubElement(
            inner,
            SVG + "g",
            {"id": f"sys{system}", "class": "system", "transform": "translate(10,20) scale(2)"},
        )
        for measure in range(2):
            mg = ET.SubElement(group, SVG + "g", {"id": f"m{system}-{measure}", "class": "measure"})
            for staff in range(staves):
                sg = ET.SubElement(
                    mg,
                    SVG + "g",
                    {
                        "id": f"s{system}-{measure}-{staff}",
                        "class": "staff",
                        "data-n": str(staff + 1),
                    },
                )
                for line in range(5):
                    y = system * 500 + staff * 100 + line * 10
                    ET.SubElement(sg, SVG + "path", d=f"M 0 {y} L 100 {y}")
                ledger = ET.SubElement(sg, SVG + "g", {"class": "ledgerLines"})
                ET.SubElement(ledger, SVG + "path", d="M 20 60 L 30 60")
    return ET.tostring(root, encoding="unicode")


def test_provenance_and_overlay_under_identical_coordinate_context() -> None:
    svg = fixture_svg()
    labels, overlay = extract(svg, max_bytes=100_000)
    assert len(labels) == 8
    assert labels[0].polylines[0] == [[0, 0], [100, 0]]
    assert labels[-1].system_id == "sys1"
    assert labels[-1].staff_number == "2"
    assert len({(x.system_id, x.staff_number) for x in labels}) == 4
    root = ET.fromstring(overlay)
    for label in labels:
        staff = next(e for e in root.iter() if e.get("id") == label.staff_id)
        polylines = staff.findall(f"{SVG}g[@class='clavis-staff-audit']/{SVG}polyline")
        assert len(polylines) == 5
        assert all(line.get("style") == "stroke:#e00078" for line in polylines)
        assert [
            [list(map(float, p.split(","))) for p in line.get("points", "").split()]
            for line in polylines
        ] == label.polylines
    assert label_document(labels)["segments"] == [asdict(x) for x in labels]
    assert extract(svg, max_bytes=100_000) == extract(svg, max_bytes=100_000)


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.replace('data-n="1"', 'other="1"'),
        lambda s: s.replace('id="s0-0-1"', 'id="s0-0-0"'),
        lambda s: s.replace("M 0 0 L 100 0", "M 0 0 Q 50 0 100 0"),
        lambda s: s.replace("M 0 0 L 100 0", "M 0 0 L 100 1"),
        lambda s: s.replace("M 0 0 L 100 0", "M 100 0 L 0 0"),
        lambda s: s.replace("M 0 0 L 100 0", "M 0 10 L 100 10"),
        lambda s: s.replace("M 0 0 L 100 0", "M 0 0 L 1e999 0"),
        lambda s: s.replace('d="M 0 0 L 100 0"', 'transform="scale(2)" d="M 0 0 L 100 0"'),
        lambda s: s.replace('d="M 0 0 L 100 0"', 'style="display:none" d="M 0 0 L 100 0"'),
        lambda s: s.replace('<ns0:path d="M 0 0 L 100 0" />', ""),
        lambda s: "<!DOCTYPE svg>" + s,
        lambda s: "<svg/>",
        lambda s: '<svg xmlns="http://www.w3.org/2000/svg"/>',
    ],
)
def test_unsupported_or_incomplete_evidence_fails(change) -> None:
    with pytest.raises(ValueError):
        extract(change(fixture_svg()), max_bytes=100_000)


def test_size_limit() -> None:
    with pytest.raises(ValueError, match="size"):
        extract(fixture_svg(), max_bytes=1)
    with pytest.raises(ValueError, match="disabled"):
        extract(fixture_svg(), max_bytes=100_000, enabled=False)


def test_label_json_roundtrip() -> None:
    labels, _ = extract(fixture_svg(), max_bytes=100_000)
    assert json.loads(json.dumps(label_document(labels))) == label_document(labels)
