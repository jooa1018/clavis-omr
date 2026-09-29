"""Bounded W2/W3 component measurements: synthetic smoke, NOT SYN-Val or W4 evaluation."""

import argparse
import gzip
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from clavis.geometry import detect_staves, extract_strip, load_config, strip_to_processed
from training.data.resources import peak_rss_bytes
from training.degrade.ops import Labels, apply


def ground_truth(job: Path, width: int, height: int) -> list[np.ndarray]:
    """Resolve W2 staff-local labels through the unmodified SVG ancestor chain.

    This adapter deliberately rejects unfamiliar viewport/transform structures.
    It does not infer line geometry from pixels or from the detector's output.
    """
    root = ET.fromstring(gzip.decompress((job / "page-1.svg.gz").read_bytes()))
    parent = {child: node for node in root.iter() for child in node}
    ids = {node.get("id"): node for node in root.iter() if node.get("id")}
    document = json.loads((job / "page-1.labels.json").read_text())
    groups = {}
    view = list(map(float, root.attrib["viewBox"].split()))
    for segment in document["segments"]:
        node = ids[segment["staff_id"]]
        chain = [node]
        while node is not root:
            node = parent[node]
            chain.append(node)
        matrix = np.array(
            [
                [width / view[2], 0, -view[0] * width / view[2]],
                [0, height / view[3], -view[1] * height / view[3]],
                [0, 0, 1.0],
            ]
        )
        viewport = view[2:]
        for node in reversed(chain[:-1]):
            if node.tag.endswith("}svg"):
                box = list(map(float, node.attrib["viewBox"].split()))
                if any(k in node.attrib for k in ("width", "height", "x", "y")):
                    raise ValueError("Unsupported nested viewport")
                sx, sy = viewport[0] / box[2], viewport[1] / box[3]
                if not np.isclose(sx, sy):
                    raise ValueError("Nonuniform viewport")
                matrix = matrix @ np.array(
                    [[sx, 0, -box[0] * sx], [0, sy, -box[1] * sy], [0, 0, 1.0]]
                )
                viewport = box[2:]
            transform = node.get("transform", "")
            if transform:
                match = re.fullmatch(r"translate\(([-\d.]+)[, ]+([-\d.]+)\)", transform)
                if not match:
                    raise ValueError("Unsupported ancestor transform")
                dx, dy = map(float, match.groups())
                matrix = matrix @ np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1.0]])
        points = np.asarray(segment["polylines"], float)
        flat = points.reshape(-1, 2)
        mapped = (np.column_stack((flat, np.ones(len(flat)))) @ matrix.T)[:, :2].reshape(
            points.shape
        )
        groups.setdefault((segment["system_id"], segment["staff_number"]), []).append(mapped)
    staves = []
    for segments in groups.values():
        lines = np.concatenate(segments, axis=1)
        order = np.argsort(lines[0, :, 0], kind="stable")
        lines = lines[:, order]
        _, unique = np.unique(lines[0, :, 0], return_index=True)
        staves.append(lines[:, unique])
    return sorted(staves, key=lambda line: line[0, 0, 1])


