"""Analytic vertical paper wave with inverse raster map and bounded chord error.

This approximates smooth paper curl, not a calibrated cylindrical camera model.
"""

from dataclasses import replace

import cv2
import numpy as np

from training.degrade.ops import Array, Labels, Params
from training.degrade.photometric import bounded


def transform(points: Array, amplitude: float, omega: float, phase: float) -> Array:
    """Forward y'=y+A*sin(omega*x+phase), x'=x."""
    result = np.array(points, dtype=np.float64, copy=True)
    result[..., 1] += amplitude * np.sin(omega * result[..., 0] + phase)
    return result


def envelope(boxes: Array, amplitude: float, omega: float, phase: float) -> Array:
    """Include analytic sine extrema on horizontal edges, not just four corners."""
    left, right = omega * boxes[:, 0] + phase, omega * boxes[:, 2] + phase
    start = np.ceil((left - np.pi / 2) / np.pi)
    candidates = [np.sin(left), np.sin(right)]
    for offset in (0, 1):
        critical = np.pi / 2 + (start + offset) * np.pi
        candidates.append(np.where(critical <= right, np.sin(critical), np.sin(left)))
    shifts = amplitude * np.stack(candidates)
    result = boxes.copy()
    result[:, 1] += shifts.min(axis=0)
    result[:, 3] += shifts.max(axis=0)
    return result


def densify(line: Array, amplitude: float, omega: float, tolerance: float, limit: int) -> Array:
    """Linear interpolation error <= max|y''| * dx^2 / 8 for each segment."""
    if len(line) < 2:
        return line.copy()
    counts = np.maximum(
        1,
        np.ceil(np.abs(np.diff(line[:, 0])) * np.sqrt(abs(amplitude) * omega**2 / (8 * tolerance))),
    ).astype(int)
    if int(counts.sum()) + 1 > limit:
        raise ValueError("Curve polyline exceeds configured point budget")
    segments = [
        np.linspace(a, b, count + 1)[:-1]
        for a, b, count in zip(line[:-1], line[1:], counts, strict=True)
    ]
    return np.concatenate([*segments, line[-1:]])


def warp_wave(image: Array, labels: Labels, params: Params) -> tuple[Array, Labels, Params]:
    """Deform every label using the same analytic forward map as the inverse raster."""
    h, w = image.shape[:2]
    amplitude = bounded(
        params, "amplitude_spaces", -params["max_wave_spaces"], params["max_wave_spaces"]
    ) * float(np.median(labels.interlines))
    phase = bounded(params, "phase_radians", -np.pi, np.pi)
    tolerance = bounded(params, "chord_error_px", np.finfo(float).eps, params["max_chord_error_px"])
    omega = 2 * np.pi / max(w - 1, 1)
    points = transform(labels.points, amplitude, omega, phase)
    boxes = envelope(labels.boxes, amplitude, omega, phase)
    lines = tuple(
        transform(
            densify(line, amplitude, omega, tolerance, int(params["max_curve_points"])),
            amplitude,
            omega,
            phase,
        )
        for line in labels.polylines
    )
    pairs = transform(labels.interline_pairs, amplitude, omega, phase)
    tangents = labels.tangents.copy()
    tangents[:, 1] += (
        amplitude * omega * np.cos(omega * labels.interline_pairs[:, 0, 0] + phase) * tangents[:, 0]
    )
    extents = [boxes.reshape(-1, 2), points, pairs, *lines]
    for mask in labels.masks:
        rows, cols = np.flatnonzero(np.any(mask, axis=1)), np.flatnonzero(np.any(mask, axis=0))
        if len(rows):
            extents.append(
                envelope(
                    np.array([[cols[0], rows[0], cols[-1], rows[-1]]], float),
                    amplitude,
                    omega,
                    phase,
                ).reshape(-1, 2)
            )
    outside = any(np.any((extent < 0) | (extent > [w - 1, h - 1])) for extent in extents)
    x = np.arange(w, dtype=np.float32)
    map_x = np.broadcast_to(x, (h, w)).copy()
    map_y = np.arange(h, dtype=np.float32)[:, None] - amplitude * np.sin(omega * x + phase)[None, :]
    map_y = map_y.astype(np.float32)
    result = cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    masks = tuple(cv2.remap(mask, map_x, map_y, cv2.INTER_NEAREST) for mask in labels.masks)
    moved = replace(
        labels,
        points=points,
        boxes=boxes,
        polylines=lines,
        masks=masks,
        interline_pairs=pairs,
        interline_tangents=tangents,
        truncated=bool(labels.truncated or outside),
    )
    return (
        result,
        moved,
        {
            **params,
            "matrix": None,
            "map": {
                "kind": "vertical_sine",
                "amplitude_px": amplitude,
                "omega": omega,
                "phase": phase,
            },
            "size": [w, h],
            "actual_interlines": moved.interlines.tolist(),
        },
    )
