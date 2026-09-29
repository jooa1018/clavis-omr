"""PR #4 conditional approval: representation and candidate invariants."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from clavis.contracts import Event, ScoreIR, SymbolGraph, canonical_json
from clavis.contracts.outputs import BoundingBox, DurationPatch
from clavis.contracts.symbols import LatticeItem, SymbolAttributes
from clavis.contracts.tokens import LSTLItem, NoteItem

ROOT = Path(__file__).resolve().parents[1] / "fixtures/contracts"


def raw(stem):
    return json.loads((ROOT / "valid" / f"{stem}.json").read_bytes())


NOTE = {"type": "note", "dur": "quarter", "dots": 0, "pos": 0, "head": "normal", "v": 1}
DEFAULTS = {
    "acc": "none",
    "accParen": False,
    "tie": "none",
    "slur": "none",
    "chord": 0,
    "grace": "none",
    "tup3": "none",
    "fermata": False,
    "stem": "none",
    "beam": "none",
}


def test_first_system_order_and_matching_bar_evidence():
    lattice = raw("lattice-0")
    items = lattice["hypotheses"][0]["items"]
    assert [x["item"]["type"] for x in items[:3]] == ["clef", "time", "bar"]
    assert items[2]["item"]["style"] == "repeatStart"
    symbols = {s["symbolId"]: s for s in raw("symbols-0")["symbols"]}
    assert items[2]["spanU"][0] == symbols[items[2]["symbolIds"][0]]["boxStrip"][0]
    assert (
        raw("layout")["systems"][0]["barlines"][0]["uByStaff"]["pg0-sy0-st0"]
        == items[2]["spanU"][0]
    )


@pytest.mark.parametrize("field,default", DEFAULTS.items())
def test_optional_default_rejected_and_writer_omits(field, default):
    with pytest.raises(ValidationError, match="default must be omitted"):
        NoteItem.model_validate({**NOTE, field: default})
    # The writer also guarantees omission if trusted in-process construction bypasses validation.
    model = NoteItem.model_validate(NOTE)
    name = next(
        name for name, info in NoteItem.model_fields.items() if (info.alias or name) == field
    )
    encoded = json.loads(canonical_json(model.model_copy(update={name: default})))
    assert field not in encoded
    assert encoded["dots"] == 0
    assert encoded["pos"] == 0


@pytest.mark.parametrize(
    "item,field,value",
    [
        ({"type": "clef", "sign": "G2"}, "courtesy", False),
        ({"type": "key", "fifths": 0}, "cancel", 0),
        ({"type": "rest", "dur": "quarter", "dots": 0, "v": 1}, "measureRest", False),
    ],
)
def test_other_token_default_omission(item, field, value):
    adapter = TypeAdapter(LSTLItem)
    with pytest.raises(ValidationError):
        adapter.validate_python({**item, field: value})
    model = adapter.validate_python(item)
    name = next(
        name for name, info in type(model).model_fields.items() if (info.alias or name) == field
    )
    assert field not in json.loads(canonical_json(model.model_copy(update={name: value})))


def test_event_and_empty_attrs_writer_preserves_required_fields():
    data = raw("score")["measures"][0]["staffMeasures"][0]["voices"][0]["events"][0]
    event = Event.model_validate(data).model_copy(
        update={"grace": "none", "accidental_visible": "none"}
    )
    result = json.loads(canonical_json(event))
    assert "grace" not in result and "accidentalVisible" not in result
    assert result["tie"] == {"start": False, "stop": False}
    assert result["chordWithPrev"] is False
    assert result["notated"]["dots"] == data["notated"]["dots"]
    graph = SymbolGraph.model_validate(raw("symbols-0"))
    graph.symbols[0].attrs = SymbolAttributes()
    assert "attrs" not in json.loads(canonical_json(graph))["symbols"][0]
    assert SymbolGraph.model_validate_json(canonical_json(graph))


@pytest.mark.parametrize(
    "field,candidates",
    [
        ("acc", [["none", 6000], ["sharp", 4000]]),
        ("chord", [[0, 6000], [1, 4000]]),
        ("fermata", [[False, 6000], [True, 4000]]),
        ("pos", [[-1, 5000], [0, 5000]]),
    ],
)
def test_attr_candidates_allow_defaults_and_natural_ties(field, candidates):
    item = LatticeItem.model_validate(
        {
            "item": NOTE,
            "attrTopK": {field: candidates},
            "spanU": [0.0, 10.0],
            "itemProbBp": 9000,
            "symbolIds": [],
        }
    )
    assert json.loads(canonical_json(item))["attrTopK"][field] == candidates


@pytest.mark.parametrize(
    "field,values",
    [
        ("voiceTopK", [[1, 5000], [2, 5000]]),
        ("beamCountTopK", [[0, 5000], [2, 5000]]),
        ("flagCountTopK", [[0, 5000], [1, 5000]]),
        ("dotsTopK", [[0, 5000], [2, 5000]]),
        ("stemDir", [["down", 5000], ["up", 5000]]),
        ("headType", [["normal", 5000], ["x", 5000]]),
    ],
)
def test_each_attribute_distribution_validates_order_and_duplicates(field, values):
    assert SymbolAttributes.model_validate({field: values})
    for invalid in ([], list(reversed(values)), [values[0], values[0]], values * 2):
        with pytest.raises(ValidationError):
            SymbolAttributes.model_validate({field: invalid})


def test_pos_top_level_and_voice_distribution():
    graph = raw("symbols-0")
    graph["symbols"][0]["posTopK"] = [[-1, 5000], [0, 5000]]
    graph["symbols"][0]["attrs"] = {"voiceTopK": [[1, 7000], [2, 3000]]}
    model = SymbolGraph.model_validate(graph)
    assert model.symbols[0].attrs.voice_top_k == [(1, 7000), (2, 3000)]


@pytest.mark.parametrize("grace", ["acciaccatura", "appoggiatura"])
def test_zero_duration_grace_only(grace):
    data = raw("score")["measures"][0]["staffMeasures"][0]["voices"][0]["events"][0]
    assert Event.model_validate({**data, "grace": grace, "duration": {"n": 0, "d": 1}})
    assert DurationPatch.model_validate({"kind": "duration", "duration": {"n": 1, "d": 4}})


def test_measure_index_is_per_part_and_respects_list_order():
    data = raw("score")
    second = json.loads(json.dumps(data).replace("P1", "P2"))
    data["parts"] += second["parts"]
    data["measures"] = [
        m for pair in zip(data["measures"], second["measures"], strict=True) for m in pair
    ]
    assert ScoreIR.model_validate(data)
    invalid = copy.deepcopy(data)
    invalid["measures"][1]["index"] = 1
    with pytest.raises(ValidationError, match="consecutive per part"):
        ScoreIR.model_validate(invalid)


def test_minimum_external_box_and_distinct_target_validation():
    assert BoundingBox.model_validate(
        {"frameId": "frame0", "xMu": 0, "yMu": 0, "widthMu": 1, "heightMu": 1}
    )


def test_printed_columns_do_not_override_voice_order_inside_musical_column():
    from clavis.contracts.symbols import Hypothesis

    def item(u, v):
        return {
            "item": {**NOTE, "v": v},
            "attrTopK": {},
            "spanU": [u, u + 8],
            "itemProbBp": 9000,
            "symbolIds": [],
        }

    assert Hypothesis.model_validate(
        {"rank": 0, "logProbMicro": 0, "items": [item(20.0, 1), item(0.0, 2)]}
    )


def test_every_approval_condition_has_a_negative_fixture():
    conditions = {
        json.loads(p.read_bytes())["condition"] for p in (ROOT / "invalid").glob("condition-*.json")
    }
    assert conditions == set(range(1, 9))
