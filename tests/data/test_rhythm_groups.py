"""Synthetic arithmetic fixtures, never a replacement PDMX target."""

import math
from fractions import Fraction as F

import numpy as np
import pytest

from training.data.rhythm_groups import (
    Pattern,
    conditional_count_bounds,
    kl_divergence,
    sample_groups,
)


def test_complete_groups_preserve_time_and_determinism() -> None:
    pools = {
        F(1): [Pattern((F(1),), 2), Pattern((F(1, 2), F(1, 2)), 1)],
        F(3, 2): [Pattern((F(3, 4), F(3, 4)), 1)],
    }
    groups = [F(1), F(3, 2), F(1)]
    first = sample_groups(np.random.default_rng(7), groups, pools, enabled=True)
    assert first == sample_groups(np.random.default_rng(7), groups, pools, enabled=True)
    assert [sum(group) for group in first] == groups
    assert all(
        group in [p.durations for p in pools[size]]
        for size, group in zip(groups, first, strict=True)
    )


@pytest.mark.parametrize(
    "pattern",
    [
        Pattern((), 1),
        Pattern((F(0), F(1)), 1),
        Pattern((F(2),), 1),
        Pattern((F(1),), math.inf),
        Pattern((F(1),), 0),
    ],
)
def test_reject_invalid_patterns(pattern: Pattern) -> None:
    with pytest.raises(ValueError):
        sample_groups(np.random.default_rng(1), [F(1)], {F(1): [pattern]}, enabled=True)


def test_missing_disabled_or_invalid_groups() -> None:
    for groups, enabled in [([F(1)], True), ([F(1)], False), ([], True), ([F(0)], True)]:
        with pytest.raises(ValueError):
            sample_groups(np.random.default_rng(1), groups, {}, enabled=enabled)


def test_kl_known_values_and_zeros() -> None:
    assert kl_divergence({"a": 2, "b": 2}, {"a": 5, "b": 5}) == 0
    assert kl_divergence({"a": 4, "b": 0}, {"a": 2, "b": 2}) == pytest.approx(math.log(2))
    assert math.isinf(kl_divergence({"a": 1}, {"b": 1}))


@pytest.mark.parametrize("counts", [{}, {"a": 0}, {"a": -1}, {"a": True}, {"a": 0.5}])
def test_kl_invalid_counts(counts: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        kl_divergence(counts, {"a": 1})
    with pytest.raises(ValueError):
        kl_divergence({"a": 1}, counts)


def test_conditional_ratios_cannot_round_outside_limits() -> None:
    assert conditional_count_bounds(4, 0.1, 0.3) == (1, 1)
    assert conditional_count_bounds(8, 0.2, 0.5) == (2, 4)
    assert conditional_count_bounds(20, 0.02, 0.05) == (1, 1)
    for args in [(19, 0.02, 0.05), (0, 0.1, 0.3), (4, 0.5, 0.2)]:
        with pytest.raises(ValueError):
            conditional_count_bounds(*args)
