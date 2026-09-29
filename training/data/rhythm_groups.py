"""Beat-group sampling primitives; no corpus target or training admission defaults."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

import numpy as np


@dataclass(frozen=True)
class Pattern:
    """A complete group in quarter-note units, weighted by the caller's evidence."""

    durations: tuple[Fraction, ...]
    weight: float


def sample_groups(
    rng: np.random.Generator,
    groups: Sequence[Fraction],
    patterns: Mapping[Fraction, Sequence[Pattern]],
    *,
    enabled: bool,
) -> tuple[tuple[Fraction, ...], ...]:
    """Choose whole patterns, never conditional notes that fill a remaining length.

    Groups are supplied by a meter-aware caller; spans across beats must be
    represented as complete multi-beat groups. This primitive does not infer
    notation (ties, rests, tuplets, dots) from elapsed durations.
    """
    if not enabled:
        raise ValueError("DATA-GEN-002 disabled")
    if not groups or any(group <= 0 for group in groups):
        raise ValueError("Positive beat groups are required")
    pools: list[Sequence[Pattern]] = []
    for group in groups:
        pool = patterns.get(group, ())
        if not pool:
            raise ValueError("Missing complete patterns for beat group")
        for pattern in pool:
            if (
                not pattern.durations
                or any(duration <= 0 for duration in pattern.durations)
                or sum(pattern.durations, Fraction()) != group
                or not math.isfinite(pattern.weight)
                or pattern.weight <= 0
            ):
                raise ValueError("Invalid complete beat-group pattern")
        pools.append(pool)
    result = []
    for pool in pools:
        weights = np.array([pattern.weight for pattern in pool], dtype=float)
        weights /= weights.max()
        result.append(pool[int(rng.choice(len(pool), p=weights / weights.sum()))].durations)
    return tuple(result)


def kl_divergence(generated: Mapping[str, int], target: Mapping[str, int]) -> float:
    """D_KL(generated || target), natural logarithms, no implicit smoothing.

    Category keys must encode the same notation and denominator in both inputs.
    Call separately per meter; pooled counts are not a meter-specific target.
    Zero target mass with positive generated mass returns infinity.
    """
    for counts in (generated, target):
        if (
            not counts
            or any(type(count) is not int or count < 0 for count in counts.values())
            or sum(counts.values()) <= 0
        ):
            raise ValueError("Nonnegative integer counts with positive total required")
    total, target_total = sum(generated.values()), sum(target.values())
    terms = []
    for key, count in generated.items():
        if count == 0:
            continue
        reference = target.get(key, 0)
        if reference == 0:
            return math.inf
        p, q = count / total, reference / target_total
        terms.append(p * math.log(p / q))
    return math.fsum(terms)


def conditional_count_bounds(total: int, lower: float, upper: float) -> tuple[int, int]:
    """Return feasible positive event counts without rounding outside approved rates."""
    if total <= 0 or not 0 < lower <= upper <= 1:
        raise ValueError("Positive denominator and ordered probabilities required")
    lo = max(1, math.ceil(total * Fraction(str(lower))))
    hi = math.floor(total * Fraction(str(upper)))
    if lo > hi:
        raise ValueError("No integer count satisfies the approved within-song range")
    return lo, hi
