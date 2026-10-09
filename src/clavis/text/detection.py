"""Bounded DB-map components and conservative rectangular expansion.

Expansion distance A*r/P follows DB (https://arxiv.org/abs/1911.08947).
We expand the minimum-area rectangle, not an arbitrary polygon offset; this
explicit approximation avoids importing a polygon clipping implementation.
"""

from dataclasses import dataclass
from math import isfinite

import cv2
import numpy as np

from clavis.contracts.common import Box, Polygon

from .ctc import BASIS_POINTS
from .ppocr import PpOcrOutput


@dataclass(frozen=True)
class DbLimits:
    threshold_bp: int
    box_threshold_bp: int
    unclip_ratio: float
    max_components: int
    max_pixels: int

    def __post_init__(self) -> None:
        for n in (self.threshold_bp, self.box_threshold_bp):
            if type(n) is not int or not 0 <= n <= BASIS_POINTS:
                raise ValueError("DB thresholds must be basis points")
        if not isfinite(self.unclip_ratio) or self.unclip_ratio < 0:
            raise ValueError("invalid DB expansion ratio")
        if any(type(n) is not int or n <= 0 for n in (self.max_components, self.max_pixels)):
            raise ValueError("invalid DB resource limit")


@dataclass(frozen=True)
class TextRegion:
    box: Box
    polygon: Polygon
    score_bp: int


def detection_regions(
    output: PpOcrOutput,
    *,
    limits: DbLimits,
    enabled: bool,
    offset: tuple[float, float] = (0.0, 0.0),
) -> tuple[TextRegion, ...]:
    if not enabled:
        return ()
    raw = output.probabilities
    if (
        raw.ndim != 2
        or not raw.size
        or raw.size > limits.max_pixels
        or not np.isfinite(raw).all()
        or (raw < 0).any()
        or (raw > 1).any()
        or any(type(n) is not int or n <= 0 for n in output.source_hw)
        or not all(isfinite(n) for n in offset)
    ):
        raise ValueError("invalid bounded DB map")
    scores = np.rint(raw * BASIS_POINTS).astype(np.int32)
    binary = (scores > limits.threshold_bp).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) > limits.max_components:
        raise ValueError("DB component budget exceeded")
    source_h, source_w = output.source_hw
    scale = np.array([source_w / scores.shape[1], source_h / scores.shape[0]])
    result: list[TextRegion] = []
    for contour in contours:
        area, perimeter = cv2.contourArea(contour), cv2.arcLength(contour, True)
        if area <= 0 or perimeter <= 0:
            continue
        mask = np.zeros(scores.shape, dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, (1,), cv2.FILLED)
        score = round(float(scores[mask.astype(bool)].mean()))
        if score < limits.box_threshold_bp:
            continue
        center, (width, height), angle = cv2.minAreaRect(contour)
        distance = area * limits.unclip_ratio / perimeter
        vertices = cv2.boxPoints((center, (width + 2 * distance, height + 2 * distance), angle))
        vertices = np.clip(vertices * scale, (0, 0), (source_w, source_h))
        vertices += np.array(offset)
        points = [(round(float(x), 3), round(float(y), 3)) for x, y in vertices]
        start = min(range(len(points)), key=lambda i: points[i])
        points = points[start:] + points[:start]
        left, top = min(x for x, _ in points), min(y for _, y in points)
        right, bottom = max(x for x, _ in points), max(y for _, y in points)
        if right > left and bottom > top:
            result.append(
                TextRegion(
                    (left, top, round(right - left, 3), round(bottom - top, 3)), points, score
                )
            )
    return tuple(sorted(result, key=lambda r: (r.box[1], r.box[0], r.box, r.polygon)))
