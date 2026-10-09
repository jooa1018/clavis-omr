import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from clavis.text.onnx_boundary import VerifiedCpuModel
from clavis.text.ppocr import ImageLimits, PpOcrProfile, cpu_factory, image_tensor, infer_image

ROOT = Path(__file__).resolve().parents[2]
VALUES = {
    r["name"].removeprefix("text.ppocr."): r["value"]
    for r in json.loads((ROOT / "configs/text/constants.yaml").read_text())
    if r["name"].startswith("text.ppocr.")
}
LIMITS = ImageLimits(**VALUES)
REC = PpOcrProfile("rec", 48, 320, 1, (0.5,) * 3, (0.5,) * 3, ("", "a", " "), "x", "fetch_name_0")
DET = PpOcrProfile(
    "det", 960, 960, 32, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225), (), "x", "fetch_name_0"
)


class Session:
    def __init__(self, output):
        self.output = output
        self.feed = None

    def get_providers(self):
        return ["CPUExecutionProvider"]

    def run(self, names, feed):
        self.feed = feed
        return [self.output]


def test_recognizer_preserves_aspect_and_bgr_order_and_padding():
    image = np.zeros((24, 24, 3), dtype=np.uint8)
    image[:, :, 0] = 255
    tensor = image_tensor(image, REC, LIMITS)
    assert tensor.shape == (1, 3, 48, 320)
    assert tensor.dtype == np.float32
    assert np.all(tensor[0, 0, :, :48] == 1)
    assert np.all(tensor[0, 1:, :, :48] == -1)
    assert np.all(tensor[:, :, :, 48:] == 0)
    wide = image_tensor(np.zeros((24, 200, 3), dtype=np.uint8), REC, LIMITS)
    assert wide.shape == (1, 3, 48, 400)


def test_detector_stride_and_normalization():
    image = np.full((50, 100, 3), 255, dtype=np.uint8)
    tensor = image_tensor(image, DET, LIMITS)
    assert tensor.shape == (1, 3, 480, 960)
    np.testing.assert_allclose(tensor[0, :, 0, 0], (1 - np.array(DET.mean)) / DET.std, rtol=1e-6)
    thin = image_tensor(np.zeros((1, 100, 3), dtype=np.uint8), DET, LIMITS)
    assert thin.shape[2] == 32


@pytest.mark.parametrize(
    "image",
    [
        np.zeros((0, 1, 3), np.uint8),
        np.zeros((4, 4), np.uint8),
        np.zeros((4, 4, 4), np.uint8),
        np.zeros((4, 4, 3), np.float32),
    ],
)
def test_reject_image_formats(image):
    with pytest.raises(ValueError):
        image_tensor(image, REC, LIMITS)


def test_resource_limits():
    image = np.zeros((24, 24, 3), dtype=np.uint8)
    for limits in (
        replace(LIMITS, max_pixels=1),
        replace(LIMITS, max_rec_width=1),
        replace(LIMITS, max_tensor_pixels=1),
    ):
        with pytest.raises(ValueError):
            image_tensor(image, REC, limits)
    for field in ("max_pixels", "max_rec_width", "max_tensor_pixels"):
        with pytest.raises(ValueError):
            replace(LIMITS, **{field: 0})


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "bad"},
        {"height": 0},
        {"mean": (0, 0)},
        {"std": (1, 0, 1)},
        {"std": (1, float("nan"), 1)},
        {"input_name": ""},
        {"output_name": ""},
        {"alphabet": ()},
        {"alphabet": ("a",)},
        {"alphabet": ("", "a", "")},
    ],
)
def test_profile_rejections(changes):
    with pytest.raises(ValueError):
        replace(REC, **changes)


def test_raw_outputs_and_disabled():
    image = np.zeros((24, 24, 3), dtype=np.uint8)
    session = Session(np.array([[[0, 1, 0]]], np.float32))
    model = VerifiedCpuModel(session, "mock")
    result = infer_image(model, image, REC, LIMITS, enabled=True)
    assert result.source_hw == (24, 24) and result.tensor_hw == (48, 320)
    assert result.probabilities.tolist() == [[0, 1, 0]]
    assert list(session.feed) == ["x"]
    assert infer_image(model, image, REC, LIMITS, enabled=False) is None
    session.output = np.zeros((1, 1, 960, 960), np.float32)
    assert infer_image(model, image, DET, LIMITS, enabled=True).probabilities.shape == (960, 960)


@pytest.mark.parametrize(
    "output",
    [
        np.zeros((1, 3)),
        np.zeros((2, 1, 3)),
        np.zeros((1, 1, 4)),
        np.zeros((1, 0, 3)),
        np.zeros((1, 321, 3)),
        np.array([[[0, float("nan"), 0]]]),
        np.array([[[0, 2, 0]]]),
        np.array([[[-1, 1, 0]]]),
    ],
)
def test_reject_invalid_recognizer_output(output):
    with pytest.raises(ValueError):
        infer_image(
            VerifiedCpuModel(Session(output), "mock"),
            np.zeros((24, 24, 3), np.uint8),
            REC,
            LIMITS,
            enabled=True,
        )


def test_reject_detector_shape():
    with pytest.raises(ValueError):
        infer_image(
            VerifiedCpuModel(Session(np.zeros((1, 1, 32, 32))), "mock"),
            np.zeros((24, 24, 3), np.uint8),
            DET,
            LIMITS,
            enabled=True,
        )


def test_model_roundoff_obeys_contract_quantization():
    session = Session(np.array([[[-1e-7, 1 + 1e-7, 0]]], np.float32))
    result = infer_image(
        VerifiedCpuModel(session, "mock"),
        np.zeros((24, 24, 3), np.uint8),
        REC,
        LIMITS,
        enabled=True,
    )
    assert result.probabilities.tolist() == [[0, 1, 0]]
    session.output = np.array([[[-0.001, 1.001, 0]]], np.float32)
    with pytest.raises(ValueError):
        infer_image(
            VerifiedCpuModel(session, "mock"),
            np.zeros((24, 24, 3), np.uint8),
            REC,
            LIMITS,
            enabled=True,
        )


def test_export_dictionary_preserves_distinct_class_ids_and_raw_spelling():
    from clavis.text.ctc import CtcLimits, greedy_observation

    result = greedy_observation(
        [[0, 1, 0], [0, 0, 1]],
        ("", "e\u0301", "e\u0301"),
        blank_index=0,
        limits=CtcLimits(2, 3, 6),
        enabled=True,
        preserve_export_alphabet=True,
    )
    assert result.text == "éé"
    assert result.tokens == ("e\u0301", "e\u0301")
    assert result.token_frames == (0, 1)


def test_factory_requests_cpu_sequential_and_explicit_threads(monkeypatch):
    captured = {}

    def session(blob, **kwargs):
        captured.update(blob=blob, **kwargs)
        return Session([])

    import sys

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(
            SessionOptions=SimpleNamespace,
            ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
            InferenceSession=session,
        ),
    )
    cpu_factory(b"verified", 4)
    assert captured["blob"] == b"verified"
    assert captured["providers"] == ["CPUExecutionProvider"]
    assert vars(captured["sess_options"]) == {
        "intra_op_num_threads": 4,
        "inter_op_num_threads": 1,
        "execution_mode": "sequential",
    }
