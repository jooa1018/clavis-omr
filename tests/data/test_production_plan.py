from collections import Counter
from pathlib import Path

import pytest
import yaml

from training.data.production_plan import balanced, grace_count, plan_block
from training.data.production_rhythm import seeded


def test_block_mode_meter_and_two_level_ratios() -> None:
    config = yaml.safe_load(
        Path("configs/data/leadgen-production.yaml").read_text(encoding="utf-8")
    )
    plans = plan_block("train-block-plan", config)
    assert Counter(p.mode for p in plans) == {"major": 7500, "minor": 2500}
    assert Counter(p.meter for p in plans) == Counter(
        balanced(10000, config["meter_weights"], seeded("train-other-order"))
    )
    for mode in ("major", "minor"):
        assert {p.fifths for p in plans if p.mode == mode} == set(range(-7, 8))
    for feature, definition in config["features"].items():
        assert sum(feature in p.features for p in plans) == round(
            10000 * definition["song_probability"]
        )
    for plan in plans:
        for name, selected in plan.marked_measures:
            lo, hi = config["features"][name]["within_range"]
            assert len(set(selected)) == len(selected)
            assert lo <= len(selected) / plan.bars <= hi
            assert all(0 <= slot < plan.bars for slot in selected)
    assert plans == plan_block("train-block-plan", config)


def test_eval_namespace_is_explicit_and_is_not_training() -> None:
    config = yaml.safe_load(
        Path("configs/data/leadgen-production.yaml").read_text(encoding="utf-8")
    )
    config["block_acceptance"]["songs"] = 12
    assert plan_block("eval-w4-fixture", config, purpose="w4-evaluation")
    for seed, purpose in [
        ("eval-invalid", "train"),
        ("train-invalid", "w4-evaluation"),
        ("train-x", "unknown"),
    ]:
        with pytest.raises(ValueError):
            plan_block(seed, config, purpose=purpose)
    config["enabled"] = False
    with pytest.raises(ValueError):
        plan_block("train-off", config)


def test_grace_integer_ratio_includes_grace_noteheads() -> None:
    rng = seeded("train-grace")
    for ordinary in range(19, 201):
        count = grace_count(ordinary, 0.02, 0.05, rng)
        assert 0.02 <= count / (ordinary + count) <= 0.05
    for ordinary, low, high in [(18, 0.02, 0.05), (0, 0.02, 0.05), (20, 0.3, 0.2)]:
        with pytest.raises(ValueError):
            grace_count(ordinary, low, high, rng)
    for count, weights in [(0, {"x": 1}), (1, {}), (1, {"x": float("inf")})]:
        with pytest.raises(ValueError):
            balanced(count, weights, rng)
