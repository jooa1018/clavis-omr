"""Synthetic geometry only; never open Dev or sealed data."""

import json

import cv2
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from training.degrade.ops import Labels, apply, project, run


def fixture(color=False):
    image = np.full((240, 320), 255, np.uint8)
    points = np.array([[x, y] for y in (60, 120, 180) for x in (60, 120, 180, 240)], float)
    mask = np.zeros_like(image)
    for i, (x, y) in enumerate(points.astype(int), 1):
        cv2.circle(image, (x, y), 5, 0, -1)
        cv2.circle(mask, (x, y), 5, i, -1)
    boxes = np.column_stack((points - 5, points + 5))
    pairs = np.array([[[60, 60], [60, 84]], [[180, 120], [180, 144]]], float)
    labels = Labels(points, boxes, (points[:4],), (mask,), pairs)
    return np.repeat(image[..., None], 3, axis=2) if color else image, labels


def op(name, **params):
    return {"op": name, "max_pixels": 8_000_000, **params}


def centroid_errors(image, expected):
    errors = []
    for x, y in expected:
        cx, cy = round(x), round(y)
        patch = 255.0 - image[cy - 8 : cy + 9, cx - 8 : cx + 9].astype(float)
        yy, xx = np.indices(patch.shape)
        center = np.array([(patch * xx).sum(), (patch * yy).sum()]) / patch.sum()
        errors.append(float(np.linalg.norm(center + [cx - 8, cy - 8] - [x, y])))
    return errors


@settings(max_examples=40, deadline=None, derandomize=True)
@given(angle=st.floats(-8, 8), px=st.floats(-0.0003, 0.0003), py=st.floats(-0.0003, 0.0003))
def test_grid_pixels_and_labels(angle, px, py):
    image, labels = fixture()
    for params in (
        op("rotation", degrees=angle),
        op("perspective", matrix=[[1, 0.02, 0], [0.01, 1, 0], [px, py, 1]]),
    ):
        output, moved, record = apply(image, labels, np.random.default_rng(0), params)
        assert max(centroid_errors(output, moved.points)) <= 0.5
        matrix = np.array(record["matrix"])
        np.testing.assert_allclose(
            project(moved.points, np.linalg.inv(matrix)), labels.points, atol=1e-10
        )
        corners = labels.boxes[:, [0, 1, 2, 1, 2, 3, 0, 3]].reshape(-1, 4, 2)
        corners = project(corners, matrix)
        np.testing.assert_allclose(moved.boxes[:, :2], corners.min(axis=1))
        np.testing.assert_allclose(moved.boxes[:, 2:], corners.max(axis=1))
        np.testing.assert_allclose(moved.polylines[0], moved.points[:4])
        assert set(np.unique(moved.masks[0])) <= set(np.unique(labels.masks[0]))
        # A categorical centroid is quantized (up to sqrt(0.5) px for translation).
        # Check masks against an independent inverse nearest-neighbor raster oracle.
        yy, xx = np.indices(image.shape)
        back = project(np.stack((xx, yy), axis=-1), np.linalg.inv(matrix))
        nearest = np.rint(back).astype(int)
        inside = np.all((nearest >= 0) & (nearest < [320, 240]), axis=-1)
        expected_mask = np.zeros_like(image)
        expected_mask[inside] = labels.masks[0][nearest[..., 1][inside], nearest[..., 0][inside]]
        untied = np.all(np.abs(np.abs(back - nearest) - 0.5) > 0.001, axis=-1)
        np.testing.assert_array_equal(moved.masks[0][untied], expected_mask[untied])


@pytest.mark.parametrize("target", [16, 12, 10, 8, 7])
@pytest.mark.parametrize("interpolation", ["area", "bilinear", "bicubic", "nearest"])
def test_resize_grid(target, interpolation):
    image, labels = fixture()
    out, moved, record = apply(
        image,
        labels,
        np.random.default_rng(0),
        op("resize", target_interline=target, interpolation=interpolation),
    )
    assert max(centroid_errors(out, moved.points)) <= 0.5
    np.testing.assert_allclose(moved.interlines, target, atol=1e-12)
    assert record["actual_interlines"] == moved.interlines.tolist()
    assert out.shape == (round(240 * target / 24), round(320 * target / 24))


@pytest.mark.parametrize("color", [False, True])
def test_replay_purity_and_threads(color):
    image, labels = fixture(color)
    original = image.copy()
    mask = labels.masks[0].copy()
    config = {
        "max_pixels": 8_000_000,
        "operations": [
            {"op": "rotation", "degrees": {"uniform": [-8, 8]}},
            {"op": "perspective", "matrix": [[1, 0, 0], [0, 1, 0], [0.0001, 0, 1]]},
            {
                "op": "resize",
                "target_interline": 8,
                "interpolation": {"choice": ["area", "bicubic"]},
            },
            {"op": "jpeg", "quality": 70, "repeats": 2, "subsampling": 2},
        ],
    }
    baseline = None
    old_threads = cv2.getNumThreads()
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(3):
                output, moved, record = run(image, labels, np.random.default_rng(31), config)
                signature = (
                    output.tobytes(),
                    json.dumps(record, sort_keys=True),
                    moved.points.tobytes(),
                )
                if baseline is None:
                    baseline = signature
                assert signature == baseline
                replay, replay_labels = image, labels
                for params in record["operations"]:
                    replay, replay_labels, _ = apply(
                        replay, replay_labels, np.random.default_rng(99), params
                    )
                np.testing.assert_array_equal(output, replay)
                np.testing.assert_array_equal(moved.masks[0], replay_labels.masks[0])
                np.testing.assert_allclose(
                    moved.points, project(labels.points, np.array(record["matrix"]))
                )
    finally:
        cv2.setNumThreads(old_threads)
    np.testing.assert_array_equal(image, original)
    np.testing.assert_array_equal(labels.masks[0], mask)


