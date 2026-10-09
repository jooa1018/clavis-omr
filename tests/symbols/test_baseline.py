"""Authored component probes, not SYN-Val or a music accuracy benchmark."""

import hashlib
import json
from pathlib import Path

import cv2
import jsonschema
import numpy as np
import pytest

from clavis.contracts import canonical_json
from clavis.contracts.common import Producer
from clavis.contracts.symbols import StaffLattice, SymbolGraph
from clavis.symbols.detection import Settings, Template, detect
from clavis.symbols.reading import draft_reading
from clavis.symbols.templates import template_responses

ROOT = Path(__file__).resolve().parents[2]
PRODUCER = Producer(name="symbols-component-test", version="0.1", sha256="0" * 64)


def settings(**updates):
    initial = Settings.load(ROOT / "configs/symbols/constants.yaml")
    return Settings.model_validate({**initial.model_dump(), **updates})


def scene(scale=1):
    yy, xx = np.mgrid[:16, :20]
    head = np.where(((xx - 9.5) / 9) ** 2 + ((yy - 7.5) / 6) ** 2 <= 1, 0, 255).astype(np.uint8)
    original = np.full((240, 200), 255, np.uint8)
    original[120:136, 40:60] = head
    original[80:130, 58:60] = 0
    original[96:161, 180:182] = 0

    def resize(a):
        return cv2.resize(a, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

    return resize(original), [Template("noteheadFilled", resize(head))]


def run_detection(image, bank, **kwargs):
    return detect(
        image,
        image,
        staff_id="pg0-sy0-st0",
        staff_space=kwargs.pop("staff_space", 16),
        v_top=kwargs.pop("v_top", 96),
        templates=bank,
        settings=settings(),
        producer=PRODUCER,
        **kwargs,
    )


def graph():
    return SymbolGraph.model_validate(
        {
            "schema": "clavis-ir-0.1",
            "id": "pg0-sy0-st0",
            "stripId": "pg0-sy0-st0",
            "producer": PRODUCER,
            "rejectedCandidates": [],
            "symbols": [
                {
                    "symbolId": "pg0-sy0-st0-s0",
                    "sources": ["template"],
                    "classTopK": [["noteheadFilled", 10000]],
                    "boxStrip": [40, 120, 20, 16],
                    "centerStrip": [50, 128],
                    "posTopK": [[4, 6000], [5, 4000]],
                    "attrs": {"dotsTopK": [[0, 7000], [1, 3000]], "voiceTopK": [[1, 10000]]},
                },
                {
                    "symbolId": "pg0-sy0-st0-s1",
                    "sources": ["vline"],
                    "classTopK": [["stem", 10000]],
                    "boxStrip": [58, 80, 2, 50],
                    "centerStrip": [59, 105],
                    "attrs": {
                        "beamCountTopK": [[0, 6000], [1, 3000], [2, 1000]],
                        "flagCountTopK": [[0, 10000]],
                    },
                },
                {
                    "symbolId": "pg0-sy0-st0-s2",
                    "sources": ["vline"],
                    "classTopK": [["stem", 10000]],
                    "boxStrip": [38, 125, 2, 50],
                    "centerStrip": [39, 150],
                    "attrs": {
                        "beamCountTopK": [[1, 7000], [2, 3000]],
                        "flagCountTopK": [[0, 10000]],
                    },
                },
            ],
            "relations": [
                {
                    "kind": "stemOf",
                    "from": "pg0-sy0-st0-s1",
                    "to": "pg0-sy0-st0-s0",
                    "probBp": 6000,
                },
                {
                    "kind": "stemOf",
                    "from": "pg0-sy0-st0-s2",
                    "to": "pg0-sy0-st0-s0",
                    "probBp": 4000,
                },
            ],
        }
    )


@pytest.mark.parametrize("scale", [0.8, 1, 1.25])
def test_detection_geometry_and_evidence(scale):
    image, bank = scene(scale)
    result = run_detection(image, bank, staff_space=16 * scale, v_top=96 * scale)
    assert any(s.class_top_k[0][0] == "noteheadFilled" for s in result.symbols)
    assert any(s.class_top_k[0][0] == "barline" for s in result.symbols)
    assert result.relations
    heads = [s for s in result.symbols if s.pos_top_k]
    assert any(s.pos_top_k[0][0] == 4 for s in heads)
    assert all(s.attrs is None for s in result.symbols)  # No invented beam/dot observations.
    jsonschema.validate(json.loads(canonical_json(result)), SymbolGraph.model_json_schema())


def test_determinism_threads_and_input_immutability():
    image, bank = scene()
    before = image.copy()
    previous = cv2.getNumThreads()
    try:
        outputs = []
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(3):
                outputs.append(
                    hashlib.sha256(canonical_json(run_detection(image, bank))).hexdigest()
                )
        assert len(set(outputs)) == 1
        np.testing.assert_array_equal(image, before)
    finally:
        cv2.setNumThreads(previous)


def test_channels_are_separate_and_scores_are_not_probabilities():
    image, bank = scene()
    blank = np.full_like(image, 255)
    original, removed = template_responses(image, blank, [bank[0].pixels])[0]
    assert original.max() > 9000
    assert removed.max() == 0
    assert template_responses(image, blank, [], enabled=False) == []


@pytest.mark.parametrize(
    "kind", ["dtype", "shape", "empty", "constant", "oversized", "template-dtype"]
)
def test_invalid_images(kind):
    image, bank = scene()
    template = bank[0].pixels
    other = image
    if kind == "dtype":
        image = image.astype(float)
    elif kind == "shape":
        other = other[:-1]
    elif kind == "empty":
        image = other = np.empty((0, 0), np.uint8)
    elif kind == "constant":
        template = np.zeros((2, 2), np.uint8)
    elif kind == "oversized":
        template = np.zeros((300, 300), np.uint8)
    else:
        template = template.astype(float)
    with pytest.raises(ValueError):
        template_responses(image, other, [template])


@pytest.mark.parametrize(
    "rule", ["SYM-TEMPLATE-001", "SYM-VLINE-001", "SYM-POS-001", "SYM-REL-001"]
)
def test_detector_ablation_switch(rule):
    image, bank = scene()
    result = run_detection(image, bank, disabled=frozenset([rule]))
    if rule == "SYM-TEMPLATE-001":
        assert not any("template" in s.sources for s in result.symbols)
    elif rule == "SYM-VLINE-001":
        assert not any("vline" in s.sources for s in result.symbols)
    elif rule == "SYM-POS-001":
        assert all(s.pos_top_k is None for s in result.symbols)
    else:
        assert result.relations == []


def test_rejected_candidates_and_empty_page():
    image, bank = scene()
    config = settings(accept_bp=10000)
    result = detect(
        image,
        image,
        staff_id="pg0-sy0-st0",
        staff_space=16,
        v_top=96,
        templates=bank,
        settings=config,
        producer=PRODUCER,
    )
    assert result.rejected_candidates
    blank = np.full_like(image, 255)
    assert run_detection(blank, bank).symbols == []


@pytest.mark.parametrize(
    "change",
    [
        {"pos_sigma_steps": 0},
        {"candidate_bp": 9999},
        {"line_class_bp": 9999},
        {"nms_spaces": float("nan")},
    ],
)
def test_invalid_config(change):
    with pytest.raises(ValueError):
        settings(**change)


def test_reading_preserves_attribute_and_relation_alternatives():
    result = draft_reading(graph(), PRODUCER)
    assert len(result.lattice.hypotheses) == 2
    items = [h.items[0] for h in result.lattice.hypotheses]
    assert {tuple(i.symbol_ids) for i in items} == {
        ("pg0-sy0-st0-s0", "pg0-sy0-st0-s1"),
        ("pg0-sy0-st0-s0", "pg0-sy0-st0-s2"),
    }
    assert all(i.attr_top_k["pos"] == [(4, 6000), (5, 4000)] for i in items)
    assert all(i.attr_top_k["dots"] == [(0, 7000), (1, 3000)] for i in items)
    assert any({v for v, _ in i.attr_top_k["dur"]} == {"quarter", "eighth", "16th"} for i in items)
    assert all(i.span_u in ((40, 60), (38, 60)) for i in items)
    assert len({canonical_json(draft_reading(graph(), PRODUCER).lattice) for _ in range(3)}) == 1
    jsonschema.validate(
        json.loads(canonical_json(result.lattice)), StaffLattice.model_json_schema()
    )
    assert result.finalize() == result.lattice


@pytest.mark.parametrize(
    "missing", ["pos_top_k", "attrs", "dots_top_k", "voice_top_k", "flag_count_top_k"]
)
def test_missing_attributes_are_unknown(missing):
    source = graph()
    if missing in ("pos_top_k", "attrs"):
        setattr(source.symbols[0], missing, None)
    elif missing == "flag_count_top_k":
        for symbol in source.symbols[1:]:
            symbol.attrs.flag_count_top_k = None
    else:
        setattr(source.symbols[0].attrs, missing, None)
    result = draft_reading(source, PRODUCER)
    assert result.lattice.hypotheses[0].items == []
    assert result.unresolved_symbol_ids
    with pytest.raises(ValueError, match="Unresolved"):
        result.finalize()


@pytest.mark.parametrize("fixture", [0, 1, 2])
def test_contract_graphs_without_ground_truth_injection(fixture):
    source = SymbolGraph.model_validate_json(
        (ROOT / f"tests/fixtures/contracts/valid/symbols-{fixture}.json").read_bytes()
    )
    result = draft_reading(source, PRODUCER)
    assert result.unresolved_symbol_ids  # This component does not claim complete reading.
    assert StaffLattice.model_validate_json(canonical_json(result.lattice)) == result.lattice


def test_whole_hollow_class_uncertainty_and_rule_switches():
    source = graph()
    source.symbols[0].class_top_k = [("noteheadHollow", 5000), ("noteheadWhole", 5000)]
    result = draft_reading(source, PRODUCER)
    assert {h.items[0].item.dur for h in result.lattice.hypotheses} == {"whole", "half"}
    assert draft_reading(source, PRODUCER, enabled=False).lattice.hypotheses[0].items == []
    assert (
        draft_reading(source, PRODUCER, durations_enabled=False).lattice.hypotheses[0].items == []
    )


def test_unsupported_counts_fail_closed_and_geometry_rejected():
    source = graph()
    for symbol in source.symbols[1:]:
        symbol.attrs.beam_count_top_k = [(9, 10000)]
    assert draft_reading(source, PRODUCER).lattice.hypotheses[0].items == []
    image, bank = scene()
    with pytest.raises(ValueError):
        run_detection(image, bank, staff_space=0)


def test_weak_connection_is_not_crowded_out_by_attribute_combinations():
    source = graph()
    source.relations[0].prob_bp = 9999
    source.relations[1].prob_bp = 1
    result = draft_reading(source, PRODUCER)
    assert len(result.lattice.hypotheses) == 2
    assert any("pg0-sy0-st0-s2" in h.items[0].symbol_ids for h in result.lattice.hypotheses)
    assert all(len(h.items[0].attr_top_k["dots"]) == 2 for h in result.lattice.hypotheses)


@pytest.mark.parametrize("notes", [3, 4])
def test_eight_hypothesis_cap_applies_to_relationship_paths(notes):
    source = graph()
    symbols, relations = [], []
    for note in range(notes):
        part = graph()
        rename = {s.symbol_id: f"pg0-sy0-st0-s{note * 3 + i}" for i, s in enumerate(part.symbols)}
        for symbol in part.symbols:
            symbol.symbol_id = rename[symbol.symbol_id]
            x, y, w, h = symbol.box_strip
            symbol.box_strip = (x + note * 100, y, w, h)
            u, v = symbol.center_strip
            symbol.center_strip = (u + note * 100, v)
        for relation in part.relations:
            relation.from_id, relation.to = rename[relation.from_id], rename[relation.to]
        symbols.extend(part.symbols)
        relations.extend(part.relations)
    source.symbols, source.relations = symbols, relations
    result = draft_reading(source, PRODUCER)
    assert len(result.lattice.hypotheses) == 8
    assert all(len(h.items) == notes for h in result.lattice.hypotheses)
