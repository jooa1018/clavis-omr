"""Extract renderer-owned staff paths; never infer missing lines from music."""

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

SVG = "{http://www.w3.org/2000/svg}"
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
LINE = re.compile(rf"\s*M\s*({NUMBER})[,\s]+({NUMBER})\s*L\s*({NUMBER})[,\s]+({NUMBER})\s*")


@dataclass(frozen=True)
class StaffSegment:
    """Intermediate label, not StaffGeometry IR; coordinates are SVG staff-local."""

    system_id: str
    measure_id: str
    staff_id: str
    staff_number: str
    polylines: list[list[list[float]]]


def extract(svg: str, *, max_bytes: int, enabled: bool = True) -> tuple[list[StaffSegment], str]:
    """Return exact source polylines and an overlay in the same SVG coordinate tree.

    Verovio owns the system/measure/staff groups and staff@n metadata. Only direct
    staff paths are lines; nested note/ledger paths must never become staff labels.
    Unsupported renderer structures fail closed instead of estimating geometry.
    """
    if not enabled:
        raise ValueError("DATA-SVG-001 disabled; no staff labels emitted")
    if len(svg.encode("utf-8")) > max_bytes or "<!" in svg:
        raise ValueError("SVG size or declaration rejected")
    root = ET.fromstring(svg)
    if root.tag != SVG + "svg":
        raise ValueError("Expected SVG namespace")
    labels: list[StaffSegment] = []
    seen: set[str] = set()

    def visit(node: ET.Element, system: str = "", measure: str = "") -> None:
        classes = node.get("class", "").split()
        if "system" in classes:
            system = node.get("id", "")
        if "measure" in classes:
            measure = node.get("id", "")
        if "staff" in classes:
            staff = node.get("id", "")
            number = node.get("data-n", "")
            if not all((system, measure, staff, number)) or staff in seen:
                raise ValueError("Missing or duplicate staff provenance")
            seen.add(staff)
            paths = [child for child in node if child.tag == SVG + "path"]
            if len(paths) != 5:
                raise ValueError("Expected five explicit staff lines")
            lines: list[list[list[float]]] = []
            for path in paths:
                match = LINE.fullmatch(path.get("d", ""))
                if match is None or path.get("transform") or path.get("style"):
                    raise ValueError("Unsupported staff path")
                x1, y1, x2, y2 = map(float, match.groups())
                if not all(map(math.isfinite, (x1, y1, x2, y2))) or y1 != y2 or x1 >= x2:
                    raise ValueError("Expected finite horizontal staff path")
                lines.append([[x1, y1], [x2, y2]])
            lines.sort(key=lambda points: points[0][1])
            gaps = [b[0][1] - a[0][1] for a, b in zip(lines, lines[1:], strict=False)]
            if min(gaps) <= 0:
                raise ValueError("Repeated staff line")
            labels.append(StaffSegment(system, measure, staff, number, lines))
            overlay = ET.SubElement(node, SVG + "g", {"class": "clavis-staff-audit"})
            ET.SubElement(overlay, SVG + "title").text = f"{system}/{number} ({staff})"
            for points in lines:
                ET.SubElement(
                    overlay,
                    SVG + "polyline",
                    {
                        "points": " ".join(f"{x},{y}" for x, y in points),
                        "fill": "none",
                        "stroke": "#e00078",
                        "stroke-opacity": "0.65",
                        "stroke-width": str(min(gaps) / 8),
                    },
                )
        for child in list(node):
            visit(child, system, measure)

    visit(root)
    if not labels:
        raise ValueError("No staff evidence")
    return labels, ET.tostring(root, encoding="unicode")


def label_document(labels: list[StaffSegment]) -> dict[str, object]:
    """Keep coordinate semantics explicit; do not impersonate a runtime contract."""
    return {
        "format": "w2-staff-audit-v0",
        "coordinate_frame": "svg-staff-local",
        "mapping": "SVG ancestor viewBox/transform chain addressed by staff_id",
        "segments": [asdict(label) for label in labels],
    }
