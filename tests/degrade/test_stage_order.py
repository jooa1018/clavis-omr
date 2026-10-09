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
    ordered = [step for step in ordered if not step.get("capture_factor")]
    if placement == "before_resize":
        ordered = [
            original["operations"][[s["op"] for s in original["operations"]].index("resize")]
            if step.get("finish_capture")
            else step
            for step in ordered
        ]
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
    first = run_preset(
        image,
        labels,
        np.random.default_rng(42),
        catalog,
        "phone-daylight",
        vary_resolution_stage=False,
    )
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


@pytest.mark.parametrize("target", [7, 12, 20, 24])
def test_intermediate_dimensions_final_geometry_and_single_sampling(catalog, target):
    image, labels = fixture()
    preset = catalog["presets"]["phone-daylight"]
    preset["resolution_stage_variant"]["placements"] = ["before_resize"]
    preset["operations"] = [{"op": "resize", "target_interline": target, "interpolation": "area"}]
    output, moved, trace = run_preset(
        image,
        labels,
        np.random.default_rng(3),
        catalog,
        "phone-daylight",
        vary_resolution_stage=True,
    )
    final = next(step for step in trace["operations"] if step.get("capture_final"))
    assert final["capture_intermediate_size"] == [
        min(image.shape[1], 2 * output.shape[1]),
        min(image.shape[0], 2 * output.shape[0]),
    ]
    assert list(output.shape[::-1]) == final["output_size"]
    from training.degrade.ops import apply

    direct, direct_labels, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        {
            "op": "resize",
            "target_interline": target,
            "interpolation": "area",
            "max_pixels": catalog["max_pixels"],
        },
    )
    assert output.shape == direct.shape
    np.testing.assert_allclose(moved.points, direct_labels.points, atol=1e-12)
    np.testing.assert_allclose(moved.boxes, direct_labels.boxes, atol=1e-12)
    restored, _ = replay(image, labels, np.random.default_rng(8), json.loads(json.dumps(trace)))
    np.testing.assert_array_equal(restored, output)


def test_default_probability_is_enforced(catalog):
    image, labels = fixture()
    preset = catalog["presets"]["phone-daylight"]
    assert preset["resolution_stage_variant"]["default_use_probability"] <= 0.3
    preset["operations"] = [{"op": "resize", "target_interline": 12, "interpolation": "area"}]
    seen = set()
    for seed in range(12):
        expected = np.random.default_rng(seed).random() < 0.3
        _, _, trace = run_preset(
            image, labels, np.random.default_rng(seed), catalog, "phone-daylight"
        )
        assert ("resolution_stage_placement" in trace) == expected
        seen.add(expected)
    assert seen == {True, False}


@pytest.mark.parametrize("size", [[0, 1], [321, 240], [100.5, 100]])
def test_explicit_resize_forbids_invalid_size(size):
    from training.degrade.ops import apply

    image, labels = fixture()
    with pytest.raises(ValueError, match="Output size"):
        apply(
            image,
            labels,
            np.random.default_rng(0),
            {
                "op": "resize",
                "target_interline": 12,
                "interpolation": "area",
                "output_size": size,
                "max_pixels": 8000000,
            },
        )


def test_comparison_artifact_contains_matched_errors(catalog, tmp_path, monkeypatch):
    import sys

    from training.degrade import compare_stages

    catalog["presets"] = {"phone-daylight": catalog["presets"]["phone-daylight"]}
    catalog["presets"]["phone-daylight"]["operations"] = [
        {"op": "resize", "target_interline": 7, "interpolation": "area"}
    ]
    config_dir = tmp_path / "configs" / "degrade"
    config_dir.mkdir(parents=True)
    (config_dir / "presets.yaml").write_text(yaml.safe_dump(catalog), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compare_stages, "render", lambda _: fixture())
    monkeypatch.setattr(sys, "argv", ["compare", "--output", str(tmp_path / "result")])
    previous = cv2.getNumThreads()
    try:
        compare_stages.main()
    finally:
        cv2.setNumThreads(previous)
    report = json.loads((tmp_path / "result" / "comparison.json").read_text())
    assert report["pages_executed"] == 18
    assert report["sampling"]["rejected"] == 0
    assert len(report["slices"]) == 4
    for row in report["slices"]:
        if row["placement"] == "before_resize":
            assert len(row["differences"]) == 3
            assert all(
                d["mae"] > 0 and d["label_point_max_error_px"] < 1e-10 for d in row["differences"]
            )
