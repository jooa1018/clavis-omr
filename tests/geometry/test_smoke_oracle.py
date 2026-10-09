"""Independent toy expectations for the synthetic removal diagnostic (not W4)."""

import numpy as np
import pytest

from training.models.staff.smoke import aggregate_removal, removal_quality


def test_removal_oracle_extremes():
    original = np.array([[0, 0, 255]], dtype=np.uint8)
    symbols = np.array([[255, 0, 255]], dtype=np.uint8)
    unchanged = aggregate_removal([removal_quality(original, original, symbols)])
    assert unchanged["staff_residue_ratio"] == 1
    assert unchanged["symbol_damage_ratio"] == 0
    perfect = aggregate_removal([removal_quality(original, symbols, symbols)])
    assert perfect["staff_residue_ratio"] == perfect["symbol_damage_ratio"] == 0
    erased = np.full_like(original, 255)
    damaged = aggregate_removal([removal_quality(original, erased, symbols)])
    assert damaged["staff_residue_ratio"] == 0
    assert damaged["symbol_damage_ratio"] == 1


def test_removal_oracle_empty_and_shape():
    blank = np.full((2, 2), 255, dtype=np.uint8)
    measured = aggregate_removal([removal_quality(blank, blank, blank)])
    assert measured["staff_residue_ratio"] is None
    assert measured["symbol_damage_ratio"] is None
    with pytest.raises(ValueError):
        removal_quality(blank, blank[:1], blank)


def test_residue_excludes_neighbor_staff_but_keeps_symbol_damage():
    original = np.zeros((1, 3), dtype=np.uint8)
    symbols = np.array([[255, 255, 0]], dtype=np.uint8)
    removed = np.array([[255, 0, 255]], dtype=np.uint8)
    target = np.array([[True, False, True]])
    measured = aggregate_removal([removal_quality(original, removed, symbols, target)])
    assert measured["staff_ink"] == 255
    assert measured["staff_residue_ratio"] == 0
    assert measured["symbol_damage_ratio"] == 1
    with pytest.raises(ValueError):
        removal_quality(original, removed, symbols, target[:, :1])
