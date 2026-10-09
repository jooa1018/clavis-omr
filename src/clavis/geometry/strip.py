"""Shared deterministic grayscale/de-lined strip and CONTRACTS 2 mesh mapping."""

import cv2
import numpy as np
from numpy.typing import NDArray

from clavis.contracts.geometry import DewarpMesh, Staff

from .config import GeometryConfig, load_config
from .staff import Floats, Gray, ink_mask, validate_gray


def strip_to_processed(
    points: Floats, mesh: DewarpMesh, s_star: float, margin_above: float
) -> Floats:
    """Map (...,2) strip points; reject extrapolation beyond the sampled mesh."""
    points = np.asarray(points, dtype=np.float64)
    if (
        points.shape[-1:] != (2,)
        or not np.isfinite(points).all()
        or not np.isfinite(s_star)
        or not np.isfinite(margin_above)
        or s_star <= 0
        or margin_above < 0
    ):
        raise ValueError("Expected finite points and positive s_star")
    u, v = points[..., 0], points[..., 1]
    knots = np.arange(len(mesh.x)) * mesh.u_step
    if np.any(u < 0) or np.any(u > knots[-1]):
        raise ValueError("Point outside mesh support")
    x = np.interp(u, knots, mesh.x)
    y = (
        np.interp(u, knots, mesh.y_top)
        + (v - margin_above * s_star) * np.interp(u, knots, mesh.interline) / s_star
    )
    return np.stack((x, y), axis=-1)


def processed_to_strip(
    points: Floats, mesh: DewarpMesh, s_star: float, margin_above: float
) -> Floats:
    """Invert the same piecewise linear mesh, without a separate geometric fit."""
    points = np.asarray(points, dtype=np.float64)
    if (
        points.shape[-1:] != (2,)
        or not np.isfinite(points).all()
        or not np.isfinite(s_star)
        or not np.isfinite(margin_above)
        or s_star <= 0
        or margin_above < 0
    ):
        raise ValueError("Expected finite points and positive s_star")
    x, y = points[..., 0], points[..., 1]
    if np.any(x < mesh.x[0]) or np.any(x > mesh.x[-1]):
        raise ValueError("Point outside mesh support")
    u = np.interp(x, mesh.x, np.arange(len(mesh.x)) * mesh.u_step)
    top = np.interp(x, mesh.x, mesh.y_top)
    space = np.interp(x, mesh.x, mesh.interline)
    return np.stack((u, margin_above * s_star + (y - top) * s_star / space), axis=-1)


def remove_staff_lines(
    strip: Gray,
    s_star: float,
    margin_above: float,
    thickness_spaces: float,
    config: GeometryConfig | None = None,
) -> Gray:
    """Erase short vertical ink runs at staff rows; preserve crossing symbol runs."""
    validate_gray(strip)
    cfg = config or load_config()
    if (
        not all(np.isfinite(v) for v in (s_star, margin_above, thickness_spaces))
        or s_star <= 0
        or thickness_spaces <= 0
        or margin_above < 0
    ):
        raise ValueError("Invalid strip geometry")
    output = strip.copy()
    if "GEO-REMOVE" not in cfg.enabled:
        return output
    mask = ink_mask(strip)
    rows = np.arange(len(strip), dtype=np.int32)[:, None]
    previous_white = np.maximum.accumulate(np.where(mask, -1, rows), axis=0)
    next_white = np.minimum.accumulate(np.where(mask, len(strip), rows)[::-1], axis=0)[::-1]
    heights = np.where(mask, next_white - previous_white - 1, 0)
    radius = s_star * (thickness_spaces / 2 + cfg["remove.position_tolerance"])
    max_run = s_star * (thickness_spaces + cfg["remove.run_allowance"])
    for line in range(int(cfg["staff.lines"])):
        center = (margin_above + line) * s_star
        a, b = (
            max(0, int(np.floor(center - radius))),
            min(len(strip), int(np.ceil(center + radius)) + 1),
        )
        erase = (heights[a:b] > 0) & (heights[a:b] <= max_run)
        output[a:b][erase] = np.iinfo(np.uint8).max
    return output


def extract_strip(
    page: Gray,
    staff_geometry: Staff,
    s_star: float | None = None,
    margins: tuple[float, float] | None = None,
    *,
    config: GeometryConfig | None = None,
) -> tuple[NDArray[np.uint8], DewarpMesh]:
    """Return H×W×2 uint8 (original, staff-removed), with white out-of-page fill.

    Width uses the integrated local reciprocal interline, so perspective changes
    horizontal and vertical scale together. Mesh knots have uniform uStep; the
    final knot lands exactly at the right supported endpoint (no padded domain).
    """
    validate_gray(page)
    cfg = config or load_config()
    s = cfg["strip.s_star"] if s_star is None else s_star
    above, below = margins if margins is not None else (cfg["strip.above"], cfg["strip.below"])
    if not all(np.isfinite(v) for v in (s, above, below)) or s <= 0 or min(above, below) < 0:
        raise ValueError("Invalid strip scale or margins")
    if staff_geometry.ood or staff_geometry.line_count != int(cfg["staff.lines"]):
        raise ValueError("Only five-line pitched staves supported")
    polylines = [np.asarray(line, dtype=np.float64) for line in staff_geometry.lines]
    if any(np.any(np.diff(line[:, 0]) <= 0) for line in polylines):
        raise ValueError("Staff lines must be x-monotone")
    left = max(line[0, 0] for line in polylines)
    right = min(line[-1, 0] for line in polylines)
    if right <= left:
        raise ValueError("No shared staff domain")
    xs = np.unique(np.r_[left, right, np.concatenate([line[:, 0] for line in polylines])])
    xs = xs[(xs >= left) & (xs <= right)]
    ys = np.stack([np.interp(xs, line[:, 0], line[:, 1]) for line in polylines])
    gaps = np.diff(ys, axis=0)
    if np.any(gaps <= 0):
        raise ValueError("Staff lines cross")
    spaces = np.mean(gaps, axis=0)
    # Trapezoidal integration of s*/I(x), independent of raster resolution.
    us = np.r_[0, np.cumsum(np.diff(xs) * s * (1 / spaces[:-1] + 1 / spaces[1:]) / 2)]
    width = max(2, int(np.ceil(us[-1])) + 1)
    height = max(1, int(np.ceil((cfg["staff.lines"] - 1 + above + below) * s)))
    count = max(1, int(np.ceil((width - 1) / (cfg["strip.mesh_step"] * s))))
    step = (width - 1) / count
    knots = np.arange(count + 1) * step
    knot_x = np.interp(knots * us[-1] / (width - 1), us, xs)
    mesh = DewarpMesh(
        u_step=step,
        x=knot_x.tolist(),
        y_top=np.interp(knot_x, xs, ys[0]).tolist(),
        interline=np.interp(knot_x, xs, spaces).tolist(),
    )
    u = np.arange(width)
    xmap = np.interp(u, knots, mesh.x)
    ymap = (
        np.interp(u, knots, mesh.y_top)[None, :]
        + (np.arange(height)[:, None] - above * s)
        * np.interp(u, knots, mesh.interline)[None, :]
        / s
    )
    gray = cv2.remap(
        page,
        np.broadcast_to(xmap, (height, width)).astype(np.float32),
        ymap.astype(np.float32),
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(float(np.iinfo(np.uint8).max),),
    )
    gray_u8 = np.asarray(gray, dtype=np.uint8)
    removed = remove_staff_lines(
        gray_u8, s, above, staff_geometry.line_thickness_px / staff_geometry.interline_px, cfg
    )
    return np.stack((gray_u8, removed), axis=-1), mesh
