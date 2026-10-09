"""Training-only, offline loading of SHA-256-pinned PP-OCR smoke artifacts."""

import hashlib
import json
from pathlib import Path

import yaml

from clavis.text.chord import ChordGrammar
from clavis.text.ctc import CtcLimits
from clavis.text.onnx_boundary import VerifiedCpuModel
from clavis.text.ppocr import ImageLimits, PpOcrProfile, cpu_factory


def load_artifacts(manifest_path):
    manifest = json.loads(manifest_path.read_text())
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

    return models, profiles, grammar, image_limits, ctc_limits, values, verified
