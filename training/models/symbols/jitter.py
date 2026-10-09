"""Training-only consumer of complete W5 synthetic-v0 empirical error rows."""

import json
from pathlib import Path

import numpy as np

from clavis.contracts.geometry import Staff
from clavis.geometry import StaffCandidate


def jitter_staff(staff: Staff, row: dict) -> Staff:
    """Apply a joint error vector; never turn row identities into recognition rules."""
    lines = [np.asarray(line, dtype=np.float64) for line in staff.lines]
    if any(np.any(np.diff(line[:, 0]) <= 0) for line in lines):
        raise ValueError("Staff lines must be x-monotone")
    space = staff.interline_px
    relative = float(row["interline_relative"])
    offsets = np.asarray(row["line_y_spaces"], dtype=np.float64)
    if offsets.shape != (len(lines),) or not np.isfinite(offsets).all() or relative <= -1:
        raise ValueError("Invalid W5 jitter vector")
    left = max(line[0, 0] for line in lines) + float(row["left_spaces"]) * space
    right = min(line[-1, 0] for line in lines) + float(row["right_spaces"]) * space
    if not np.isfinite([left, right, relative, row["slope_dy_dx"]]).all() or left >= right:
        raise ValueError("Invalid W5 jitter support")
    center = (left + right) / 2
    knots = np.unique(np.r_[left, np.concatenate([line[:, 0] for line in lines]), right])
    knots = knots[(knots >= left) & (knots <= right)]
    result = []
    for index, line in enumerate(lines):
        xs = knots.copy()
        ys = np.interp(xs, line[:, 0], line[:, 1])
        # Extend endpoint tangents, rather than clipping an empirical crop error.
        for endpoint, neighbor, mask in ((0, 1, xs < line[0, 0]), (-1, -2, xs > line[-1, 0])):
            slope = (line[endpoint, 1] - line[neighbor, 1]) / (
                line[endpoint, 0] - line[neighbor, 0]
            )
            ys[mask] = line[endpoint, 1] + slope * (xs[mask] - line[endpoint, 0])
        # W5 records each line's center error, already including spacing error.
        ys += space * offsets[index]
        ys += (xs - center) * float(row["slope_dy_dx"])
        result.append(np.column_stack((xs, ys)))
    candidate = StaffCandidate(
        np.stack(result), space * (1 + relative), staff.line_thickness_px, staff.confidence_bp
    )
    return candidate.as_staff(staff.staff_id, staff.system_id)


def sample_row(path: Path, target_interline: int, rng: np.random.Generator) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document["source"] != "synthetic-v0":
        raise ValueError("Only the explicit W5 synthetic-v0 profile is supported")
    rows = [row for row in document["errors"] if row["target_interline"] == target_interline]
    if not rows:
        raise ValueError("Requested W5 jitter slice is unavailable")
    return rows[int(rng.integers(len(rows)))]
