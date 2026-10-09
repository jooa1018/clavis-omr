"""Image-supported horizontal lyric segments; no lyric lexicon or CTC boxes."""

from math import isfinite

import cv2
import numpy as np
from numpy.typing import NDArray

from clavis.contracts.common import Box


def lyric_segments(
    image: NDArray[np.uint8],
    *,
    staff_space: float,
    gap_spaces: float,
    max_pixels: int,
    max_segments: int,
    enabled: bool,
    offset: tuple[float, float] = (0.0, 0.0),
) -> tuple[Box, ...]:
    """Otsu dark-ink projection, joining small internal gaps in staff units.

    These are candidate ink segments, not asserted syllables. Independently OCR
    each segment; only callers with observed text may construct Syllable values.
    Stems, extenders and hyphens are not relabelled as syllables here.
    """
    if not enabled:
        return ()
    if (
        image.dtype != np.uint8
        or image.ndim != 3
        or image.shape[2] != 3
        or not image.size
        or image.shape[0] * image.shape[1] > max_pixels
        or not isfinite(staff_space)
        or staff_space <= 0
        or not isfinite(gap_spaces)
        or gap_spaces < 0
        or any(type(n) is not int or n <= 0 for n in (max_pixels, max_segments))
        or not all(isfinite(n) for n in offset)
    ):
        raise ValueError("invalid lyric segmentation input")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if gray.min() == gray.max():
        return ()
    _, ink = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    columns = np.flatnonzero(ink.any(axis=0))
    if not len(columns):
        return ()
    groups = np.split(columns, np.flatnonzero(np.diff(columns) - 1 > gap_spaces * staff_space) + 1)
    if len(groups) > max_segments:
        raise ValueError("lyric segment budget exceeded")
    boxes: list[Box] = []
    for group in groups:
        left, right = int(group[0]), int(group[-1]) + 1
        ys = np.flatnonzero(ink[:, left:right].any(axis=1))
        top, bottom = int(ys[0]), int(ys[-1]) + 1
        boxes.append((left + offset[0], top + offset[1], float(right - left), float(bottom - top)))
    return tuple(boxes)
