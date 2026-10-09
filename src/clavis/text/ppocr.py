"""Offline PP-OCR ONNX image adapter; profiles come from verified export metadata.

PaddlePaddle PP-OCRv5 inference.yml: BGR, CHW, detector mean/std and
recognizer [-1, 1] scaling with right zero padding. No model acquisition here.
Detector output is a probability map, not a detected text box or staff link.
"""

from dataclasses import dataclass
from math import ceil
from typing import Literal, cast

import cv2
import numpy as np
import numpy.typing as npt

from clavis.text.ctc import BASIS_POINTS
from clavis.text.onnx_boundary import CpuSession, VerifiedCpuModel

FloatArray = npt.NDArray[np.float32]
ByteArray = npt.NDArray[np.uint8]


def cpu_factory(blob: bytes, threads: int) -> CpuSession:
    """Construct a CPU-only sequential ORT session from hash-verified bytes."""
    import onnxruntime as ort  # type: ignore[import-untyped]

    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return cast(
        CpuSession,
        ort.InferenceSession(blob, sess_options=options, providers=["CPUExecutionProvider"]),
    )


@dataclass(frozen=True)
class ImageLimits:
    max_pixels: int
    max_tensor_pixels: int
    max_rec_width: int

    def __post_init__(self) -> None:
        if any(
            type(v) is not int or v <= 0
            for v in (self.max_pixels, self.max_tensor_pixels, self.max_rec_width)
        ):
            raise ValueError("image limits must be positive integers")


@dataclass(frozen=True)
class PpOcrProfile:
    mode: Literal["det", "rec"]
    height: int
    width: int
    stride: int
    mean: tuple[float, float, float]
    std: tuple[float, float, float]
    alphabet: tuple[str, ...]
    input_name: str
    output_name: str

    def __post_init__(self) -> None:
        if self.mode not in ("det", "rec") or any(
            type(v) is not int or v <= 0 for v in (self.height, self.width, self.stride)
        ):
            raise ValueError("invalid PP-OCR image profile")
        if (
            len(self.mean) != 3
            or len(self.std) != 3
            or not all(np.isfinite(v) for v in (*self.mean, *self.std))
            or min(self.std) <= 0
        ):
            raise ValueError("invalid channel normalization")
        if not self.input_name or not self.output_name:
            raise ValueError("explicit model IO names required")
        if self.mode == "rec" and (
            not self.alphabet
            or self.alphabet[0] != ""
            or any(not token for token in self.alphabet[1:])
        ):
            raise ValueError("recognizer alphabet must have its only blank at index zero")


@dataclass(frozen=True)
class PpOcrOutput:
    """Raw probabilities with explicit image/tensor dimensions, never calibrated."""

    probabilities: FloatArray
    source_hw: tuple[int, int]
    tensor_hw: tuple[int, int]


def image_tensor(image: ByteArray, profile: PpOcrProfile, limits: ImageLimits) -> FloatArray:
    """Accept caller-decoded BGR uint8 pixels; resize without silently clipping."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("expected BGR uint8 HWC image")
    source_h, source_w = image.shape[:2]
    if min(source_h, source_w) <= 0 or source_h * source_w > limits.max_pixels:
        raise ValueError("source image exceeds pixel budget or is empty")
    if profile.mode == "rec":
        height = profile.height
        resized_width = ceil(source_w * height / source_h)
        width = max(profile.width, resized_width)
        if width > limits.max_rec_width:
            raise ValueError("recognizer width exceeds budget; split externally with evidence")
    else:
        scale = profile.width / max(source_h, source_w)
        height = max(profile.stride, ceil(source_h * scale / profile.stride) * profile.stride)
        width = max(profile.stride, ceil(source_w * scale / profile.stride) * profile.stride)
        resized_width = width
    if height * width > limits.max_tensor_pixels:
        raise ValueError("preprocessed image exceeds tensor budget")
    resized = cv2.resize(image, (resized_width, height), interpolation=cv2.INTER_LINEAR)
    # 255 is the uint8 unit conversion, not a fitted image threshold.
    normalized = (
        resized.astype(np.float32) / np.iinfo(np.uint8).max
        - np.asarray(profile.mean, dtype=np.float32)
    ) / np.asarray(profile.std, dtype=np.float32)
    output = np.zeros((1, 3, height, width), dtype=np.float32)
    output[0, :, :, :resized_width] = normalized.transpose(2, 0, 1)
    return output


def infer_image(
    model: VerifiedCpuModel,
    image: ByteArray,
    profile: PpOcrProfile,
    limits: ImageLimits,
    *,
    enabled: bool,
) -> PpOcrOutput | None:
    """Forward one bounded image, preserving a full CTC tensor or detector map."""
    if not enabled:
        return None
    tensor = image_tensor(image, profile, limits)
    result = np.asarray(model.run(profile.output_name, {profile.input_name: tensor}))
    if profile.mode == "rec":
        if (
            result.ndim != 3
            or result.shape[0] != 1
            or result.shape[2] != len(profile.alphabet)
            or result.shape[1] <= 0
            or result.shape[1] > tensor.shape[3]
        ):
            raise ValueError("recognizer shape does not match verified dictionary or tensor")
        probabilities = result[0]
    else:
        if result.ndim != 4 or result.shape[:2] != (1, 1) or result.shape[2:] != tensor.shape[2:]:
            raise ValueError("detector output is not a full-resolution single map")
        probabilities = result[0, 0]
    # CONTRACTS 11 requires quantization before decisions. CPU sigmoid/softmax
    # kernels can overshoot endpoints by a floating-point rounding unit.
    quantized = np.rint(probabilities * BASIS_POINTS)
    if (
        not np.all(np.isfinite(probabilities))
        or np.any(quantized < 0)
        or np.any(quantized > BASIS_POINTS)
    ):
        raise ValueError("model did not return finite probabilities")
    return PpOcrOutput(
        np.asarray(np.clip(probabilities, 0, 1), dtype=np.float32),
        (image.shape[0], image.shape[1]),
        (tensor.shape[2], tensor.shape[3]),
    )
