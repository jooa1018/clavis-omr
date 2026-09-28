"""Pixel-center homographies, with explicit labels and replayable parameters."""

from dataclasses import dataclass, replace
from io import BytesIO
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

Array = NDArray[Any]
Params = dict[str, Any]


@dataclass(frozen=True)
class Labels:
    """Private training container; coordinates use integer pixel centers.

    Interline pairs are corresponding points on adjacent staff lines (N, 2, 2).
    Tangents at each first point retain perpendicular spacing under perspective.
    Initially omitted tangents mean lines perpendicular to the supplied pairs.
    A truncated sample must be excluded from losses requiring complete content.
    """

    points: Array
    boxes: Array
    polylines: tuple[Array, ...]
    masks: tuple[Array, ...]
    interline_pairs: Array
    truncated: bool = False
    interline_tangents: Array | None = None

    @property
    def tangents(self) -> Array:
        if self.interline_tangents is not None:
            return self.interline_tangents
        delta = self.interline_pairs[:, 1] - self.interline_pairs[:, 0]
        return np.column_stack((-delta[:, 1], delta[:, 0]))

    @property
    def interlines(self) -> Array:
        delta = self.interline_pairs[:, 1] - self.interline_pairs[:, 0]
        tangent = self.tangents
        cross = delta[:, 0] * tangent[:, 1] - delta[:, 1] * tangent[:, 0]
        return np.asarray(np.abs(cross) / np.linalg.norm(tangent, axis=1))


def project(points: Array, matrix: Array) -> Array:
    """Apply homogeneous coordinates in float64; reject points at the horizon."""
    points = np.asarray(points, dtype=np.float64)
    if points.shape[-1:] != (2,) or not np.isfinite(points).all():
        raise ValueError("Coordinates must be finite (..., 2) arrays")
    flat = points.reshape(-1, 2)
    mapped = np.column_stack((flat, np.ones(len(flat)))) @ matrix.T
    if np.any(mapped[:, 2] == 0):
        raise ValueError("Projective horizon intersects labels")
    result = mapped[:, :2] / mapped[:, 2:]
    if not np.isfinite(result).all():
        raise ValueError("Non-finite projected labels")
    return np.asarray(result.reshape(points.shape))


def validate(image: Array, labels: Labels, max_pixels: int) -> None:
    """Reject unsupported images and inconsistent label geometry before allocation."""
    if image.dtype != np.uint8 or image.ndim not in (2, 3):
        raise ValueError("Expected uint8 grayscale or RGB")
    if image.ndim == 3 and image.shape[2] != 3:
        raise ValueError("Expected three RGB channels")
    if not 0 < image.shape[0] * image.shape[1] <= max_pixels:
        raise ValueError("Image exceeds configured pixel budget or is empty")
    if labels.points.ndim != 2 or labels.boxes.ndim != 2 or labels.boxes.shape[1] != 4:
        raise ValueError("Expected points (N,2) and boxes (N,4)")
    if not np.isfinite(labels.boxes).all() or np.any(labels.boxes[:, 2:] < labels.boxes[:, :2]):
        raise ValueError("Boxes must be finite ordered xyxy")
    if labels.interline_pairs.shape[1:] != (2, 2) or not len(labels.interline_pairs):
        raise ValueError("At least one interline pair is required")
    for points in (labels.points, labels.interline_pairs, *labels.polylines):
        project(points, np.eye(3))
    if (
        labels.tangents.shape != (len(labels.interline_pairs), 2)
        or not np.isfinite(labels.tangents).all()
        or np.any(np.linalg.norm(labels.tangents, axis=1) == 0)
    ):
        raise ValueError("Expected finite nonzero interline tangents")
    if np.any(labels.interlines <= 0):
        raise ValueError("Interline must be positive")
    for mask in labels.masks:
        if mask.shape != image.shape[:2] or mask.dtype not in (np.uint8, np.uint16):
            raise ValueError("Masks must match image shape and use uint8 or uint16 IDs")


