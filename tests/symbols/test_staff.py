"""W5/W6 public boundary, not recognition accuracy or SYN-Val."""

import hashlib
import json

import cv2
import jsonschema
import numpy as np
import pytest

from clavis.contracts import canonical_json
from clavis.contracts.symbols import StaffLattice, SymbolGraph
from clavis.geometry import StaffCandidate, extract_strip, load_config
from clavis.symbols.detection import detect
from clavis.symbols.reading import draft_reading
from clavis.symbols.staff import read_staff
from tests.symbols.test_baseline import PRODUCER, ROOT, scene, settings
from training.models.symbols.jitter import jitter_staff, sample_row


def staff_scene(scale=1):
    page, bank = scene()
    for y in range(96, 161, 16):
        page[y, :] = 0
    lines = np.array([[[0, y], [199, y]] for y in range(96, 161, 16)], dtype=float) * scale
    staff = StaffCandidate(lines, 16 * scale, scale, 10000).as_staff("pg0-sy0-st0", "pg0-sy0")
    return cv2.resize(page, None, fx=scale, fy=scale), bank, staff


@pytest.mark.parametrize("scale", [0.8, 1, 1.25])
def test_shared_strip_channels_and_unresolved_lattice(scale):
    page, bank, staff = staff_scene(scale)
    result = read_staff(page, staff, templates=bank, settings=settings(), producer=PRODUCER)
    expected, mesh = extract_strip(page, staff)
    np.testing.assert_array_equal(result.channels, expected)
    assert result.mesh == mesh
    assert np.any(result.channels[:, :, 0] != result.channels[:, :, 1])
    assert any(s.pos_top_k for s in result.graph.symbols)
    assert all(s.attrs is None for s in result.graph.symbols)
    assert result.reading.unresolved_symbol_ids
    assert result.reading.lattice.hypotheses[0].items == []
    for value, schema in ((result.graph, SymbolGraph), (result.reading.lattice, StaffLattice)):
        jsonschema.validate(json.loads(canonical_json(value)), schema.model_json_schema())
    with pytest.raises(ValueError, match="Unresolved"):
        result.reading.finalize()


def test_shared_strip_determinism_and_input_immutability():
    page, bank, staff = staff_scene()
    before, wire = page.copy(), canonical_json(staff)
    previous = cv2.getNumThreads()
    outputs = []
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(3):
                result = read_staff(
                    page,
                    staff,
                    templates=bank,
                    settings=settings(),
                    producer=PRODUCER,
                    geometry_config=load_config(),
                )
                outputs.append(
                    hashlib.sha256(
                        result.channels.tobytes()
                        + canonical_json(result.mesh)
                        + canonical_json(result.graph)
                        + canonical_json(result.reading.lattice)
                    ).hexdigest()
                )
        assert len(set(outputs)) == 1
        np.testing.assert_array_equal(before, page)
        assert canonical_json(staff) == wire
    finally:
        cv2.setNumThreads(previous)


def test_unsupported_geometry_is_not_silently_read():
    page, bank, staff = staff_scene()
    staff.ood = True
    with pytest.raises(ValueError, match="five-line"):
        read_staff(page, staff, templates=bank, settings=settings(), producer=PRODUCER)


def test_eight_pixel_staff_keeps_original_only_evidence():
    page, bank, staff = staff_scene(0.5)
    config = load_config(ROOT / "configs/geometry")
    result = read_staff(
        page,
        staff,
        templates=bank,
        settings=settings(),
        producer=PRODUCER,
        geometry_config=config,
    )
    original = result.channels[:, :, 0]
    graph = detect(
        original,
        np.full_like(original, 255),
        staff_id=staff.staff_id,
        staff_space=config["strip.s_star"],
        v_top=config["strip.above"] * config["strip.s_star"],
        templates=bank,
        settings=settings(),
        producer=PRODUCER,
    )
    assert staff.interline_px == 8
    assert original.shape[0] == 240
    assert any(s.class_top_k[0][0] == "noteheadFilled" for s in graph.symbols)
    assert any("vline" in s.sources for s in graph.symbols)
    assert all(s.attrs is None for s in graph.symbols)
    reading = draft_reading(graph, PRODUCER)
    assert reading.unresolved_symbol_ids
    assert reading.lattice.hypotheses[0].items == []
    with pytest.raises(ValueError, match="Unresolved"):
        reading.finalize()


def test_joint_jitter_preserves_center_offsets_without_double_spacing_error():
    _, _, staff = staff_scene()
    # Each center offset already incorporates spacing error, as W5 defines it.
    row = {
        "line_y_spaces": [0, 0.1, 0.2, 0.3, 0.4],
        "interline_relative": 0.1,
        "left_spaces": -1,
        "right_spaces": 1,
        "slope_dy_dx": 0.01,
    }
    result = jitter_staff(staff, row)
    for index, line in enumerate(result.lines):
        array = np.asarray(line)
        assert np.interp(99.5, array[:, 0], array[:, 1]) == pytest.approx(96 + index * 17.6)
    assert result.interline_px == pytest.approx(17.6)
    assert result.lines[0][0][0] == -16
    assert result.lines[0][-1][0] == 215
    # Different line knot counts remain valid at the public Staff boundary.
    staff.lines[2].insert(1, (99.5, 128))
    assert jitter_staff(staff, row).lines[0][1][0] == 0


def test_synthetic_jitter_seed_and_slice(tmp_path):
    path = ROOT / "configs/geometry/jitter.yaml"
    row = sample_row(path, 16, np.random.default_rng(6))
    assert row == sample_row(path, 16, np.random.default_rng(6))
    assert row in json.loads(path.read_text())["errors"]
    with pytest.raises(ValueError, match="unavailable"):
        sample_row(path, 3, np.random.default_rng(6))
    invalid = tmp_path / "jitter.json"
    invalid.write_text(json.dumps({"source": "unapproved", "errors": []}))
    with pytest.raises(ValueError, match="synthetic-v0"):
        sample_row(invalid, 16, np.random.default_rng(6))


@pytest.mark.parametrize(
    "change",
    [
        {"line_y_spaces": [0]},
        {"interline_relative": -1},
        {"slope_dy_dx": float("nan")},
        {"left_spaces": 30},
    ],
)
def test_invalid_jitter_fails_closed(change):
    _, _, staff = staff_scene()
    row = {
        "line_y_spaces": [0] * 5,
        "interline_relative": 0,
        "left_spaces": 0,
        "right_spaces": 0,
        "slope_dy_dx": 0,
        **change,
    }
    with pytest.raises(ValueError):
        jitter_staff(staff, row)
