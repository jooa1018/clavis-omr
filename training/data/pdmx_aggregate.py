"""Aggregate PDMX notation without retaining song IDs or per-song values."""

import io
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from collections.abc import Mapping

LICENSE_URLS = {
    "https://creativecommons.org/publicdomain/mark/1.0/": "PDM-1.0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0-1.0",
}


def eligible(row: Mapping[str, str]) -> bool:
    """Require agreeing license metadata and an explicit permitted license URL."""
    return (
        row.get("subset:no_license_conflict") == "True"
        and row.get("license_conflict") == "False"
        and row.get("license_url") in LICENSE_URLS
        and row.get("mxl", "").startswith("./mxl/")
        and row.get("mxl", "").endswith(".mxl")
        and ".." not in row.get("mxl", "").split("/")
    )


def notation_counts(xml: bytes, meters: set[str]) -> dict[str, Counter[str]]:
    """Count written pitched noteheads by type+dots, separately from rests/grace.

    Tied segments and chord members are separate written noteheads. All parts
    contribute. No repeats are unfolded. Missing/unsupported meter is excluded;
    missing type is counted as unknown rather than inferred from duration.
    """
    if b"<!ENTITY" in xml.upper():
        raise ValueError("XML entities are not supported")
    root = ET.fromstring(xml)
    if root.tag != "score-partwise":
        raise ValueError("Only unnamespaced score-partwise MusicXML is supported")
    totals: dict[str, Counter[str]] = {}
    for part in root.findall("part"):
        active: dict[str, str] = {}
        default = "unknown"
        for measure in part.findall("measure"):
            for event in measure:
                if event.tag == "attributes":
                    for time in event.findall("time"):
                        numerator, denominator = time.findall("beats"), time.findall("beat-type")
                        meter = "unknown"
                        if len(numerator) == len(denominator) == 1:
                            meter = f"{numerator[0].text}/{denominator[0].text}"
                        staff = time.get("number")
                        if staff is None:
                            default, active = meter, {}
                        else:
                            active[staff] = meter
                if event.tag != "note":
                    continue
                meter = active.get(event.findtext("staff", "1"), default)
                if meter not in meters:
                    continue
                counts = totals.setdefault(meter, Counter())
                if event.find("grace") is not None:
                    counts["grace"] += 1
                elif event.find("rest") is not None:
                    counts["rest"] += 1
                elif event.find("pitch") is not None:
                    kind = event.findtext("type", "unknown")
                    if kind not in {
                        "maxima",
                        "long",
                        "breve",
                        "whole",
                        "half",
                        "quarter",
                        "eighth",
                        "16th",
                        "32nd",
                        "64th",
                        "128th",
                        "256th",
                        "512th",
                        "1024th",
                    }:
                        kind = "unknown"
                    counts[f"note:{kind}:dots={len(event.findall('dot'))}"] += 1
                else:
                    counts["unpitched_or_missing_pitch"] += 1
    return totals


def unpack_mxl(payload: bytes, *, max_xml_bytes: int, max_ratio: int) -> bytes:
    """Read only the container-selected XML root into bounded memory; never extract."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist()) != len(set(archive.namelist())):
            raise ValueError("Duplicate ZIP members")
        for info in archive.infolist():
            if (
                info.file_size > max_xml_bytes
                or info.file_size > max(1, info.compress_size) * max_ratio
            ):
                raise ValueError("MXL member exceeds size/ratio limit")
        container = archive.read("META-INF/container.xml")
        if b"<!ENTITY" in container.upper():
            raise ValueError("Container entities are not supported")
        roots = ET.fromstring(container).findall(".//{*}rootfile")
        selected = [
            r.get("full-path")
            for r in roots
            if r.get("media-type") == "application/vnd.recordare.musicxml+xml"
        ]
        if len(selected) != 1 or selected[0] is None:
            raise ValueError("Exactly one MusicXML rootfile is required")
        return archive.read(selected[0])
