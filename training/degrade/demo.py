"""One original schematic score, five resolutions; no external data or fonts."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw
from PIL import __version__ as pillow_version

from training.degrade.ops import Array, Labels, Params, run


def render(spec: Params) -> tuple[Array, Labels]:
    """Draw a self-authored staff/note schematic, not a semantic W2 MusicXML renderer."""
    width, height = spec["size"]
    space = spec["interline"]
    image = np.full((height, width), 255, np.uint8)
    mask = np.zeros_like(image)
    points, boxes, lines, pairs = [], [], [], []
    left, right = space * 4, width - space * 4
    for system in range(spec["systems"]):
        top = space * (4 + system * 12)
        for line in range(5):
            y = top + line * space
            cv2.line(image, (left, y), (right, y), (0,), 1)
            lines.append(np.array([[left, y], [right, y]], float))
        pairs.extend([[[x, top], [x, top + space]] for x in (left, (left + right) / 2, right)])
        for index, step in enumerate(spec["note_steps"]):
            x, y = left + (index + 1) * space * 4, top + step * space // 2
            rx, ry = space // 2, space // 3
            cv2.ellipse(image, (x, y), (rx, ry), -20, 0, 360, (0,), -1)
            cv2.ellipse(mask, (x, y), (rx, ry), -20, 0, 360, (1,), -1)
            cv2.line(image, (x + rx, y), (x + rx, y - space * 3), (0,), 2)
            points.append([x, y])
            boxes.append([x - rx - ry, y - ry - rx, x + rx + ry, y + ry + rx])
    return image, Labels(
        np.array(points, float),
        np.array(boxes, float),
        tuple(lines),
        (mask,),
        np.array(pairs, float),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/degrade/first-pr.yaml"))
    parser.add_argument("--output", type=Path, default=Path("work/degrade-demo"))
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    started = time.perf_counter()
    source, labels = render(config["demo"])
    Image.fromarray(source).save(args.output / "source.png")
    width, height = config["demo"]["size"]
    frame = np.diag([width, height, 1])
    matrix = frame @ np.array(config["demo"]["normalized_homography"]) @ np.linalg.inv(frame)
    records, previews = [], []
    for target in config["demo"]["targets"]:
        operations = [dict(op) for op in config["operations"]]
        operations[1]["matrix"] = matrix.tolist()
        operations[2]["target_interline"] = target
        output, moved, applied = run(
            source,
            labels,
            np.random.default_rng(config["demo"]["seed"]),
            {**config, "operations": operations},
        )
        filename = f"interline-{target}.png"
        Image.fromarray(output).save(args.output / filename)
        np.savez_compressed(
            args.output / f"labels-{target}.npz",
            points=moved.points,
            boxes=moved.boxes,
            polylines=np.array(moved.polylines),
            mask=moved.masks[0],
            interline_pairs=moved.interline_pairs,
            interline_tangents=moved.tangents,
        )
        records.append({"file": filename, "target": target, "applied": applied})
        preview = Image.fromarray(output)
        preview.thumbnail((256, 340))
        previews.append((target, preview))
    sheet = Image.new("RGB", (256 * len(previews), 380), "#e8e8e8")
    draw = ImageDraw.Draw(sheet)
    for index, (target, preview) in enumerate(previews):
        draw.text((index * 256 + 12, 10), f"interline {target} px", fill="black")
        sheet.paste(preview, (index * 256, 35))
    sheet.save(args.output / "overview.png")
    files = []
    for path in sorted(args.output.glob("*")):
        if path.suffix in (".png", ".npz"):
            files.append(
                {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "license": "CC0-1.0",
                    "source": "W3 self-authored schematic",
                    "split": "synthetic-demo",
                }
            )
    report = {
        "scope": "synthetic-demo, local CPU, automatic; not Dev/SYN-Val or recognition metrics",
        "seed": config["demo"]["seed"],
        "wall_seconds": time.perf_counter() - started,
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "versions": {
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "pillow": pillow_version,
        },
        "records": records,
        "manifest": files,
    }
    (args.output / "demo.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
