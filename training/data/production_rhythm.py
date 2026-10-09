"""Complete meter-group catalogs and empirical marginal fitting; no greedy fills."""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Value:
    kind: str
    dots: int = 0

    @property
    def quarters(self) -> Fraction:
        names = ("whole", "half", "quarter", "eighth", "16th", "32nd")
        return Fraction(4, 2 ** names.index(self.kind)) * sum(
            (Fraction(1, 2**dot) for dot in range(self.dots + 1)), Fraction()
        )

    @property
    def key(self) -> str:
        return f"note:{self.kind}:dots={self.dots}"


def seeded(seed: str) -> np.random.Generator:
    if not re.fullmatch(r"(?:train|eval)-[A-Za-z0-9][A-Za-z0-9_-]*", seed):
        raise ValueError("Explicit train-* or W4 eval-* namespace required")
    return np.random.default_rng(int.from_bytes(hashlib.sha256(seed.encode()).digest(), "big"))


def group_patterns(length: Fraction) -> tuple[tuple[Value, ...], ...]:
    """Enumerate whole valid motifs, never choose a note against remaining length."""
    values = tuple(
        Value(kind, dots)
        for kind in ("whole", "half", "quarter", "eighth", "16th", "32nd")
        for dots in range(3)
    )
    values = tuple(value for value in values if value.quarters <= length)
    duration = {value: value.quarters for value in values}
    motifs: set[tuple[Value, ...]] = set()
    for count in (1, 2, 3):
        for pattern in product(values, repeat=count):
            if sum((duration[v] for v in pattern), Fraction()) == length:
                motifs.add(pattern)
    for value in values:
        repeats = length / value.quarters
        if repeats.denominator == 1:
            motifs.add((value,) * int(repeats))
    return tuple(sorted(motifs, key=lambda p: tuple(v.key for v in p)))


def catalog(meter: str, config: dict[str, Any]) -> tuple[tuple[tuple[Value, ...], ...], ...]:
    """Fixed corpus-independent motif library for the specified meter grouping."""
    rng = seeded(config["catalog_seed"])
    patterns: set[tuple[tuple[Value, ...], ...]] = set()
    numerator, denominator = map(int, meter.split("/"))
    target = Fraction(4 * numerator, denominator)
    cached_pools: dict[Fraction, tuple[tuple[Value, ...], ...]] = {}
    for grouping in config["groupings"][meter]:
        lengths = tuple(Fraction(str(value)) for value in grouping)
        if sum(lengths) != target:
            raise ValueError("Meter grouping has invalid time sum")
        for length in lengths:
            if length not in cached_pools:
                cached_pools[length] = group_patterns(length)
        pools = [cached_pools[length] for length in lengths]
        if any(not pool for pool in pools):
            raise ValueError("Empty complete-group pattern pool")
        # Keep every group motif reachable, plus reproducible mixed-group variants.
        for offset in range(max(map(len, pools))):
            patterns.add(tuple(pool[offset % len(pool)] for pool in pools))
        for _ in range(config["mixed_patterns_per_grouping"]):
            patterns.add(tuple(pool[int(rng.integers(len(pool)))] for pool in pools))
    return tuple(sorted(patterns, key=lambda p: tuple(tuple(v.key for v in group) for group in p)))


@dataclass(frozen=True)
class Fitted:
    patterns: tuple[tuple[tuple[Value, ...], ...], ...]
    probabilities: tuple[float, ...]
    empirical_counts: dict[str, int]
    fitted_note_probabilities: dict[str, float]

    def sample(self, rng: np.random.Generator) -> tuple[tuple[Value, ...], ...]:
        return self.patterns[int(rng.choice(len(self.patterns), p=self.probabilities))]


def fit(meter: str, counts: dict[str, int], config: dict[str, Any]) -> Fitted:
    """Fit expected written-note proportions using complete-group pattern mixtures.

    Least-squares marginal matching uses exponentiated gradient descent. This is
    a generator calibration criterion, not a claimed KL acceptance threshold.
    Actual generated KL must be computed against the untouched corpus counts.
    """
    if not counts or any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("Nonnegative integer empirical counts required")
    patterns = catalog(meter, config)
    vocabulary = sorted({v.key for pattern in patterns for group in pattern for v in group})
    histogram = [Counter(v.key for group in p for v in group) for p in patterns]
    matrix = np.array([[h[key] for key in vocabulary] for h in histogram], dtype=float)
    reference = np.array([counts.get(key, 0) for key in vocabulary], dtype=float)
    if reference.sum() <= 0:
        raise ValueError("No supported empirical note counts for meter")
    reference /= reference.sum()
    # Separate marginal floors preserve raw target provenance for final KL reporting.
    for selected in (
        [i for i, key in enumerate(vocabulary) if ":32nd:" in key],
        [i for i, key in enumerate(vocabulary) if key.endswith("dots=2")],
    ):
        mass = reference[selected].sum()
        floor = config["rare_note_floor_for_fit"]
        if mass < floor:
            reference[selected] += (floor - mass) / len(selected)
            reference /= reference.sum()
    # Optimize notehead-mixture weights on the simplex. Each row is a
    # normalized pattern histogram, so density cannot amplify the gradient.
    # Convert back to pattern-draw probabilities by dividing by pattern size.
    sizes = matrix.sum(axis=1)
    marginals = matrix / sizes[:, None]
    mixture = np.full(len(patterns), 1 / len(patterns))
    for _ in range(config["fit_iterations"]):
        actual = mixture @ marginals
        gradient = marginals @ (actual - reference)
        exponent = np.clip(-config["fit_learning_rate"] * gradient, -20, 20)
        mixture *= np.exp(exponent)
        mixture /= mixture.sum()
    probabilities = mixture / sizes
    probabilities /= probabilities.sum()
    expected = probabilities @ matrix
    expected /= expected.sum()
    return Fitted(
        patterns,
        tuple(map(float, probabilities)),
        counts,
        dict(zip(vocabulary, map(float, expected), strict=True)),
    )
