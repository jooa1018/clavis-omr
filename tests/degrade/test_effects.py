"""Synthetic-only checks for photometry, nonlinear geometry, and route replay."""

import json
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from tests.degrade.test_ops import centroid_errors, fixture, op
from training.degrade.curve import densify, envelope, transform
from training.degrade.ops import apply, run, sample_interline
from training.degrade.presets import replay, run_preset


@pytest.fixture
def catalog():
    return yaml.safe_load(Path("configs/degrade/presets.yaml").read_text(encoding="utf-8"))


EFFECTS = [
    {
        "op": "illumination",
        "x_slope": 0.1,
        "y_slope": -0.1,
        "vignette": 0.1,
        "shadow_strength": 0.3,
        "shadow_radius": 0.5,
        "shadow_x": 0,
        "shadow_y": 0.2,
    },
    {"op": "blur", "sigma_spaces": 0.1},
    {"op": "noise", "sigma": 0.03},
    {"op": "threshold", "level": 0.6},
    {"op": "photocopy", "radius_spaces": 0.1, "mode": "thicken"},
    {"op": "paper", "strength": 0.2, "grain_spaces": 4},
    {
        "op": "screen",
        "period_spaces": 0.3,
        "strength": 0.2,
        "phase_radians": 0,
        "angle_degrees": 15,
    },
]


@pytest.mark.parametrize("effect", EFFECTS)
@pytest.mark.parametrize("color", [False, True])
def test_photometric_purity_and_replay(effect, color, catalog):
    image, labels = fixture(color)
    image = np.where(image == 0, 40, 220).astype(np.uint8)
    before = image.copy()
    params = {**catalog["limits"], **effect, "max_pixels": catalog["max_pixels"]}
    output, moved, record = apply(image, labels, np.random.default_rng(4), params)
    assert output.shape == image.shape and output.dtype == np.uint8
    assert np.any(output != image)
    assert moved is labels
    np.testing.assert_array_equal(image, before)
    restored, _ = replay(
        image, labels, np.random.default_rng(111), {"operations": [json.loads(json.dumps(record))]}
    )
    np.testing.assert_array_equal(output, restored)


def test_zero_strength_and_photocopy_directions(catalog):
    image, labels = fixture()
    base = {**catalog["limits"], "max_pixels": catalog["max_pixels"]}
    for effect in [
        {"op": "blur", "sigma_spaces": 0},
        {"op": "noise", "sigma": 0},
        {"op": "paper", "strength": 0, "grain_spaces": 2},
    ]:
        output, _, _ = apply(image, labels, np.random.default_rng(0), {**base, **effect})
        np.testing.assert_array_equal(image, output)
    thick, _, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        {**base, "op": "photocopy", "radius_spaces": 0.1, "mode": "thicken"},
    )
    thin, _, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        {**base, "op": "photocopy", "radius_spaces": 0.1, "mode": "thin"},
    )
    assert thick.sum() < image.sum() < thin.sum()


@pytest.mark.parametrize("generator", [np.random.PCG64, np.random.MT19937])
def test_rng_state_and_seed_diversity(generator, catalog):
    image, labels = fixture()
    params = {**catalog["limits"], **op("noise", sigma=0.02)}
    output, _, record = apply(image, labels, np.random.Generator(generator(5)), params)
    restored, _, _ = apply(
        image, labels, np.random.Generator(generator(91)), json.loads(json.dumps(record))
    )
    np.testing.assert_array_equal(output, restored)
    different, _, _ = apply(image, labels, np.random.Generator(generator(6)), params)
    assert not np.array_equal(output, different)


@pytest.mark.parametrize("strength", [-1.5, 0, 1.5])
def test_curve_grid_boxes_and_chord_error(strength, catalog, record_property):
    image, labels = fixture()
    # One box crosses the interior sine maximum, which four-corner transforms miss.
    labels = replace(
        labels,
        boxes=np.array([[20, 60, 150, 90]], float),
        polylines=(np.array([[20, 60], [290, 60]], float),),
    )
    params = {
        **catalog["limits"],
        **op("paper_wave", amplitude_spaces=strength, phase_radians=0, chord_error_px=0.25),
    }
    out, moved, record = apply(image, labels, np.random.default_rng(0), params)
    pixel_error = max(centroid_errors(out, moved.points))
    record_property("wave_centroid_max_error_px", pixel_error)
    assert pixel_error <= 0.5
    amplitude, omega = record["map"]["amplitude_px"], record["map"]["omega"]
    x = np.linspace(20, 150, 10001)
    ys = amplitude * np.sin(omega * x)
    assert moved.boxes[0, 1] <= 60 + ys.min() + 1e-8
    assert moved.boxes[0, 3] >= 90 + ys.max() - 1e-8
    dense_x = np.linspace(20, 290, 10001)
    interpolated = np.interp(dense_x, moved.polylines[0][:, 0], moved.polylines[0][:, 1])
    chord_error = float(np.max(np.abs(interpolated - (60 + amplitude * np.sin(omega * dense_x)))))
    record_property("wave_chord_max_error_px", chord_error)
    assert chord_error <= 0.25
    np.testing.assert_allclose(
        moved.interlines,
        24
        / np.sqrt(1 + (amplitude * omega * np.cos(omega * labels.interline_pairs[:, 0, 0])) ** 2),
    )
    yy, xx = np.indices(image.shape)
    source_y = yy - amplitude * np.sin(omega * xx)
    nearest_y = np.rint(source_y).astype(int)
    inside = (nearest_y >= 0) & (nearest_y < image.shape[0])
    reference = np.zeros_like(image)
    reference[inside] = labels.masks[0][nearest_y[inside], xx[inside]]
    untied = np.abs(np.abs(source_y - nearest_y) - 0.5) > 0.001
    np.testing.assert_array_equal(moved.masks[0][untied], reference[untied])
    if strength:
        assert record["matrix"] is None


