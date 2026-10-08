"""Deterministic template evidence, without an unfitted detection threshold."""

from collections.abc import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

Gray = NDArray[np.uint8]
Scores = NDArray[np.int32]
SCORE_SCALE = 10000  # CONTRACTS 11: quantize comparison scores at 10^-4.


def template_responses(
    original: Gray, staff_removed: Gray, templates: Sequence[Gray], *, enabled: bool = True
) -> list[tuple[Scores, Scores]]:
    """SYM-TEMPLATE-001: retain separate NCC evidence from both strip channels.

    Responses are signed correlation scores, NOT calibrated probabilities.
    No channel wins by default, no peak is discarded, and no note is fabricated.
    Coordinates denote the top-left corner of a template window.
    """
    channels = (original, staff_removed)
    if any(image.dtype != np.uint8 or image.ndim != 2 for image in channels):
        raise ValueError("Expected two uint8 grayscale strip channels")
    if original.shape != staff_removed.shape or not original.size:
        raise ValueError("Strip channels must have the same nonempty shape")
    if not enabled:
        return []
    results: list[tuple[Scores, Scores]] = []
    for template in templates:
        if template.dtype != np.uint8 or template.ndim != 2 or not template.size:
            raise ValueError("Expected a nonempty uint8 grayscale template")
        if any(t > s for t, s in zip(template.shape, original.shape, strict=True)):
            raise ValueError("Template exceeds strip dimensions")
        if np.ptp(template) == 0:
            raise ValueError("Constant templates have undefined normalized correlation")
        scores = [
            np.rint(
                np.clip(cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED), -1, 1)
                * SCORE_SCALE
            ).astype(np.int32)
            for image in channels
        ]
        results.append((scores[0], scores[1]))
    return results
