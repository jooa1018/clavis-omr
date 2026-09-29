"""ADR-011 provisional G1 sampling, with explicit rejection accounting."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np


class SampleRejected(ValueError):
    """A sampled band is unsupported; callers must count it, never silently redraw."""

    def __init__(self, record: dict[str, Any]) -> None:
        super().__init__("Sampled interline band exceeds source interline")
        self.record = record


@dataclass
class SamplingStats:
    """Caller-owned, batch-level counters. No process-global mutable state."""

    rate_limit: float
    attempted: int = 0
    rejected: int = 0
    by_band: dict[int, dict[str, int]] = field(default_factory=dict)

    def add(self, record: dict[str, Any]) -> None:
        self.attempted += 1
        rejected = int(record["rejected"])
        self.rejected += rejected
        row = self.by_band.setdefault(record["band_index"], {"attempted": 0, "rejected": 0})
        row["attempted"] += 1
        row["rejected"] += rejected

    def summary(self) -> dict[str, Any]:
        rate = self.rejected / self.attempted if self.attempted else None
        return {
            "attempted": self.attempted,
            "accepted": self.attempted - self.rejected,
            "rejected": self.rejected,
            "rejection_rate": rate,
            "rate_limit": self.rate_limit,
            "w2_report_required": rate is not None and rate >= self.rate_limit,
            "by_band": {str(k): dict(v) for k, v in self.by_band.items()},
        }


def draw_interline(
    rng: np.random.Generator,
    source: float,
    distribution: dict[str, Any],
    stats: SamplingStats | None = None,
) -> dict[str, Any]:
    """Choose the prescribed band first, then uniformly sample its feasible range."""
    cap = float(distribution["upper_cap_px"])
    bands = np.asarray(
        [[lo, cap if hi is None else hi] for lo, hi in distribution["bands"]], dtype=float
    )
    weights = np.asarray(distribution["weights"], dtype=float)
    if (
        not np.isfinite(source)
        or source <= 0
        or not np.isfinite(cap)
        or cap <= 0
        or bands.ndim != 2
        or bands.shape[1] != 2
        or len(bands) != len(weights)
        or not np.isfinite(bands).all()
        or np.any(bands[:, 0] <= 0)
        or np.any(bands[:, 0] > bands[:, 1])
        or not np.isfinite(weights).all()
        or np.any(weights < 0)
        or not np.isclose(weights.sum(), 1)
    ):
        raise ValueError("Invalid interline distribution or source")
    index = int(rng.choice(len(bands), p=weights))
    low, high = float(bands[index, 0]), min(float(bands[index, 1]), source)
    record = {
        "band_index": index,
        "band_low_px": low,
        "band_high_px": float(bands[index, 1]),
        "source_interline_px": source,
        "feasible_high_px": high,
        "rejected": source < low,
        "target_interline_px": None,
    }
    if stats is not None:
        stats.add(record)
    if source < low:
        raise SampleRejected(record)
    record["target_interline_px"] = float(rng.uniform(low, high))
    return record