def warp(
    image: Array, labels: Labels, matrix: Array, size: tuple[int, int]
) -> tuple[Array, Labels]:
    """Use the same forward map for image and labels; mask background ID is zero."""
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("Expected finite 3x3 homography")
    if np.linalg.matrix_rank(matrix) != 3:
        raise ValueError("Singular homography")
    h, w = image.shape[:2]
    corners = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    depths = np.column_stack((corners, np.ones(4))) @ matrix[2]
    if not (np.all(depths > 0) or np.all(depths < 0)):
        raise ValueError("Projective horizon crosses the image")
    boxes = labels.boxes
    box_points = boxes[:, [0, 1, 2, 1, 2, 3, 0, 3]].reshape(-1, 4, 2)
    moved = project(box_points, matrix)
    moved_boxes = np.concatenate((moved.min(axis=1), moved.max(axis=1)), axis=1)
    points = project(labels.points, matrix)
    lines = tuple(project(line, matrix) for line in labels.polylines)
    pairs = project(labels.interline_pairs, matrix)
    tangents = project(labels.interline_pairs[:, 0] + labels.tangents, matrix) - pairs[:, 0]
    geometries = (points, moved, pairs, *lines)
    outside = any(np.any((p < 0) | (p > np.array(size) - 1)) for p in geometries)
    for mask in labels.masks:
        rows, cols = np.flatnonzero(np.any(mask, axis=1)), np.flatnonzero(np.any(mask, axis=0))
        if len(rows):
            extent = project(
                np.array(
                    [
                        [cols[0], rows[0]],
                        [cols[-1], rows[0]],
                        [cols[-1], rows[-1]],
                        [cols[0], rows[-1]],
                    ]
                ),
                matrix,
            )
            outside = outside or bool(np.any((extent < 0) | (extent > np.array(size) - 1)))
    masks = tuple(
        cv2.warpPerspective(m, matrix, size, flags=cv2.INTER_NEAREST) for m in labels.masks
    )
    result = cv2.warpPerspective(image, matrix, size, borderValue=(255, 255, 255))
    return result, Labels(
        points, moved_boxes, lines, masks, pairs, labels.truncated or outside, tangents
    )


def apply(
    image: Array, labels: Labels, rng: np.random.Generator, params: Params
) -> tuple[Array, Labels, Params]:
    """Apply one fixed operation; rng belongs to the caller and is never global."""
    del rng  # Sampling is centralized in run(); replay consumes no random state.
    validate(image, labels, int(params["max_pixels"]))
    name = params["op"]
    h, w = image.shape[:2]
    matrix = np.eye(3, dtype=np.float64)
    size = (w, h)
    if name == "rotation":
        angle = float(params["degrees"])
        if not np.isfinite(angle):
            raise ValueError("Rotation must be finite")
        matrix[:2] = cv2.getRotationMatrix2D(((w - 1) / 2, (h - 1) / 2), angle, 1)
    elif name == "perspective":
        matrix = np.asarray(params["matrix"], dtype=np.float64)
    elif name == "resize":
        target = float(params["target_interline"])
        source = float(np.median(labels.interlines))
        if not np.isfinite(target) or not 0 < target <= source:
            raise ValueError("Target interline must be finite, positive and no larger than source")
        scale = target / source
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        sx, sy = size[0] / w, size[1] / h
        # OpenCV resize maps pixel centers by (x + 0.5) * scale - 0.5.
        matrix = np.array([[sx, 0, (sx - 1) / 2], [0, sy, (sy - 1) / 2], [0, 0, 1]])
    elif name == "jpeg":
        quality, repeats, subsampling = (
            int(params[k]) for k in ("quality", "repeats", "subsampling")
        )
        if not 1 <= quality <= 95 or not 1 <= repeats <= 3 or subsampling not in (0, 1, 2):
            raise ValueError("Invalid JPEG parameters")
        result = image.copy()
        for _ in range(repeats):
            buffer = BytesIO()
            Image.fromarray(result).save(
                buffer, format="JPEG", quality=quality, subsampling=subsampling
            )
            buffer.seek(0)
            with Image.open(buffer) as decoded:
                result = np.array(decoded)
        return result, labels, {**params, "matrix": matrix.tolist(), "size": list(size)}
    else:
        raise ValueError(f"Unknown operation: {name}")
    result, transformed = warp(image, labels, matrix, size)
    if name == "resize":
        interpolation = {
            "area": cv2.INTER_AREA,
            "bilinear": cv2.INTER_LINEAR,
            "bicubic": cv2.INTER_CUBIC,
            "nearest": cv2.INTER_NEAREST_EXACT,
        }
        result = cv2.resize(image, size, interpolation=interpolation[params["interpolation"]])
        transformed = replace(
            transformed,
            masks=tuple(
                cv2.resize(m, size, interpolation=cv2.INTER_NEAREST_EXACT) for m in labels.masks
            ),
        )
    return (
        result,
        transformed,
        {
            **params,
            "matrix": matrix.tolist(),
            "size": list(size),
            "actual_interlines": transformed.interlines.tolist(),
        },
    )


def run(
    image: Array, labels: Labels, rng: np.random.Generator, config: Params
) -> tuple[Array, Labels, Params]:
    """Sample scalar uniform/choice distributions and record every resolved parameter."""
    records = []
    total = np.eye(3)
    for spec in config["operations"]:
        params = {"max_pixels": config["max_pixels"]}
        for key, value in spec.items():
            if isinstance(value, dict):
                if set(value) == {"uniform"}:
                    value = float(rng.uniform(*value["uniform"]))
                elif set(value) == {"choice"}:
                    options = value["choice"]
                    value = options[int(rng.integers(len(options)))]
                else:
                    raise ValueError("Unknown parameter distribution")
            params[key] = value
        image, labels, record = apply(image, labels, rng, params)
        total = np.asarray(record["matrix"]) @ total
        records.append(record)
    return (
        image,
        labels,
        {
            "operations": records,
            "matrix": total.tolist(),
            "actual_interlines": labels.interlines.tolist(),
            "truncated": bool(labels.truncated),
        },
    )
