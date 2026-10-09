"""72 self-authored rendered crops; SYN-Val 아님, no page/Dev claims.

No network: consume an explicit local artifact manifest, verifying every file.
Run with OR-005 --items 72. No OCR retraining, dictionary repair or rule fitting.
"""

import argparse
import hashlib
import io
import json
from dataclasses import asdict
from itertools import product
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

from clavis.text.chord import ChordGrammar
from clavis.text.ctc import CtcLimits, greedy_observation
from clavis.text.onnx_boundary import VerifiedCpuModel
from clavis.text.ppocr import ImageLimits, PpOcrProfile, cpu_factory, infer_image


def edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        next_row = [i]
        for j, right in enumerate(b, 1):
            next_row.append(min(row[j] + 1, next_row[-1] + 1, row[j - 1] + (left != right)))
        row = next_row
    return row[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter()
    manifest = json.loads(args.manifest.read_text())
    artifacts = {a["id"]: a for a in manifest["artifacts"]}

    def verified(identity):
        item = artifacts[identity]
        path = Path(item["local"])
        blob = path.read_bytes()
        if len(blob) != item["bytes"] or hashlib.sha256(blob).hexdigest() != item["sha256"]:
            raise ValueError("artifact verification failed")
        return blob

    root = Path(__file__).resolve().parents[3]
    values = {
        r["name"]: r["value"]
        for r in json.loads((root / "configs/text/constants.yaml").read_text())
    }
    image_limits = ImageLimits(
        *(values["text.ppocr." + n] for n in ("max_pixels", "max_tensor_pixels", "max_rec_width"))
    )
    ctc_limits = CtcLimits(
        *(values["text.ctc." + n] for n in ("max_frames", "max_classes", "max_cells"))
    )
    grammar = ChordGrammar(
        root / "configs/text/rules.yaml",
        max_chars=values["text.grammar.max_chars"],
        max_states=values["text.grammar.max_states"],
    )
    models = {}
    profiles = {}
    for key, name in (
        ("det", "PP-OCRv5_mobile_det_onnx"),
        ("latin", "latin_PP-OCRv5_mobile_rec_onnx"),
        ("korean", "korean_PP-OCRv5_mobile_rec_onnx"),
    ):
        metadata = yaml.safe_load(verified(name + "/inference.yml"))
        transforms = {
            k: v for row in metadata["PreProcess"]["transform_ops"] for k, v in row.items()
        }
        if key == "det":
            size = transforms["DetResizeForTest"]["resize_long"]
            norm = transforms["NormalizeImage"]
            profile = PpOcrProfile(
                "det",
                size,
                size,
                32,
                tuple(norm["mean"]),
                tuple(norm["std"]),
                (),
                "x",
                "fetch_name_0",
            )
        else:
            _, height, width = transforms["RecResizeImg"]["image_shape"]
            # PaddleX CTCLabelDecode: prepend blank, append space to export dictionary.
            alphabet = ("", *metadata["PostProcess"]["character_dict"], " ")
            profile = PpOcrProfile(
                "rec", height, width, 1, (0.5,) * 3, (0.5,) * 3, alphabet, "x", "fetch_name_0"
            )
        item = artifacts[name + "/inference.onnx"]
        models[key] = VerifiedCpuModel.load(
            Path(item["local"]),
            item["sha256"],
            max_bytes=values["text.onnx.max_model_bytes"],
            threads=1,
            factory=cpu_factory,
        )
        profiles[key] = profile

    load_seconds = perf_counter() - started
    rows = []
    crops = args.out.parent / "ppocr-crops"
    crops.mkdir(parents=True, exist_ok=True)
    texts = [
        ("chord", r + suffix)
        for r, suffix in product(("C", "F#"), ("M7", "min7", "ø", "7(b9)", "sus", "6/9", "5", "13"))
    ]
    texts += [("latin", "Blue river"), ("korean", "새로운 아침")]
    for family, font_px, (kind, printed) in product(
        ("NotoSansCJKkr", "NotoSerifCJKkr"), (12, 24), texts
    ):
        font_blob = verified(f"{family}/{family}-Regular.otf")
        font = ImageFont.truetype(io.BytesIO(font_blob), font_px)
        left, top, right, bottom = font.getbbox(printed)
        padding = 8  # Synthetic render margin, not an OCR threshold.
        image = Image.new("RGB", (right - left + 2 * padding, bottom - top + 2 * padding), "white")
        ImageDraw.Draw(image).text(
            (padding - left, padding - top), printed, fill="black", font=font
        )
        image.save(crops / f"{len(rows):03d}.png")
        bgr = np.asarray(image)[:, :, ::-1].copy()
        key = "korean" if kind == "korean" else "latin"
        outputs, repeats = [], []
        tick = perf_counter()
        for _ in range(3):
            result = infer_image(models[key], bgr, profiles[key], image_limits, enabled=True)
            observation = greedy_observation(
                result.probabilities.tolist(),
                profiles[key].alphabet,
                blank_index=0,
                limits=ctc_limits,
                preserve_export_alphabet=True,
                enabled=True,
            )
            outputs.append(observation.text)
            repeats.append(
                hashlib.sha256(
                    np.rint(result.probabilities * 10000).astype(np.int32).tobytes()
                ).hexdigest()
            )
        elapsed = perf_counter() - tick
        detected = infer_image(models["det"], bgr, profiles["det"], image_limits, enabled=True)
        parsed = grammar.parse(outputs[0]) if kind == "chord" else None
        expected = grammar.parse(printed) if kind == "chord" else None
        rows.append(
            {
                "family": family,
                "fontPx": font_px,
                "kind": kind,
                "printed": printed,
                "observed": outputs[0],
                "rawExact": outputs[0] == printed,
                "characterEdits": edit_distance(printed, outputs[0]),
                "characters": len(printed),
                "normalized": parsed.normalized if parsed else None,
                "normalizedExact": parsed is not None and parsed.normalized == expected.normalized
                if expected
                else None,
                "repeat3QuantizedEqual": len(set(repeats)) == 1,
                "repeat3TextEqual": len(set(outputs)) == 1,
                "recognizeThreeSeconds": elapsed,
                "detectorMapShape": list(detected.probabilities.shape),
                "detectorMaxBp": int(round(float(detected.probabilities.max()) * 10000)),
                "disabledAbstained": infer_image(
                    models[key], bgr, profiles[key], image_limits, enabled=False
                )
                is None,
            }
        )
    slices = {}
    for kind in ("chord", "latin", "korean"):
        selected = [r for r in rows if r["kind"] == kind]
        slices[kind] = {
            "count": len(selected),
            "rawExact": sum(r["rawExact"] for r in selected),
            "characterEdits": sum(r["characterEdits"] for r in selected),
            "characters": sum(r["characters"] for r in selected),
            "normalizedExact": sum(r["normalizedExact"] is True for r in selected)
            if kind == "chord"
            else None,
        }
    summary = {
        "scope": "synthetic rendered crop smoke; SYN-Val 아님; not a page OCR evaluation",
        "manifestSha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "items": len(rows),
        "loadSeconds": load_seconds,
        "totalSeconds": perf_counter() - started,
        "profiles": {
            k: {n: v for n, v in asdict(p).items() if n != "alphabet"} for k, p in profiles.items()
        },
        "slices": slices,
        "allRepeat3Equal": all(r["repeat3QuantizedEqual"] and r["repeat3TextEqual"] for r in rows),
        "allDisabledAbstained": all(r["disabledAbstained"] for r in rows),
        "threads": "OR-005 overrides ORT to 2; no actual 1-vs-4 claim",
        "detectorBoxesRecall": "NOT_RUN: map only",
        "grammarConstrainedCtc": "NOT_RUN: greedy observation plus grammar validation only",
        "rows": rows,
    }
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
