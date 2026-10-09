"""CCR-0003 authored geometry families, NOT SYN-Val."""

import itertools

import cv2
import pytest

from clavis.contracts import canonical_json
from clavis.contracts.lstl import parse, serialize, validate_sequence
from clavis.contracts.symbols import Relation, SymbolGraph
from clavis.symbols.reading import draft_reading
from tests.symbols.test_baseline import PRODUCER, graph, run_detection, scene


def column_graph(specs, scale=1):
    """Specs are x, voice, pos, stem group; labels are test-only observations."""
    source = graph()
    heads, stems, relations = [], {}, []
    for i, (x, voice, pos, stem_group) in enumerate(specs):
        head = source.symbols[0].model_copy(deep=True)
        head.symbol_id = f"pg0-sy0-st0-s{i}"
        head.box_strip = (x * scale, (150 - pos * 8) * scale, 20 * scale, 16 * scale)
        head.center_strip = ((x + 10) * scale, (158 - pos * 8) * scale)
        head.pos_top_k = [(pos, 10000)]
        head.attrs.voice_top_k = [(voice, 10000)]
        heads.append(head)
        if stem_group not in stems:
            stem = source.symbols[1].model_copy(deep=True)
            stem.symbol_id = f"pg0-sy0-st0-s{len(specs) + len(stems)}"
            stem.box_strip = ((x + 18) * scale, 80 * scale, 2 * scale, 50 * scale)
            stem.center_strip = ((x + 19) * scale, 105 * scale)
            stems[stem_group] = stem
        relations.append(
            Relation(
                kind="stemOf",
                **{"from": stems[stem_group].symbol_id},
                to=head.symbol_id,
                prob_bp=10000,
            )
        )
    return SymbolGraph.model_validate(
        {**source.model_dump(), "symbols": heads + list(stems.values()), "relations": relations}
    )


@pytest.mark.parametrize("scale", [0.8, 1, 1.25])
@pytest.mark.parametrize("offset", [0, 4, 12, 19])
def test_overlapping_voices_keep_both_join_values(scale, offset):
    # Higher voice deliberately precedes lower voice in x and input order.
    source = column_graph([(40, 2, 2, "a"), (40 + offset, 1, 6, "b")], scale)
    result = draft_reading(source, PRODUCER)
    items = result.finalize().hypotheses[0].items
    assert [i.item.v for i in items] == [1, 2]
    assert items[1].item.join == 1 and items[1].item.chord is None
    assert items[1].attr_top_k["join"] == [(0, 5000), (1, 5000)]
    assert validate_sequence(i.item for i in items).column == 0
    assert parse(serialize([i.item for i in items])) == [i.item for i in items]


@pytest.mark.parametrize("scale", [0.8, 1, 1.25])
@pytest.mark.parametrize("offset", [0, 8, 20, 22])
def test_shared_stem_chord_pos_order_and_evidence(scale, offset):
    source = column_graph([(40, 1, 6, "a"), (40 + offset, 1, 2, "a")], scale)
    items = draft_reading(source, PRODUCER).finalize().hypotheses[0].items
    assert [i.item.pos for i in items] == [2, 6]
    assert items[1].item.chord == 1 and items[1].item.join is None
    assert "join" not in items[1].attr_top_k
    assert set(items[0].symbol_ids) & set(items[1].symbol_ids) == {source.symbols[-1].symbol_id}


def test_disjoint_columns_do_not_invent_join():
    source = column_graph([(100, 2, 2, "a"), (40, 1, 6, "b")])
    items = draft_reading(source, PRODUCER).finalize().hypotheses[0].items
    assert [i.item.v for i in items] == [1, 2]
    assert all(i.item.join is None and "join" not in i.attr_top_k for i in items)
    assert validate_sequence(i.item for i in items).column == 1


@pytest.mark.parametrize(
    "specs",
    [
        [(40, 1, 2, "a"), (40, 1, 6, "b")],  # same voice, competing stems
        [(40, 1, 2, "a"), (40, 2, 6, "a")],  # shared stem, conflicting voice
        [(40, 1, 2, "a"), (40, 1, 2, "a")],  # duplicate pos, no unique order
        [(40, 1, 2, "a"), (55, 2, 6, "b"), (70, 3, 8, "c")],  # overlap chain
    ],
)
def test_conflicting_geometry_is_unresolved(specs):
    result = draft_reading(column_graph(specs), PRODUCER)
    assert not result.lattice.hypotheses
    assert result.unresolved_symbol_ids
    with pytest.raises(ValueError, match="Unresolved"):
        result.finalize()


def test_chord_mismatched_dots_rejected_by_shared_automaton():
    source = column_graph([(40, 1, 2, "a"), (40, 1, 6, "a")])
    source.symbols[1].attrs.dots_top_k = [(1, 10000)]
    result = draft_reading(source, PRODUCER)
    assert not result.lattice.hypotheses
    assert result.unresolved_symbol_ids


def test_rules_off_leave_ambiguous_columns_unresolved():
    joined = column_graph([(40, 1, 2, "a"), (40, 2, 6, "b")])
    chord = column_graph([(40, 1, 2, "a"), (40, 1, 6, "a")])
    assert not draft_reading(joined, PRODUCER, joins_enabled=False).lattice.hypotheses
    assert not draft_reading(chord, PRODUCER, chords_enabled=False).lattice.hypotheses


def test_join_chord_composition_and_determinism(record_property):
    source = column_graph([(40, 2, 8, "b"), (44, 1, 6, "a"), (40, 1, 2, "a")])
    expected = draft_reading(source, PRODUCER).finalize()
    items = expected.hypotheses[0].items
    assert items[1].item.chord == 1 and items[2].item.join == 1
    assert validate_sequence(i.item for i in items).column == 0
    original_threads = cv2.getNumThreads()
    effective_threads = []
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            effective_threads.append(cv2.getNumThreads())
            for order in itertools.permutations(source.symbols[:3]):
                variant = source.model_copy(update={"symbols": list(order) + source.symbols[3:]})
                assert canonical_json(
                    draft_reading(variant, PRODUCER).finalize()
                ) == canonical_json(expected)
    finally:
        cv2.setNumThreads(original_threads)
    record_property("effective_opencv_threads", str(effective_threads))


def test_new_producers_upgrade_legacy_graph_without_mutating_it():
    source = graph()
    result = draft_reading(source, PRODUCER)
    assert source.schema_version == "clavis-ir-0.1"
    assert result.lattice.schema_version == "clavis-ir-0.1.1"
    image, bank = scene()
    assert run_detection(image, bank).schema_version == "clavis-ir-0.1.1"
