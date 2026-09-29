"""Deterministic stratified song plans for the adopted two-stage distributions."""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from training.data.production_rhythm import seeded
from training.data.rhythm_groups import conditional_count_bounds


@dataclass(frozen=True)
class SongPlan:
    seed: str
    mode: str
    fifths: int
    meter: str
    bars: int
    features: tuple[str, ...]
    marked_measures: tuple[tuple[str, tuple[int, ...]], ...]


def balanced[T](count: int, weights: dict[T, float], rng: np.random.Generator) -> list[T]:
    """Largest-remainder allocation, shuffled without changing approved marginals."""
    if count <= 0 or not weights or any(not math.isfinite(w) or w <= 0 for w in weights.values()):
        raise ValueError("Positive count and finite positive weights required")
    keys = list(weights)
    probabilities = np.array(list(weights.values()), dtype=float)
    probabilities /= probabilities.max()
    probabilities /= probabilities.sum()
    expected = probabilities * count
    sizes = np.floor(expected).astype(int)
    order = np.argsort(-(expected - sizes), kind="stable")
    sizes[order[: count - int(sizes.sum())]] += 1
    values = [key for key, size in zip(keys, sizes, strict=True) for _ in range(int(size))]
    return [values[int(i)] for i in rng.permutation(count)]


def plan_block(
    seed: str, config: dict[str, Any], *, purpose: str = "train"
) -> tuple[SongPlan, ...]:
    """Plan a block; eval-* is an explicit W4 call path, never training admission."""
    prefix = {"train": "train-", "w4-evaluation": "eval-"}.get(purpose)
    if prefix is None or not seed.startswith(prefix):
        raise ValueError("Purpose and seed namespace must agree")
    if not config["enabled"]:
        raise ValueError("Production planning disabled")
    rng = seeded(seed)
    count = config["block_acceptance"]["songs"]
    modes = balanced(count, config["mode_weights"], rng)
    keys = {
        mode: iter(balanced(modes.count(mode), weights, rng))
        for mode, weights in config["key_weights"].items()
    }
    meters = balanced(count, config["meter_weights"], rng)
    membership: dict[str, set[int]] = {}
    for feature, definition in config["features"].items():
        probability = definition["song_probability"]
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Invalid song probability")
        membership[feature] = set(map(int, rng.permutation(count)[: round(count * probability)]))
    plans = []
    for position, (mode, meter) in enumerate(zip(modes, meters, strict=True)):
        bars = int(rng.choice(config["phrase_bars"]))
        features = tuple(name for name, selected in membership.items() if position in selected)
        marked = []
        for feature in features:
            definition = config["features"][feature]
            if definition.get("within_denominator") == "measures":
                lower, upper = conditional_count_bounds(bars, *definition["within_range"])
                amount = int(rng.integers(lower, upper + 1))
                selected = tuple(sorted(map(int, rng.choice(bars, amount, replace=False))))
                marked.append((feature, selected))
        plans.append(
            SongPlan(
                f"{seed}-{position}",
                mode,
                int(next(keys[mode])),
                meter,
                bars,
                features,
                tuple(marked),
            )
        )
    return tuple(plans)


def grace_count(base_noteheads: int, lower: float, upper: float, rng: np.random.Generator) -> int:
    """Grace/(ordinary+grace) denominator, without rounding beyond approved bounds."""
    from fractions import Fraction

    lo, hi = Fraction(str(lower)), Fraction(str(upper))
    if base_noteheads <= 0 or not 0 < lo <= hi < 1:
        raise ValueError("Invalid grace-note denominator or range")
    minimum = max(1, math.ceil(lo * base_noteheads / (1 - lo)))
    maximum = math.floor(hi * base_noteheads / (1 - hi))
    if minimum > maximum:
        raise ValueError("Song requires more ordinary noteheads for approved grace ratio")
    return int(rng.integers(minimum, maximum + 1))