def test_curve_limits_and_truncation(catalog):
    with pytest.raises(ValueError, match="budget"):
        densify(np.array([[0, 0], [320, 0]]), 40, 0.02, 0.001, 2)
    np.testing.assert_array_equal(densify(np.array([[0, 0]]), 40, 0.02, 0.1, 2), [[0, 0]])
    image, labels = fixture()
    labels = replace(labels, points=np.array([[80, 239]], float))
    _, moved, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        {
            **catalog["limits"],
            **op("paper_wave", amplitude_spaces=1, phase_radians=0, chord_error_px=0.25),
        },
    )
    assert moved.truncated
    assert envelope(np.empty((0, 4)), 10, 0.1, 0).shape == (0, 4)
    assert transform(np.empty((0, 2)), 10, 0.1, 0).shape == (0, 2)


@pytest.mark.parametrize(
    "name",
    [
        "scan-150",
        "scan-300",
        "scan-bw",
        "phone-daylight",
        "phone-indoor",
        "phone-angle",
        "phone-shadow",
        "phone-curl",
        "messenger-kakao",
        "screenshot-downscaled",
        "photocopy",
        "screen-photo",
    ],
)
def test_presets_full_trace(name, catalog):
    image, labels = fixture(color=True)
    pairs = labels.interline_pairs.copy()
    pairs[:, 1, 1] = pairs[:, 0, 1] + 40
    labels = replace(labels, interline_pairs=pairs)
    threads_before = cv2.getNumThreads()
    baseline = None
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(3):
                output, moved, record = run_preset(
                    image, labels, np.random.default_rng(13), catalog, name
                )
                signature = (
                    output.tobytes(),
                    moved.points.tobytes(),
                    json.dumps(record, sort_keys=True),
                )
                if baseline is None:
                    baseline = signature
                assert signature == baseline
        restored, replay_labels = replay(
            image, labels, np.random.default_rng(72), json.loads(json.dumps(record))
        )
        np.testing.assert_array_equal(restored, output)
        np.testing.assert_array_equal(replay_labels.masks[0], moved.masks[0])
        if name == "phone-curl":
            assert record["matrix"] is None
        else:
            assert np.array(record["matrix"]).shape == (3, 3)
        assert record["status"] == "experimental-unfitted"
    finally:
        cv2.setNumThreads(threads_before)


def test_prescribed_distribution_and_illegible_flag(catalog):
    distribution = catalog["definitions"]["resolution"]["target_interline"][
        "interline_distribution"
    ]
    rng = np.random.default_rng(8)
    targets = np.array([sample_interline(rng, 40, distribution) for _ in range(10000)])
    counts, _ = np.histogram(targets, bins=[7, 10, 14, 24, 40])
    np.testing.assert_allclose(counts / len(targets), distribution["weights"], atol=0.02)
    with pytest.raises(ValueError, match="Sampled"):
        sample_interline(rng, 4, distribution)
    image, labels = fixture()
    _, _, record = run(
        image,
        labels,
        rng,
        {**catalog, "operations": [op("resize", target_interline=4, interpolation="area")]},
    )
    assert record["illegible_candidate"]


@pytest.mark.parametrize(
    "bad",
    [
        {"op": "noise", "sigma": -1},
        {"op": "blur", "sigma_spaces": float("nan")},
        {"op": "screen", "period_spaces": 0},
        {"op": "photocopy", "radius_spaces": 0.1, "mode": "unknown"},
    ],
)
def test_invalid_photometry(bad, catalog):
    image, labels = fixture()
    with pytest.raises(ValueError):
        apply(
            image,
            labels,
            np.random.default_rng(0),
            {**catalog["limits"], "max_pixels": catalog["max_pixels"], **bad},
        )


def test_wrong_replay_generator_and_camera_identity(catalog):
    image, labels = fixture()
    _, _, record = apply(
        image, labels, np.random.Generator(np.random.MT19937(2)), op("noise", sigma=0.1)
    )
    with pytest.raises(ValueError, match="bit-generator"):
        apply(image, labels, np.random.default_rng(0), record)
    out, moved, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        op("perspective", tilt_x_degrees=0, tilt_y_degrees=0, focal_ratio=1.5),
    )
    np.testing.assert_array_equal(out, image)
    np.testing.assert_allclose(moved.points, labels.points)


def test_smoke_outputs_and_page_count(catalog, tmp_path, monkeypatch):
    import sys

    from training.degrade.smoke import main

    catalog["presets"] = {"scan-300": catalog["presets"]["scan-300"]}
    config = tmp_path / "input.yaml"
    config.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["smoke", "--config", str(config), "--output", str(tmp_path)])
    main()
    report = json.loads((tmp_path / "smoke.json").read_text())
    assert report["pages_executed"] == 6
    assert report["peak_rss_bytes"] > 0
    assert len(report["slices"]) == 2
    assert (tmp_path / "overview.png").exists()
