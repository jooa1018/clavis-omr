"""S2 visual vertical-stroke proposals; no musical barline or system decisions."""

from dataclasses import dataclass

import numpy as np

from .config import GeometryConfig, load_config
from .staff import Gray, ink_mask, validate_gray


@dataclass(frozen=True)
class VerticalStroke:
    u: float
    width_spaces: float
    coverage: float
    ambiguity: str = "BARLINE_OR_STEM"


def propose_barlines(
    original_strip: Gray,
    s_star: float,
    margin_above: float,
    *,
    config: GeometryConfig | None = None,
) -> tuple[VerticalStroke, ...]:
    """Propose thin strokes covering most of the observed staff height.

    Use the original channel. Full-height stems remain ambiguous; this API must
    not create LayoutBarline, measures or repeat styles without further evidence.
    """
    validate_gray(original_strip)
    if not np.isfinite(s_star) or s_star <= 0 or not np.isfinite(margin_above) or margin_above < 0:
        raise ValueError("Invalid canonical geometry")
    cfg = config or load_config()
    if "GEO-VERTICAL" not in cfg.enabled:
        return ()
    top = int(round(margin_above * s_star))
    bottom = int(round((margin_above + cfg["staff.lines"] - 1) * s_star))
    if top < 0 or bottom >= len(original_strip) or bottom <= top:
        raise ValueError("Complete staff height must be present")
    mask = ink_mask(original_strip)[top : bottom + 1]
    coverage = mask.mean(axis=0)
    supported = coverage >= cfg["barline.min_coverage"]
    edges = np.diff(np.r_[False, supported, False].astype(np.int8))
    proposals = []
    for left, right in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True):
        width = (right - left) / s_star
        if width <= cfg["barline.max_width"]:
            proposals.append(
                VerticalStroke(
                    float((left + right - 1) / 2), float(width), float(coverage[left:right].mean())
                )
            )
    return tuple(proposals)
