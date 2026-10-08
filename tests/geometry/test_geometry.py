import dataclasses
from pathlib import Path

import cv2
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clavis.contracts import PageLayout
from clavis.geometry import (
    detect_staves,
    estimate_interline,
    extract_strip,
    load_config,
    processed_to_strip,
    remove_staff_lines,
    strip_to_processed,
)


def staff_image(space=16, count=5, slope=0.0):
    image = np.full((space * 20, space * 45), 255, np.uint8)
    for i in range(count):
        cv2.line(
            image,
            (space * 2, space * (6 + i)),
            (space * 42, round(space * (6 + i) + space * 40 * slope)),
            0,
            1,
        )
    return image


def fixture_staff():
    return PageLayout.model_validate_json(
        Path("tests/fixtures/contracts/valid/layout.json").read_bytes()
    ).staves[0]


@pytest.mark.parametrize("space", [8, 10, 16, 20, 24])
@pytest.mark.parametrize("slope", [-0.017, 0, 0.017])
def test_staff_detection(space, slope):
    image = staff_image(space, slope=slope)
    scales = estimate_interline(image)
    assert abs(scales[0].interline_px - space) <= 1
    result = detect_staves(image)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert abs(candidate.interline_px - space) / space < 0.03
    staff = candidate.as_staff("pg0-sy0-st0", "pg0-sy0")
    strip, mesh = extract_strip(image, staff)
    assert strip.shape[0] == 240 and strip.shape[2] == 2
    points = np.array([[0.0, 96.0], [float(strip.shape[1] - 1), 160.0]])
    np.testing.assert_allclose(
        processed_to_strip(strip_to_processed(points, mesh, 16, 6), mesh, 16, 6), points, atol=1e-9
    )
    assert strip[96, :, 0].mean() < 180


@pytest.mark.parametrize("count", [1, 4, 6, 7])
def test_unsupported_staff_groups(count):
    result = detect_staves(staff_image(count=count))
    assert not result.candidates
    assert "OOD_REGION" in result.diagnostics


@pytest.mark.parametrize("value", [0, 255])
def test_blank(value):
    result = detect_staves(np.full((100, 200), value, np.uint8))
    assert not result.candidates
    assert result.diagnostics == ("CLAVIS_NO_STAFF_FOUND",)


@pytest.mark.parametrize(
    "image", [np.empty((0, 2), np.uint8), np.zeros((2, 2, 3), np.uint8), np.zeros((4, 4), float)]
)
def test_invalid_image(image):
    with pytest.raises(ValueError):
        detect_staves(image)


def test_rule_flags():
    cfg = load_config()
    image = staff_image()
    for rule in ("GEO-RUN", "GEO-GROUP", "GEO-TRACK"):
        disabled = dataclasses.replace(cfg, enabled=cfg.enabled - {rule})
        assert not detect_staves(image, disabled).candidates
    disabled = dataclasses.replace(cfg, enabled=cfg.enabled - {"GEO-REMOVE"})
    np.testing.assert_array_equal(remove_staff_lines(image, 16, 6, 1 / 16, disabled), image)


def test_removal_preserves_crossing_symbols():
    image = staff_image()
    cv2.line(image, (100, 70), (100, 190), 0, 2)
    cv2.ellipse(image, (200, 128), (10, 5), -20, 0, 360, 0, -1)
    before = image.copy()
    removed = remove_staff_lines(image, 16, 6, 1 / 16)
    assert removed[96, 60] == 255
    np.testing.assert_array_equal(removed[70:191, 100], image[70:191, 100])
    np.testing.assert_array_equal(removed[126:131, 198:203], image[126:131, 198:203])
    np.testing.assert_array_equal(image, before)


@given(space=st.integers(8, 28), offset=st.floats(-20, 20, allow_nan=False, allow_infinity=False))
@settings(max_examples=15, deadline=None)
def test_mesh_roundtrip_and_white_border(space, offset):
    staff = fixture_staff().model_copy(deep=True)
    staff.lines = [
        [(0.0, offset + i * space), (80.0, offset + 2 + i * space), (160.0, offset + i * space)]
        for i in range(5)
    ]
    staff.interline_px = float(space)
    page = np.full((200, 161), 255, np.uint8)
    strip, mesh = extract_strip(page, staff)
    assert np.all(strip == 255)
    points = np.array([[0.0, 0.0], [strip.shape[1] / 2, 123.0], [float(strip.shape[1] - 1), 239.0]])
    mapped = strip_to_processed(points, mesh, 16, 6)
    np.testing.assert_allclose(processed_to_strip(mapped, mesh, 16, 6), points, atol=1e-9)
    assert mesh.x[-1] == 160


def test_strip_invalid_geometry():
    image = staff_image()
    staff = fixture_staff().model_copy(deep=True)
    for kwargs in ({"s_star": 0}, {"s_star": float("nan")}, {"margins": (-1, 2)}):
        with pytest.raises(ValueError):
            extract_strip(image, staff, **kwargs)
    staff.ood = "unknown"
    with pytest.raises(ValueError):
        extract_strip(image, staff)
    staff.ood = None
    staff.lines[0] = list(reversed(staff.lines[0]))
    with pytest.raises(ValueError):
        extract_strip(image, staff)
    staff.lines[0] = [(0.0, 1000.0), (100.0, 1000.0)]
    with pytest.raises(ValueError):
        extract_strip(image, staff)


def test_mapping_outside():
    image = staff_image()
    staff = detect_staves(image).candidates[0].as_staff("pg0-sy0-st0", "pg0-sy0")
    _, mesh = extract_strip(image, staff)
    for fn in (strip_to_processed, processed_to_strip):
        with pytest.raises(ValueError):
            fn(np.array([[-1.0, 0.0]]), mesh, 16, 6)
        with pytest.raises(ValueError):
            fn(np.array([[float("nan"), 0.0]]), mesh, 16, 6)
        for s_star, margin in ((float("nan"), 6), (16, float("inf")), (16, -1)):
            with pytest.raises(ValueError):
                fn(np.array([[0.0, 0.0]]), mesh, s_star, margin)
    with pytest.raises(ValueError):
        remove_staff_lines(image, 0, 6, 0.1)


def test_determinism():
    image = staff_image(slope=0.017)
    outputs = []
    previous = cv2.getNumThreads()
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(3):
                result = detect_staves(image)
                staff = result.candidates[0].as_staff("pg0-sy0-st0", "pg0-sy0")
                strip, mesh = extract_strip(image, staff)
                outputs.append((staff.model_dump_json(), mesh.model_dump_json(), strip.tobytes()))
    finally:
        cv2.setNumThreads(previous)
    assert all(o == outputs[0] for o in outputs)


def test_mixed_scales():
    small = staff_image(8)
    large = staff_image(16)
    image = np.full((small.shape[0] + large.shape[0], large.shape[1]), 255, np.uint8)
    image[: small.shape[0], : small.shape[1]] = small
    image[small.shape[0] :] = large
    found = detect_staves(image).candidates
    assert len(found) == 2
    assert sorted(round(c.interline_px) for c in found) == [8, 16]
