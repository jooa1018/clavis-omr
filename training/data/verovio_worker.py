"""Isolated renderer process only; never import this module from the engine."""

import importlib
import json
import sys
from importlib.metadata import version
from pathlib import Path


def main() -> None:
    """Render one MusicXML from stdin using a separately installed pinned toolkit."""
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if version("verovio") != config["renderer_version"]:
        raise ValueError("Renderer version mismatch")
    font = sys.argv[2]
    if font not in config["fonts"]:
        raise ValueError("Unregistered font")
    xml = sys.stdin.buffer.read(config["max_input_bytes"] + 1)
    if len(xml) > config["max_input_bytes"] or b"<!" in xml:
        raise ValueError("MusicXML size or declaration rejected")
    toolkit = importlib.import_module("verovio").toolkit()
    options = {**config["options"], "font": font}
    if not toolkit.setOptions(options) or not toolkit.loadData(xml.decode("utf-8")):
        raise ValueError("Renderer rejected options or input")
    if not 0 < toolkit.getPageCount() <= config["max_pages"]:
        raise ValueError("Page limit exceeded")
    pages = [toolkit.renderToSVG(page) for page in range(1, toolkit.getPageCount() + 1)]
    if not pages or any(len(page.encode()) > config["max_svg_bytes"] for page in pages):
        raise ValueError("Empty or oversized renderer output")
    print(json.dumps({"version": toolkit.getVersion(), "options": options, "pages": pages}))


if __name__ == "__main__":
    main()
