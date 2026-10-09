"""Verify bundled MusicXML specification bytes and distribution notices."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path


def verify(wheel: Path) -> dict[str, object]:
    prefix = "clavis/export/schemas/musicxml-4.0/"
    with zipfile.ZipFile(wheel) as archive:
        manifest = json.loads(archive.read(prefix + "manifest.json"))
        if manifest["specification"] != "MusicXML 4.0":
            raise ValueError("unexpected specification")
        if {row["file"] for row in manifest["files"]} != {"musicxml.xsd", "xlink.xsd", "xml.xsd"}:
            raise ValueError("expected exactly three approved XSDs")
        for row in manifest["files"]:
            data = archive.read(prefix + row["file"])
            if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("schema bytes differ from original")
        for name in (prefix + "NOTICE", "clavis/THIRD_PARTY_NOTICES.md"):
            if b"MusicXML 4.0" not in archive.read(name):
                raise ValueError("missing specification notice")
    return {"status": "PASS", "wheel": wheel.name, "specification": manifest}


if __name__ == "__main__":
    wheels = list(Path(sys.argv[1]).glob("clavis_omr-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("expected one Clavis wheel")
    print(json.dumps(verify(wheels[0]), sort_keys=True))