def run(root: Path, rasters: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    started = time.perf_counter()
    records = []
    errors = []
    contacts = []
    provenance = []
    cfg = load_config()
    metadata = json.loads((rasters / "rasters.json").read_text())
    for record in metadata["records"]:
        name = record["name"]
        raw = (rasters / (name + ".png")).read_bytes()
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
        lines = ground_truth(root / name, image.shape[1], image.shape[0])
        provenance.append(
            {
                "sample": name,
                "raster_sha256": hashlib.sha256(raw).hexdigest(),
                "w2_input_sha256": hashlib.sha256(
                    (root / name / "input.musicxml").read_bytes()
                ).hexdigest(),
            }
        )
        pairs = np.concatenate([np.stack((line[:-1, 0], line[1:, 0]), axis=1) for line in lines])
        labels = Labels(
            np.empty((0, 2)),
            np.empty((0, 4)),
            tuple(line for staff in lines for line in staff),
            (),
            pairs,
        )
        for target in (16, 10, 8):
            if peak_rss_bytes() > 3_000_000_000:
                raise RuntimeError("OR-001 execution budget exhausted")
            page, moved, trace = apply(
                image,
                labels,
                np.random.default_rng(0),
                {
                    "op": "resize",
                    "target_interline": target,
                    "interpolation": "area",
                    "max_pixels": 30_000_000,
                },
            )
            truth = [
                np.stack(moved.polylines[k : k + 5]) for k in range(0, len(moved.polylines), 5)
            ]
            then = time.perf_counter()
            detection = detect_staves(page, cfg)
            detect_ms = (time.perf_counter() - then) * 1000
            used = set()
            rows = []
            canvas = Image.fromarray(page).convert("RGB")
            draw = ImageDraw.Draw(canvas)
            for staff in truth:
                for line in staff:
                    draw.line([tuple(x) for x in line], fill=(0, 160, 40), width=1)
            for i, candidate in enumerate(detection.candidates):
                xs = candidate.lines[0, :, 0]
                center = float(np.mean(xs[[0, -1]]))
                top = float(np.interp(center, xs, candidate.lines[0, :, 1]))
                choices = []
                for j, gt in enumerate(truth):
                    space = float(np.median(np.diff(gt[:, :, 1], axis=0)))
                    overlap = max(0, min(xs[-1], gt[0, -1, 0]) - max(xs[0], gt[0, 0, 0]))
                    union = max(xs[-1], gt[0, -1, 0]) - min(xs[0], gt[0, 0, 0])
                    distance = abs(top - np.interp(center, gt[0, :, 0], gt[0, :, 1])) / space
                    if j not in used and distance <= 0.5 and overlap / union >= 0.5:
                        choices.append((distance, j, space))
                for line in candidate.lines:
                    draw.line([tuple(x) for x in line], fill=(230, 0, 120), width=1)
                if not choices:
                    continue
                _, j, space = min(choices)
                used.add(j)
                gt = truth[j]
                staff = candidate.as_staff(f"pg0-sy{i}-st0", f"pg0-sy{i}")
                then = time.perf_counter()
                strip, mesh = extract_strip(page, staff, config=cfg)
                strip_ms = (time.perf_counter() - then) * 1000
                top_errors = [
                    float(
                        (
                            np.interp(center, xs, line[:, 1])
                            - np.interp(center, gline[:, 0], gline[:, 1])
                        )
                        / space
                    )
                    for line, gline in zip(candidate.lines, gt, strict=True)
                ]
                slope = (candidate.lines[0, -1, 1] - candidate.lines[0, 0, 1]) / (xs[-1] - xs[0])
                gt_slope = (gt[0, -1, 1] - gt[0, 0, 1]) / (gt[0, -1, 0] - gt[0, 0, 0])
                vector = {
                    "line_y_spaces": top_errors,
                    "interline_relative": candidate.interline_px / space - 1,
                    "slope_dy_dx": float(slope - gt_slope),
                    "left_spaces": float((xs[0] - gt[0, 0, 0]) / space),
                    "right_spaces": float((xs[-1] - gt[0, -1, 0]) / space),
                }
                errors.append({"sample": name, "target_interline": target, "staff": j, **vector})
                # Inverse mesh maps five canonical rows back to independently transformed GT.
                uu = np.linspace(0, strip.shape[1] - 1, 17)
                points = np.array([[[u, (6 + k) * 16] for u in uu] for k in range(5)])
                mapped = strip_to_processed(points, mesh, 16, 6)
                residual = np.stack(
                    [
                        (p[:, 1] - np.interp(p[:, 0], g[:, 0], g[:, 1])) / space
                        for p, g in zip(mapped, gt, strict=True)
                    ]
                )
                rows.append(
                    {
                        "interline_relative_error": abs(vector["interline_relative"]),
                        "dewarp_rms_spaces": float(np.sqrt(np.mean(residual**2))),
                        "strip_ms": strip_ms,
                    }
                )
                if i == 0:
                    im = Image.fromarray(strip[:, :, 0]).convert("RGB")
                    overlay = ImageDraw.Draw(im)
                    for y in (96, 112, 128, 144, 160):
                        overlay.line((0, y, im.width, y), fill=(230, 0, 120))
                    im.save(output / f"{name}-{target}-strip-overlay.png")
                    Image.fromarray(strip[:, :, 1]).save(output / f"{name}-{target}-removed.png")
            canvas.save(output / f"{name}-{target}-overlay.png")
            if target == 8:
                # Show the entire content bounding region rather than blank page margins.
                box = Image.fromarray(page).point(lambda v: 255 - v).getbbox()
                thumb = canvas.crop(box) if box else canvas
                thumb.thumbnail((700, 450))
                contacts.append((f"{name} / {target}px / {len(used)}/{len(truth)}", thumb))
            records.append(
                {
                    "sample": name,
                    "target_interline": target,
                    "gt_staves": len(truth),
                    "detected_staves": len(detection.candidates),
                    "matched_staves": len(used),
                    "diagnostics": list(detection.diagnostics),
                    "detect_ms": detect_ms,
                    "matches": rows,
                    "trace": trace,
                }
            )
    slices = []
    for target in (16, 10, 8):
        selected = [r for r in records if r["target_interline"] == target]
        matched = sum(r["matched_staves"] for r in selected)
        gt = sum(r["gt_staves"] for r in selected)
        detected = sum(r["detected_staves"] for r in selected)
        rows = [m for r in selected for m in r["matches"]]
        err = [r["interline_relative_error"] for r in rows]
        slices.append(
            {
                "interline": target,
                "pages": len(selected),
                "gt_staves": gt,
                "detected_staves": detected,
                "matched_staves": matched,
                "recall": matched / gt,
                "precision": matched / detected if detected else None,
                "interline_relative_error_median": float(np.median(err)) if err else None,
                "interline_relative_error_p95": float(np.percentile(err, 95)) if err else None,
                "strip_ms_p95": float(np.percentile([r["strip_ms"] for r in rows], 95))
                if rows
                else None,
                "dewarp_rms_spaces_p95": float(
                    np.percentile([r["dewarp_rms_spaces"] for r in rows], 95)
                )
                if rows
                else None,
            }
        )
    sheet = Image.new("RGB", (1400, len(contacts) // 2 * 490), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(contacts):
        x, y = i % 2 * 700, i // 2 * 490
        draw.text((x + 5, y + 5), label, fill="black")
        sheet.paste(im, (x, y + 30))
    sheet.save(output / "contact.png")
    result = {
        "scope": "synthetic smoke, NOT SYN-Val; no real/Dev/sealed data; no improvement claim",
        "match_definition": (
            "one-to-one nearest top-line centre <=0.5 staff-space "
            "and horizontal IoU>=0.5; diagnostic only"
        ),
        "slices": slices,
        "records": records,
        "provenance": provenance,
        "rasterizer": metadata["versions"],
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_rss_bytes(),
        "config_sha256": hashlib.sha256(
            Path("configs/geometry/constants.yaml").read_bytes()
        ).hexdigest(),
    }
    (output / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    jitter = {
        "source": "synthetic-v0",
        "status": "provisional",
        "scope": result["scope"],
        "sampling": (
            "Resample a complete empirical row within target_interline; preserve joint errors. "
            "Misses excluded from vectors and reported in slices. "
            "No Gaussian fit. Not a real-image distribution."
        ),
        "metrics": "docs/reports/W5/synthetic-v0.json",
        "slices": slices,
        "errors": errors,
    }
    (output / "jitter.yaml").write_text(json.dumps(jitter, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rasters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.rasters, args.output)
    print(
        json.dumps(
            {
                "slices": result["slices"],
                "wall_seconds": result["wall_seconds"],
                "peak_rss_bytes": result["peak_rss_bytes"],
            }
        )
    )
