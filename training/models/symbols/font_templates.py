"""Build OFL notehead templates from the W2-pinned renderer's font resources.

This is a glyph-template consumer, not a score generator or training manifest.
Optional resvg-py (MIT) rasterizes the font outlines outside the engine.
"""

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image, ImageFilter

from clavis.symbols.detection import Template
from training.data.licenses import require_use

CONFIG = Path(__file__).resolve().parents[3] / "configs/symbols/template-build.json"


def build(font: str, staff_space: int) -> tuple[list[Template], dict[str, object]]:
    """Render filled, hollow and whole heads plus one provisional blur variant."""
    import resvg_py

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if font not in config["fonts"] or staff_space <= 0:
        raise ValueError("Expected registered OFL font and positive staff spacing")
    require_use(font.lower(), "render-font")
    spec = importlib.util.find_spec("verovio")
    if spec is None or spec.origin is None:
        raise RuntimeError("Install the W2-pinned renderer resources first")
    root = Path(spec.origin).parent / "data"
    metadata_bytes = (root / f"{font}.xml").read_bytes()
    metadata = ET.fromstring(metadata_bytes)
    # SMuFL engraving-font em = four staff spaces; Verovio metadata declares em units.
    scale = staff_space * 4 / int(metadata.attrib["units-per-em"])
    records, templates = [], []
    for glyph, name in config["glyphs"].items():
        bbox = next(g for g in metadata if g.attrib.get("c") == glyph)
        x, y, width, height = (float(bbox.attrib[k]) for k in ("x", "y", "w", "h"))
        outline = (root / font / f"{glyph}.xml").read_bytes()
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{x} {-y - height} {width} {height}" '
            f'width="{max(1, round(width * scale))}" height="{max(1, round(height * scale))}">'
            + outline.decode()
            + "</svg>"
        )
        png = resvg_py.svg_to_bytes(svg_string=svg, background="white", skip_system_fonts=True)
        image = Image.open(io.BytesIO(png)).convert("L")
        # Provisional optical variants, never fitted to a Dev image.
        for sigma in (staff_space * ratio for ratio in config["blur_sigma_spaces"]):
            pixels = np.asarray(image.filter(ImageFilter.GaussianBlur(sigma))).copy()
            templates.append(Template(name, pixels))
        records.append(
            {"glyph": glyph, "class": name, "outline_sha256": hashlib.sha256(outline).hexdigest()}
        )
    return templates, {
        "font": font,
        "license": "OFL-1.1",
        "staff_space": staff_space,
        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "glyphs": records,
        "variants": len(templates),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    bank, records = [], []
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for font in config["fonts"]:
        templates, record = build(font, config["staff_space"])
        bank.extend(templates)
        records.append(record)
    arrays = {f"t{i}": t.pixels for i, t in enumerate(bank)}
    np.savez_compressed(args.output / "templates.npz", **arrays)
    report = {
        "status": "PARTIAL",
        "scope": "OFL glyph construction; NOT SYN-Val",
        "fonts": records,
        "classes": [t.symbol_class for t in bank],
        "template_sha256": hashlib.sha256((args.output / "templates.npz").read_bytes()).hexdigest(),
        "recognition_accuracy": "NOT_RUN; no symbol box labels available",
    }
    (args.output / "manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
