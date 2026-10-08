"""Remove only W2's explicit staff paths to obtain independent symbol-only SYN pixels."""

import argparse
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path


def prepare(root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for index in range(4):
        for font in ("Leipzig", "Bravura", "Leland"):
            name = f"train-smoke-{index}-{font}"
            tree = ET.fromstring(gzip.decompress((root / name / "page-1.svg.gz").read_bytes()))
            for staff in tree.iter():
                if "staff" in staff.get("class", "").split():
                    paths = [child for child in staff if child.tag.endswith("}path")]
                    if len(paths) != 5:
                        raise ValueError("W2 staff path provenance mismatch")
                    for child in paths:
                        staff.remove(child)
            svg = (
                ET.tostring(tree, encoding="unicode")
                .replace("ns0:", "")
                .replace("xmlns:ns0=", "xmlns=")
            )
            (output / (name + "-symbols.svg")).write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.output)
