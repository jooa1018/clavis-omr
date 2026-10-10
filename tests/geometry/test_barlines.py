"""Synthetic S2 proposals preserve ambiguity instead of guessing music."""

import dataclasses

import numpy as np
import pytest

from clavis.geometry import load_config
from clavis.geometry.barlines import propose_barlines


@pytest.mark.parametrize("space", [8, 10, 16, 20])
def test_scale_relative_proposals_and_ambiguity(space):
    page = np.full((15 * space, 20 * space), 255, np.uint8)
    for row in range(5):
        page[(6 + row) * space] = 0
    page[6 * space : 10 * space + 1, 5 * space] = 0
    page[6 * space : 9 * space, 10 * space] = 0  # short stem
    result = propose_barlines(page, space, 6)
    assert len(result) == 1
    assert result[0].u == 5 * space
    assert result[0].coverage == 1
    assert result[0].ambiguity == "BARLINE_OR_STEM"
    cfg = load_config()
    assert (
        propose_barlines(
            page, space, 6, config=dataclasses.replace(cfg, enabled=cfg.enabled - {"GEO-VERTICAL"})
        )
        == ()
    )
    assert result == propose_barlines(page.copy(), space, 6)


def test_blank_thick_and_bad_geometry():
    page = np.full((240, 320), 255, np.uint8)
    assert propose_barlines(page, 16, 6) == ()
    page[96:161, 50:90] = 0
    assert propose_barlines(page, 16, 6) == ()
    for space, margin in [(0, 6), (float("nan"), 6), (16, -1), (16, 20)]:
        with pytest.raises(ValueError):
            propose_barlines(page, space, margin)