@pytest.mark.parametrize(
    "params",
    [
        op("rotation", degrees=float("nan")),
        op("perspective", matrix=np.zeros((3, 3))),
        op("perspective", matrix=[[1, 0, 0], [0, 1, 0], [-0.01, 0, 1]]),
        op("perspective", matrix=[[1, 0], [0, 1]]),
        op("resize", target_interline=0),
        op("resize", target_interline=25),
        op("jpeg", quality=96, repeats=1, subsampling=0),
        op("bad"),
    ],
)
def test_invalid_params(params):
    image, labels = fixture()
    with pytest.raises(ValueError):
        apply(image, labels, np.random.default_rng(0), params)


def test_truncation_empty_labels_and_rounding():
    image, labels = fixture()
    labels = Labels(np.empty((0, 2)), np.empty((0, 4)), (), (), labels.interline_pairs)
    _, moved, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        op("perspective", matrix=[[1, 0, 320], [0, 1, 0], [0, 0, 1]]),
    )
    assert moved.truncated
    image = image[:239, :319]
    _, moved, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        op("resize", target_interline=7, interpolation="area"),
    )
    np.testing.assert_allclose(moved.interlines, 24 * round(239 * 7 / 24) / 239)


@pytest.mark.parametrize(
    "problem", ["dtype", "channels", "empty", "budget", "box", "pairs", "mask", "point"]
)
def test_invalid_input(problem):
    from dataclasses import replace

    image, labels = fixture()
    params = op("rotation", degrees=0)
    if problem == "dtype":
        image = image.astype(float)
    elif problem == "channels":
        image = image[..., None]
    elif problem == "empty":
        image = image[:0]
    elif problem == "budget":
        params["max_pixels"] = 1
    elif problem == "box":
        labels = replace(labels, boxes=np.array([[3, 3, 1, 1]]))
    elif problem == "pairs":
        labels = replace(labels, interline_pairs=np.zeros((1, 2, 2)))
    elif problem == "mask":
        labels = replace(labels, masks=(image.astype(float),))
    else:
        labels = replace(labels, points=np.array([[np.nan, 1]]))
    with pytest.raises(ValueError):
        apply(image, labels, np.random.default_rng(0), params)


def test_bad_distribution():
    image, labels = fixture()
    with pytest.raises(ValueError):
        run(
            image,
            labels,
            np.random.default_rng(0),
            {"max_pixels": 8_000_000, "operations": [{"op": "rotation", "degrees": {"bad": []}}]},
        )


def test_projective_interline_is_perpendicular():
    image, labels = fixture()
    _, moved, _ = apply(
        image,
        labels,
        np.random.default_rng(0),
        op("perspective", matrix=[[1, 1, 0], [0, 1, 0], [0, 0, 1]]),
    )
    np.testing.assert_allclose(moved.interlines, 24)
    assert np.all(
        np.linalg.norm(moved.interline_pairs[:, 1] - moved.interline_pairs[:, 0], axis=1) > 24
    )


def test_demo_manifest_and_labels(tmp_path, monkeypatch):
    import sys
    from hashlib import sha256

    from PIL import Image

    from training.degrade.demo import main

    monkeypatch.setattr(sys, "argv", ["demo", "--output", str(tmp_path)])
    main()
    report = json.loads((tmp_path / "demo.json").read_text())
    assert [row["target"] for row in report["records"]] == [16, 12, 10, 8, 7]
    for artifact in report["manifest"]:
        path = tmp_path / artifact["path"]
        assert sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        assert path.stat().st_size == artifact["bytes"]
    for record in report["records"]:
        with Image.open(tmp_path / record["file"]) as image:
            assert image.size == tuple(record["applied"]["operations"][-1]["size"])
        with np.load(tmp_path / f"labels-{record['target']}.npz") as labels:
            delta = labels["interline_pairs"][:, 1] - labels["interline_pairs"][:, 0]
            tangent = labels["interline_tangents"]
            distances = np.abs(
                delta[:, 0] * tangent[:, 1] - delta[:, 1] * tangent[:, 0]
            ) / np.linalg.norm(tangent, axis=1)
            np.testing.assert_allclose(distances, record["applied"]["actual_interlines"])
            assert abs(np.median(distances) - record["target"]) < 0.05


def test_grid_measurements(record_property):
    image, labels = fixture()
    errors = []
    specs = [op("rotation", degrees=a) for a in (-8, -1, 0, 1, 8)]
    specs += [
        op("perspective", matrix=[[1, 0.02, 0], [0.01, 1, 0], [p, -p, 1]])
        for p in (-0.0003, 0, 0.0003)
    ]
    specs += [op("resize", target_interline=t, interpolation="area") for t in (16, 12, 10, 8, 7)]
    for params in specs:
        output, moved, _ = apply(image, labels, np.random.default_rng(0), params)
        errors.extend(centroid_errors(output, moved.points))
    record_property("grid_centroid_max_error_px", max(errors))
    record_property("grid_points_measured", len(errors))
    assert max(errors) <= 0.5
