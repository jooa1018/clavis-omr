"""Run-length scale hypotheses and bandwise grayscale staff projections."""

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from clavis.contracts.geometry import InterlineSample, Staff

from .config import GeometryConfig, load_config

Gray = NDArray[np.uint8]
Floats = NDArray[np.float64]


def validate_gray(page: Gray) -> None:
    """S0 owns decoding; geometry accepts nonempty uint8 luminance only."""
    if page.ndim != 2 or page.dtype != np.uint8 or not page.size:
        raise ValueError("Expected nonempty uint8 grayscale")


def ink_mask(page: Gray) -> NDArray[np.bool_]:
    # Otsu partitions supporting runs only; strip pixels always retain grayscale.
    _, mask = cv2.threshold(page, 0, 1, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return np.asarray(mask, dtype=np.bool_)


@dataclass(frozen=True)
class ScaleHypothesis:
    interline_px: float
    thickness_px: float
    support_ratio: float


def estimate_interline(page: Gray, config: GeometryConfig | None = None) -> list[ScaleHypothesis]:
    """Return supported vertical black+white run periods, including mixed scales."""
    validate_gray(page)
    cfg = config or load_config()
    if "GEO-RUN" not in cfg.enabled or int(page.min()) == int(page.max()):
        return []
    mask = ink_mask(page)
    periods: list[int] = []
    thicknesses: list[int] = []
    for column in mask.T:
        edges = np.flatnonzero(np.diff(np.r_[False, column, False]))
        starts, ends = edges[::2], edges[1::2]
        lengths = ends - starts
        gaps = np.diff(starts)
        good = (lengths[:-1] <= gaps * cfg["run.max_thickness"]) & (
            lengths[1:] <= gaps * cfg["run.max_thickness"]
        )
        periods.extend(gaps[good].tolist())
        thicknesses.extend(lengths[:-1][good].tolist())
    if not periods:
        return []
    counts = np.bincount(periods)
    order = np.argsort(-counts, kind="stable")
    result: list[ScaleHypothesis] = []
    samples, thick = np.asarray(periods), np.asarray(thicknesses)
    for period in order:
        if counts[period] < counts.max() * cfg["run.min_support"]:
            break
        if any(
            abs(period - h.interline_px) <= h.interline_px * cfg["group.tolerance"] for h in result
        ):
            continue
        selected = abs(samples - period) <= period * cfg["group.tolerance"]
        result.append(
            ScaleHypothesis(
                float(np.median(samples[selected])),
                float(np.median(thick[selected])),
                float(selected.mean()),
            )
        )
    return result


@dataclass(frozen=True)
class StaffCandidate:
    """S1 geometry only: callers assign S2 system/staff identities explicitly."""

    lines: Floats
    interline_px: float
    thickness_px: float
    confidence_bp: int

    def as_staff(self, staff_id: str, system_id: str) -> Staff:
        xy = self.lines
        low, high = xy.reshape(-1, 2).min(axis=0), xy.reshape(-1, 2).max(axis=0)
        profile = np.mean(np.diff(xy[:, :, 1], axis=0), axis=0)
        return Staff(
            staff_id=staff_id,
            system_id=system_id,
            lines=[[(float(x), float(y)) for x, y in line] for line in xy],
            interline_px=self.interline_px,
            interline_profile=[
                InterlineSample(x=float(x), interline_px=float(s))
                for x, s in zip(xy[0, :, 0], profile, strict=True)
            ],
            line_thickness_px=self.thickness_px,
            bbox=(float(low[0]), float(low[1]), float(high[0] - low[0]), float(high[1] - low[1])),
            line_count=len(xy),
            confidence_bp=self.confidence_bp,
        )


@dataclass(frozen=True)
class Detection:
    candidates: tuple[StaffCandidate, ...]
    diagnostics: tuple[str, ...]


def _peaks(weights: Floats, threshold: float) -> Floats:
    edges = np.flatnonzero(np.diff(np.r_[False, weights >= threshold, False]))
    return np.asarray(
        [
            np.average(np.arange(a, b), weights=weights[a:b])
            for a, b in zip(edges[::2], edges[1::2], strict=True)
        ],
        dtype=np.float64,
    )


def detect_staves(page: Gray, config: GeometryConfig | None = None) -> Detection:
    """Track regular five-line groups across narrow, slope-corrected column bands.

    Five equidistant lines are the standard pitched-staff convention (CONTRACTS 3.3).
    Confidence is geometric support, not calibrated probability. No S2 grouping.
    """
    validate_gray(page)
    cfg = config or load_config()
    scales = estimate_interline(page, cfg)
    if not scales or "GEO-GROUP" not in cfg.enabled:
        early_flags: tuple[str, ...] = ("CLAVIS_NO_STAFF_FOUND",)
        if int(page.min()) != int(page.max()):
            early_flags += ("OOD_REGION",)
        return Detection((), early_flags)
    ink = 1 - page.astype(np.float64) / np.iinfo(np.uint8).max
    found: list[StaffCandidate] = []
    ungrouped = False
    nlines = int(cfg["staff.lines"])
    for scale in scales:
        s = scale.interline_px
        band = max(1, round(cfg["projection.band_width"] * s))
        tracks: list[list[tuple[float, Floats, float]]] = []
        for left in range(0, page.shape[1], band):
            tile = ink[:, left : left + band]
            xlocal = np.arange(tile.shape[1]) - (tile.shape[1] - 1) / 2
            ys = np.arange(len(tile))[:, None]
            best: tuple[float, Floats, float] | None = None
            slopes = np.arange(
                -cfg["projection.max_slope"],
                cfg["projection.max_slope"] + cfg["projection.slope_step"] / 2,
                cfg["projection.slope_step"],
            )
            for slope in slopes:
                rows = np.rint(ys + slope * xlocal).astype(int)
                sampled = tile[np.clip(rows, 0, len(tile) - 1), np.arange(tile.shape[1])]
                projection = np.mean(sampled * ((rows >= 0) & (rows < len(tile))), axis=1)
                score = float(np.sum(projection**2))
                if best is None or score > best[0]:
                    best = score, projection, float(slope)
            assert best is not None
            peaks = _peaks(best[1], cfg["projection.min_ink"])
            center = left + (tile.shape[1] - 1) / 2
            groups: list[Floats] = []
            for k in range(len(peaks) - nlines + 1):
                group = peaks[k : k + nlines]
                if np.max(abs(np.diff(group) - s)) > s * cfg["group.tolerance"]:
                    continue
                extended = k > 0 and abs(group[0] - peaks[k - 1] - s) <= s * cfg["group.tolerance"]
                extended |= (
                    k + nlines < len(peaks)
                    and abs(peaks[k + nlines] - group[-1] - s) <= s * cfg["group.tolerance"]
                )
                if extended:
                    ungrouped = True
                    continue
                groups.append(group)
            if len(peaks) and not groups:
                ungrouped = True
            used: set[int] = set()
            for group in groups:
                choices = [
                    (float(np.max(abs(group - (t[-1][1] + t[-1][2] * (center - t[-1][0]))))), i)
                    for i, t in enumerate(tracks)
                    if i not in used and center - t[-1][0] <= band * cfg["track.max_gap"]
                ]
                distance, index = min(choices, default=(float("inf"), len(tracks)))
                if "GEO-TRACK" not in cfg.enabled or distance > s * cfg["track.tolerance"]:
                    tracks.append([])
                    index = len(tracks) - 1
                tracks[index].append((center, group, best[2]))
                used.add(index)
        for track in tracks:
            if len(track) < 2 or track[-1][0] - track[0][0] < s * cfg["track.min_width"]:
                continue
            xs = np.array([t[0] for t in track])
            yy = np.stack([t[1] for t in track], axis=1)
            # Extend only to columns with observed ink at the predicted five lines.
            for side in (0, -1):
                slope = (yy[:, side] - yy[:, side - 1 if side else 1]) / (
                    xs[side] - xs[side - 1 if side else 1]
                )
                edge_x = np.arange(
                    max(0, int(xs[side] - band)), min(page.shape[1], int(xs[side] + band) + 1)
                )
                edge_y = yy[:, side, None] + slope[:, None] * (edge_x - xs[side])
                rows = np.rint(edge_y).astype(int)
                radius = max(1, round(scale.thickness_px / 2))
                support = np.maximum.reduce(
                    [
                        ink[np.clip(rows + d, 0, len(ink) - 1), edge_x]
                        for d in range(-radius, radius + 1)
                    ]
                )
                visible = edge_x[
                    np.mean(support >= cfg["projection.min_ink"], axis=0)
                    >= cfg["endpoint.min_support"]
                ]
                if visible.size:
                    endpoint = float(visible[side])
                    if (side == 0 and endpoint < xs[0]) or (side == -1 and endpoint > xs[-1]):
                        endpoint_y = yy[:, side] + slope * (endpoint - xs[side])
                        if side == 0:
                            xs, yy = np.r_[endpoint, xs], np.column_stack((endpoint_y, yy))
                        else:
                            xs, yy = np.r_[xs, endpoint], np.column_stack((yy, endpoint_y))
            lines = np.stack((np.broadcast_to(xs, yy.shape), yy), axis=-1)
            if any(
                np.max(abs(c.lines[:, 0, 1] - yy[:, 0])) < s * cfg["group.tolerance"] for c in found
            ):
                continue
            support = len(track) * band / (xs[-1] - xs[0] + band)
            found.append(
                StaffCandidate(
                    lines,
                    float(np.median(np.diff(yy, axis=0))),
                    scale.thickness_px,
                    round(min(1, support) * cfg["confidence.bp_scale"]),
                )
            )
    found.sort(key=lambda c: (float(c.lines[0, 0, 1]), float(c.lines[0, 0, 0])))
    flags = []
    if not found:
        flags.append("CLAVIS_NO_STAFF_FOUND")
    if ungrouped:
        flags.append("OOD_REGION")
    return Detection(tuple(found), tuple(flags))
