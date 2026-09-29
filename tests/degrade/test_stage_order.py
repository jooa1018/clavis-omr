"""Capture blur/noise versus post-resize processing, including exact trace replay."""

import json
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from tests.degrade.test_ops import fixture
from training.degrade.presets import replay, resolution_stage_variant, run_preset
from training.degrade.sampling import SampleRejected, SamplingStats


@pytest.fixture
def catalog():
    return yaml.safe_load(Path("configs/degrade/presets.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name", ["phone-daylight", "phone-indoor", "phone-angle", "phone-shadow", "phone-curl"]
)
@pytest.mark.parametrize("placement", ["before_resize", "after_resize"])
def test_all_phone_routes_preserve_strengths_and_place_one_block(catalog, name, placement):
    preset = catalog["presets"][name]
    preset["resolution_stage_variant"]["placements"] = [placement]
    original = deepcopy(preset)
    ordered, selected = resolution_stage_variant(preset, np.random.default_rng(1))
    names = [step["op"] for step in ordered]
    position = names.index("resize")
    expected = (
        ["blur", "noise", "resize"] if placement == "before_resize" else ["resize", "blur", "noise"]
    )
    start = position - 2 if placement == "before_resize" else position
    assert names[start : start + 3] == expected
    assert names.count("blur") == names.count("noise") == 1
    for effect in ("blur", "noise"):
        source = next((step for step in original["operations"] if step["op"] == effect), None)
        if source is not None:
            assert next(step for step in ordered if step["op"] == effect) == source
    assert [step for step in ordered if step["op"] not in ("blur", "noise")] == [
        step for step in original["operations"] if step["op"] not in ("blur", "noise")
    ]
    assert selected == placement
    assert preset == original


def test_both_stages_draw_from_caller_rng(catalog):
    rng = np.random.default_rng(19)
    oracle = np.random.default_rng(19)
    preset = catalog["presets"]["phone-daylight"]
    choices = preset["resolution_stage_variant"]["placements"]
    draws = []
    for _ in range(100):
        _, placement = resolution_stage_variant(preset, rng)
        assert placement == choices[int(oracle.integers(len(choices)))]
        draws.append(placement)
    assert set(draws) == set(choices)
    assert rng.bit_generator.state == oracle.bit_generator.state


def test_stage_changes_pixels_preserves_labels_and_replays_at_both_thread_counts(catalog):
    image, labels = fixture()
    image = np.repeat(image[..., None], 3, axis=2) if image.ndim == 2 else image
    preset = catalog["presets"]["phone-daylight"]
    preset["operations"] = [
        {"op": "resize", "target_interline": 12, "interpolation": "area"},
        {"op": "blur", "sigma_spaces": 0.1},
        {"op": "noise", "sigma": 0.025},
    ]
    results = {}
    original_threads = cv2.getNumThreads()
    try:
        for placement in ("before_resize", "after_resize"):
            preset["resolution_stage_variant"]["placements"] = [placement]
            reference = None
            for threads in (1, 4):
                cv2.setNumThreads(threads)
                for _ in range(3):
                    output, moved, trace = run_preset(
                        image,
                        labels,
                        np.random.default_rng(7),
                        catalog,
                        "phone-daylight",
                        vary_resolution_stage=True,
                    )
                    trace = json.loads(json.dumps(trace))
                    restored, replayed = replay(image, labels, np.random.default_rng(0), trace)
                    np.testing.assert_array_equal(output, restored)
                    np.testing.assert_array_equal(moved.masks[0], replayed.masks[0])
                    np.testing.assert_array_equal(moved.points, replayed.points)
                    assert trace["resolution_stage_placement"] == placement
                    if reference is not None:
                        np.testing.assert_array_equal(output, reference[0])
                        assert trace == reference[2]
                    reference = (output, moved, trace)
            results[placement] = reference
    finally:
        cv2.setNumThreads(original_threads)
    before, after = results["before_resize"], results["after_resize"]
    assert np.any(before[0] != after[0])
    np.testing.assert_array_equal(before[1].points, after[1].points)
    np.testing.assert_array_equal(before[1].boxes, after[1].boxes)
    np.testing.assert_array_equal(before[1].masks[0], after[1].masks[0])
    np.testing.assert_array_equal(before[1].interlines, after[1].interlines)


def test_default_is_unchanged_and_variant_rejections_count(catalog):
    image, labels = fixture()
    preset = catalog["presets"]["phone-daylight"]
    first = run_preset(image, labels, np.random.default_rng(42), catalog, "phone-daylight")
    default = run_preset(
        image,
        labels,
        np.random.default_rng(42),
        catalog,
        "phone-daylight",
        vary_resolution_stage=False,
    )
    np.testing.assert_array_equal(first[0], default[0])
    assert first[2] == default[2]
    assert "resolution_stage_placement" not in first[2]
    for step in preset["operations"]:
        if step["op"] == "resize":
            step["target_interline"]["interline_distribution"].update(bands=[[30, 40]], weights=[1])
    stats = SamplingStats(0.01)
    with pytest.raises(SampleRejected) as caught:
        run_preset(
            image,
            labels,
            np.random.default_rng(0),
            catalog,
            "phone-daylight",
            stats,
            vary_resolution_stage=True,
        )
    assert caught.value.record["resolution_stage_placement"] in ("before_resize", "after_resize")
    assert stats.summary()["rejected"] == stats.summary()["attempted"] == 1


@pytest.mark.parametrize(
    "fault", ["missing", "empty", "unknown", "operators", "resize", "duplicate"]
)
def test_invalid_variant_fails_before_random_draw(catalog, fault):
    preset = catalog["presets"]["phone-daylight"]
    if fault == "missing":
        del preset["resolution_stage_variant"]
    elif fault == "empty":
        preset["resolution_stage_variant"]["placements"] = []
    elif fault == "unknown":
        preset["resolution_stage_variant"]["placements"] = ["other"]
    elif fault == "operators":
        preset["resolution_stage_variant"]["operators"] = []
    elif fault == "resize":
        preset["operations"] = [step for step in preset["operations"] if step["op"] != "resize"]
    elif fault == "duplicate":
        preset["operations"].append({"op": "blur"})
    rng = np.random.default_rng(3)
    state = deepcopy(rng.bit_generator.state)
    with pytest.raises(ValueError, match="variant"):
        resolution_stage_variant(preset, rng)
    assert rng.bit_generator.state == state
