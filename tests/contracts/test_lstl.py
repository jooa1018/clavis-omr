"""CCR-0003 golden texts, invalid sequences, masks, normalization and compatibility."""

import copy
import itertools
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from clavis.contracts import StaffLattice
from clavis.contracts.lstl import (
    LSTLError,
    PrintedItem,
    State,
    advance,
    allowed,
    normalize,
    parse,
    serialize,
    validate_sequence,
)
from clavis.contracts.lstl.automaton import ITEM
from scripts.generate_lstl_vocab import document, generate

ROOT = Path(__file__).resolve().parents[1] / "fixtures/lstl"
GOLDEN = sorted((ROOT / "golden").glob("*.lstl"))
INVALID = json.loads((ROOT / "invalid-sequences.json").read_bytes())
BAD_TEXT = json.loads((ROOT / "invalid-text.json").read_bytes())


@pytest.mark.parametrize("path", GOLDEN, ids=lambda p: p.stem)
def test_golden_roundtrip_and_incremental_masks(path):
    payload = path.read_bytes()
    items = parse(payload)
    assert serialize(items) == payload
    state = State()
    for item in items:
        wire = item.model_dump(by_alias=True, exclude_none=True)
        assert any(Draft202012Validator(mask).is_valid(wire) for mask in allowed(state))
        state = advance(state, item)
    assert state == validate_sequence(items)


@pytest.mark.parametrize("name", INVALID)
def test_invalid_sequences(name):
    with pytest.raises((ValidationError, LSTLError)):
        state = State()
        for raw in INVALID[name]:
            state = advance(state, ITEM.validate_python(raw))


@pytest.mark.parametrize("name", BAD_TEXT)
def test_noncanonical_text(name):
    with pytest.raises((ValidationError, LSTLError)):
        parse(BAD_TEXT[name])


def test_fixture_counts_and_vocabulary(tmp_path, monkeypatch):
    assert len(GOLDEN) >= 20
    assert len(INVALID) >= 30
    generate(check=True)
    vocab = document()
    assert vocab["version"] == "lstl-0.1.1"
    assert vocab["heads"]["join"] == [0, 1]
    assert vocab["heads"]["numbers"] == list(range(1, 16))
    import hashlib

    assert (
        vocab["sha256"]
        == hashlib.sha256(
            json.dumps(vocab["heads"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def model(text):
    if text.startswith("ending "):
        return parse("bar style=regular\n" + text + "\n")[-1]
    return parse(text + "\n")[0]


def printed(text, span):
    return PrintedItem(model(text), span)


def test_disjoint_columns_and_join_membership():
    a, b = parse("note dur=quarter pos=0 head=normal v=1\nrest dur=half v=2 join=1\n")
    source = [
        printed("bar style=final", (30, 31)),
        PrintedItem(a, (10, 12)),
        PrintedItem(b, (11, 14)),
    ]
    result = normalize(source)
    assert [x.item.type for x in result] == ["note", "rest", "bar"]
    assert result[1].item.join == 1
    assert normalize(result) == result
    assert validate_sequence(e.item for e in result).column == 1


def test_initial_overlap_unique_all_permutations():
    columns = [
        printed(text, (0, 2))
        for text in (
            "clef sign=G2",
            "key fifths=0",
            "time beats=4 beatType=4",
            "bar style=repeatStart",
        )
    ]
    for permutation in itertools.permutations(columns):
        assert normalize(permutation) == columns


def test_boundary_overlap_unique_all_permutations():
    note = printed("note dur=quarter pos=0 head=normal v=1", (0, 1))
    columns = [
        printed(text, (10, 12))
        for text in (
            "clef sign=F4",
            "bar style=regular",
            "key fifths=1",
            "time beats=3 beatType=4",
            "bar style=repeatStart",
        )
    ]
    for permutation in itertools.permutations(columns):
        assert normalize([note, *permutation]) == [note, *columns]


@pytest.mark.parametrize(
    "texts,spans",
    [
        (["clef sign=G2", "key fifths=0", "time beats=4 beatType=4"], [(4, 7), (2, 5), (0, 3)]),
        (["bar style=regular", "segno"], [(0, 2), (0, 2)]),
        (["segno", "coda"], [(0, 2), (0, 2)]),
        (["rest dur=quarter v=1", "rest dur=half v=2"], [(0, 2), (0, 2)]),
        (["clef sign=G2", "clef sign=F4"], [(0, 2), (0, 2)]),
    ],
)
def test_ambiguous_or_cyclic_columns(texts, spans):
    with pytest.raises(LSTLError, match="AMBIGUOUS_COLUMN_ORDER"):
        normalize([printed(t, s) for t, s in zip(texts, spans, strict=True)])


def test_ending_after_bar_and_printed_priority():
    bar = printed("bar style=regular", (10, 12))
    ending = printed("ending numbers=[1] mark=start", (10, 12))
    assert normalize([ending, bar]) == [bar, ending]
    # Conventions never override disjoint x order.
    key = printed("key fifths=0", (0, 1))
    clef = printed("clef sign=G2", (2, 3))
    assert normalize([clef, key]) == [key, clef]


def test_ending_immediately_after_regular_boundary_before_changes():
    note = printed("rest dur=half v=1", (0, 1))
    columns = [
        printed(text, (10, 12))
        for text in (
            "bar style=regular",
            "ending numbers=[1] mark=start",
            "key fifths=2",
            "time beats=3 beatType=4",
        )
    ]
    for permutation in itertools.permutations(columns):
        assert normalize([note, *permutation]) == [note, *columns]


@pytest.mark.parametrize("span", [(3, 2), (float("nan"), 2), (0, float("inf"))])
def test_invalid_spans(span):
    with pytest.raises(LSTLError, match="INVALID_SPAN"):
        normalize([printed("segno", span)])


def test_orphan_and_empty():
    note = ITEM.validate_python(
        {
            "type": "note",
            "dur": "quarter",
            "dots": 0,
            "pos": 0,
            "head": "normal",
            "v": 1,
            "chord": 1,
        }
    )
    with pytest.raises(LSTLError, match="ORPHAN_COLUMN_CONTINUATION"):
        normalize([PrintedItem(note, (0, 1))])
    assert normalize([]) == []
    assert parse(serialize([])) == []
    with pytest.raises(LSTLError):
        parse(b"\xff\n")


def test_masks_reject_invalid_next_and_cover_courtesy_grace_voice_limit():
    for raw_sequence in INVALID.values():
        state = State()
        for raw in raw_sequence:
            masks = allowed(state)
            try:
                item = ITEM.validate_python(raw)
                next_state = advance(state, item)
            except (ValidationError, LSTLError):
                # JSON Schema regards 1.0 as an integer; the strict Python model
                # still rejects it. Masks describe JSON values, not Python types.
                if not any(type(value) is float for value in raw.values()):
                    assert not any(Draft202012Validator(mask).is_valid(raw) for mask in masks)
                break
            else:
                state = next_state
    for text in [
        "note dur=eighth pos=1 head=normal v=1 grace=appoggiatura",
        "rest dur=half v=4",
        "bar style=final\nclef sign=F4 courtesy=1",
    ]:
        state = validate_sequence(parse(text + "\n"))
        masks = allowed(state)
        for mask in masks:
            Draft202012Validator.check_schema(mask)


def test_legacy_document_and_join_alternatives():
    original = (ROOT / "legacy-0.1-lattice.json").read_bytes()
    from clavis.contracts import canonical_json

    assert canonical_json(StaffLattice.model_validate_json(original)) == original
    root = ROOT.parent / "contracts/valid/lattice-0.json"
    payload = json.loads(root.read_bytes())
    payload["schema"] = "clavis-ir-0.1"
    legacy = StaffLattice.model_validate(payload)
    assert legacy.schema_version == "clavis-ir-0.1"
    assert legacy.model_dump(by_alias=True)["schema"] == "clavis-ir-0.1"
    payload["schema"] = "clavis-ir-0.1.1"
    payload["hypotheses"] = [
        {
            "rank": 0,
            "logProbMicro": -1,
            "items": [
                {
                    "item": item.model_dump(by_alias=True, exclude_none=True),
                    "attrTopK": {"join": [[1, 8000], [0, 2000]]}
                    if index
                    else {"join": [[0, 10000]]},
                    "spanU": [0, 10],
                    "itemProbBp": 10000,
                    "symbolIds": [],
                }
                for index, item in enumerate(
                    parse("note dur=quarter pos=0 head=normal v=1\nrest dur=half v=2 join=1\n")
                )
            ],
        }
    ]
    current = StaffLattice.model_validate(payload)
    assert current.hypotheses[0].items[1].item.join == 1
    bad = copy.deepcopy(payload)
    bad["hypotheses"][0]["items"][1]["item"]["v"] = 1
    with pytest.raises(ValidationError, match="JOIN_VOICE_ORDER"):
        StaffLattice.model_validate(bad)
    bad = copy.deepcopy(payload)
    bad["hypotheses"][0]["items"][1]["attrTopK"]["join"] = [[0, 10000]]
    with pytest.raises(ValidationError, match="must include"):
        StaffLattice.model_validate(bad)
    bad = copy.deepcopy(payload)
    bad["hypotheses"][0]["items"][1]["attrTopK"]["join"] = [[1, 8000], [2, 2000]]
    with pytest.raises(ValidationError):
        StaffLattice.model_validate(bad)


def test_deterministic_grammar_across_thread_settings():
    import os
    import subprocess
    import sys

    code = """import hashlib
from pathlib import Path
from clavis.contracts.lstl import parse, serialize
root=Path("tests/fixtures/lstl/golden")
print(hashlib.sha256(b"".join(serialize(parse(p.read_bytes()))
    for p in sorted(root.glob("*.lstl")))).hexdigest())
"""
    hashes = []
    for threads in (1, 4):
        for _ in range(3):
            env = dict(
                os.environ,
                OMP_NUM_THREADS=str(threads),
                OPENBLAS_NUM_THREADS=str(threads),
                MKL_NUM_THREADS=str(threads),
                PYTHONPATH="src",
            )
            hashes.append(
                subprocess.check_output(
                    [sys.executable, "-c", code],
                    env=env,
                    cwd=Path(__file__).resolve().parents[2],
                    timeout=30,
                )
            )
    assert len(set(hashes)) == 1
