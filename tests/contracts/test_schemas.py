"""Committed valid/invalid examples, round trips and contract semantics."""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from clavis.contracts import (
    DOCUMENT_MODELS,
    ContractBundle,
    ElementConfidence,
    EvidenceBundle,
    PageInput,
    PageLayout,
    QualityReport,
    Report,
    ReviewHints,
    RuntimeReport,
    ScoreIR,
    StaffLattice,
    SymbolGraph,
    TextIR,
    canonical_json,
)
from clavis.contracts.canonical import write_json
from clavis.contracts.common import Fraction, TempoValue
from clavis.contracts.outputs import Alternative, ConfidenceElement
from scripts.generate_schemas import generate

ROOT = Path(__file__).resolve().parents[1] / "fixtures/contracts"
MODELS = {m.__name__: m for m in DOCUMENT_MODELS}
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def raw(stem):
    return json.loads((ROOT / "valid" / f"{stem}.json").read_text(encoding="utf-8"))


def bundle():
    return ContractBundle(
        pages=[PageInput.model_validate(raw("page-input"))],
        layouts=[PageLayout.model_validate(raw("layout"))],
        graphs=[SymbolGraph.model_validate(raw(f"symbols-{i}")) for i in range(3)],
        lattices=[StaffLattice.model_validate(raw(f"lattice-{i}")) for i in range(3)],
        texts=[TextIR.model_validate(raw("text"))],
        score=ScoreIR.model_validate(raw("score")),
        evidence=EvidenceBundle.model_validate(raw("evidence")),
        hints=ReviewHints.model_validate(raw("hints")),
        confidence=ElementConfidence.model_validate(raw("confidence")),
        report=Report.model_validate(raw("report")),
    )


@pytest.mark.parametrize("entry", MANIFEST, ids=lambda e: e["path"])
def test_fixture_schema_and_lossless_roundtrip(entry):
    model_type = MODELS[entry["model"]]
    payload = (ROOT / entry["path"]).read_bytes()
    model = model_type.model_validate_json(payload)
    Draft202012Validator(model_type.model_json_schema()).validate(json.loads(payload))
    encoded = canonical_json(model)
    assert encoded == payload
    assert model_type.model_validate_json(encoded) == model
    assert b"\r" not in encoded
    assert encoded.endswith(b"\n")
    assert canonical_json(model_type.model_validate(json.loads(encoded))) == encoded


def test_schema_snapshots_and_generation(tmp_path, monkeypatch):
    generate(check=True)
    root = Path(__file__).resolve().parents[2] / "src/clavis/contracts/schemas"
    assert {p.stem for p in root.glob("*.json")} == set(MODELS)
    for p in root.glob("*.json"):
        Draft202012Validator.check_schema(json.loads(p.read_bytes()))
    # Exercise file writer separately without overwriting committed artifacts.
    output = tmp_path / "quality.json"
    model = QualityReport.model_validate(raw("quality"))
    write_json(output, model)
    assert output.read_bytes() == canonical_json(model)


@pytest.mark.parametrize("path", sorted((ROOT / "invalid").glob("*.json")), ids=lambda p: p.stem)
def test_committed_invalid(path):
    case = json.loads(path.read_bytes())
    with pytest.raises(ValidationError, match=case.get("expectedError")):
        MODELS[case["model"]].model_validate(case["payload"])


def test_three_system_mock_references():
    data = bundle()
    data.validate()
    assert len(data.layouts[0].systems) == 3
    assert len(data.score.measures) == 6
    assert sum(len(h.items) for lattice in data.lattices for h in lattice.hypotheses) > 20
    assert any(
        e.tie.start
        for m in data.score.measures
        for sm in m.staff_measures
        for v in sm.voices
        for e in v.events
    )
    assert len(data.texts[0].items) > 12
    assert all(item.text.strip() for item in data.texts[0].items)
    confidence_ids = {element.id for element in data.confidence.elements}
    for measure in data.score.measures:
        for sm in measure.staff_measures:
            for field in ("clef", "key", "time", "barline_left", "barline_right"):
                if getattr(sm, field) is not None:
                    alias = {"barline_left": "barlineLeft", "barline_right": "barlineRight"}.get(
                        field, field
                    )
                    assert f"{sm.staff_measure_id}-{alias}" in confidence_ids


@pytest.mark.parametrize(
    "mutation",
    [
        "symbol",
        "evidence",
        "text",
        "hint",
        "confidence",
        "count",
        "frame",
        "staff",
        "strip",
        "mask",
    ],
)
def test_bundle_dangling_references(mutation):
    data = bundle()
    if mutation == "symbol":
        data.lattices[0].hypotheses[0].items[0].symbol_ids = ["missing"]
    elif mutation == "evidence":
        data.score.measures[0].staff_measures[0].evidence_ids = ["missing"]
    elif mutation == "text":
        data.score.measures[0].harmonies[0].text_id = "missing"
    elif mutation == "hint":
        data.hints.hints[0].target.id = "missing"
    elif mutation == "confidence":
        data.confidence.elements.pop(0)
    elif mutation == "count":
        data.report.counts.events += 1
    elif mutation == "frame":
        data.evidence.frames[0].image_digest = "f" * 64
    elif mutation == "staff":
        data.score.measures[0].staff_measures[0].staff_id = "pg0-sy2-st0"
    elif mutation == "strip":
        data.graphs[0].symbols[0].box_strip = (9999.0, 0.0, 10.0, 10.0)
    elif mutation == "mask":
        data.layouts[0].non_staff_mask.width += 1
    with pytest.raises(ValueError):
        data.validate()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_rejected(value):
    obj = raw("layout")
    obj["staves"][0]["bbox"][0] = value
    with pytest.raises(ValidationError):
        PageLayout.model_validate(obj)


def test_fixed_precision_and_half_even():
    obj = raw("symbols-0")
    obj["symbols"][0]["centerStrip"] = [12.345, 12.355]
    encoded = canonical_json(SymbolGraph.model_validate(obj))
    assert b'"centerStrip":[12.34,12.36]' in encoded
    quality = raw("quality")
    quality["estimatedStaffSpacePixels"] = 12.3445
    assert b"12.344" in canonical_json(QualityReport.model_validate(quality))
    quality["estimatedStaffSpacePixels"] = 12.3455
    assert b"12.346" in canonical_json(QualityReport.model_validate(quality))
    assert b'"thresholdArtifactDigest":null' in canonical_json(
        ReviewHints.model_validate(raw("hints"))
    )


def test_tempo_and_harmony_amendments():
    assert TempoValue.model_validate({"text": "Moderato"}).per_minute is None
    assert TempoValue.model_validate({"beatUnit": "quarter", "perMinute": {"n": 96, "d": 1}})
    for value in (
        {},
        {"perMinute": {"n": 96, "d": 1}},
        {"beatUnit": "quarter", "perMinute": {"n": 0, "d": 1}},
    ):
        with pytest.raises(ValidationError):
            TempoValue.model_validate(value)
    obj = raw("score")
    del obj["measures"][0]["harmonies"][0]["staffInPart"]
    assert ScoreIR.model_validate(obj).measures[0].harmonies[0].staff_in_part == 1
    runtime = RuntimeReport.model_validate(raw("runtime"))
    assert runtime.platform.python_version == "3.12"


@given(st.integers(min_value=-100000, max_value=100000), st.integers(min_value=1, max_value=100000))
def test_fraction_reduction(n, d):
    import math

    if math.gcd(n, d) == 1:
        value = Fraction.model_validate({"n": n, "d": d})
        assert Fraction.model_validate_json(canonical_json(value)) == value
    else:
        with pytest.raises(ValidationError):
            Fraction.model_validate({"n": n, "d": d})


@pytest.mark.parametrize("value", ["가", "e\u0301"])
def test_nfc_rejected(value):
    with pytest.raises(ValidationError):
        TempoValue.model_validate({"text": value})


@pytest.mark.parametrize(
    "patch",
    [
        {"kind": "pitch", "pitch": {"step": "D", "alter": 1, "octave": 4}},
        {"kind": "duration", "duration": {"n": 1, "d": 2}},
        {"kind": "accidental", "alter": -1},
        {"kind": "tie", "tieStart": True, "tieStop": False},
        {
            "kind": "chord",
            "parseResult": {"normalized": "N.C.", "kind": "none", "kindText": "", "degrees": []},
        },
        {"kind": "timeSignature", "value": {"beats": 6, "beatType": 8}},
        {"kind": "keySignature", "value": {"fifths": 2}},
        {"kind": "replaceSourceText", "text": "빛"},
        {"kind": "insertBarline"},
        {"kind": "deleteBarline"},
    ],
)
def test_typed_patches(patch):
    payload = {"alternativeId": "a0", "labelKo": "검토", "patch": patch, "confidenceBp": 7500}
    model = Alternative.model_validate(payload)
    assert Alternative.model_validate_json(canonical_json(model)) == model
    payload["patch"]["unexpected"] = 1
    with pytest.raises(ValidationError):
        Alternative.model_validate(payload)


def test_replace_event_patch():
    event = raw("score")["measures"][0]["staffMeasures"][0]["voices"][0]["events"][0]
    assert Alternative.model_validate(
        {
            "alternativeId": "a0",
            "labelKo": "검토",
            "patch": {"kind": "replaceEvent", "event": event},
            "confidenceBp": 7000,
        }
    )


@pytest.mark.parametrize("path", ["../key", "attributes[0]/key[1]", "/key[1]", "key[@id='x']"])
def test_confidence_path_restricted(path):
    with pytest.raises(ValidationError):
        ConfidenceElement.model_validate(
            {
                "id": "key0",
                "kind": "key",
                "confidenceBp": 9500,
                "flagged": False,
                "parentId": "P1-m0",
                "path": path,
            }
        )


def test_nested_objects_reject_unknown_fields():
    # Every observed nested wire object must carry its own extra=forbid boundary.
    from pydantic import BaseModel

    def visit(value):
        if isinstance(value, BaseModel):
            payload = value.model_dump(by_alias=True)
            payload["unsupportedField"] = True
            with pytest.raises(ValidationError):
                type(value).model_validate(payload)
            for key in type(value).model_fields:
                visit(getattr(value, key))
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)

    for entry in MANIFEST:
        visit(MODELS[entry["model"]].model_validate_json((ROOT / entry["path"]).read_bytes()))


def test_serialization_repeats_across_thread_settings():
    import hashlib
    import os
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    expected = hashlib.sha256(
        b"".join((ROOT / e["path"]).read_bytes() for e in MANIFEST)
    ).hexdigest()
    code = """import hashlib,json
from pathlib import Path
from clavis.contracts import DOCUMENT_MODELS,canonical_json
root=Path("tests/fixtures/contracts")
models={m.__name__:m for m in DOCUMENT_MODELS}
manifest=json.loads((root/"manifest.json").read_text())
payloads = [canonical_json(models[e["model"]].model_validate_json(
    (root/e["path"]).read_bytes())) for e in manifest]
print(hashlib.sha256(b"".join(payloads)).hexdigest())
"""
    for threads in (1, 4):
        env = {
            **os.environ,
            "PYTHONPATH": "src",
            "OMP_NUM_THREADS": str(threads),
            "OPENBLAS_NUM_THREADS": str(threads),
            "MKL_NUM_THREADS": str(threads),
        }
        for _ in range(3):
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            assert result.stdout.strip() == expected


@pytest.mark.parametrize(
    "stem,model,path,value",
    [
        ("page-input", PageInput, ["transforms", 0, "matrix", 8], 2.0),
        ("score", ScoreIR, ["measures", 0, "harmonies", 0, "root"], None),
        ("score", ScoreIR, ["measures", 4, "harmonies", 0, "root"], {"step": "C", "alter": 0}),
        ("score", ScoreIR, ["parts", 0, "staffSlots", 0, "staffInPart"], 2),
        (
            "score",
            ScoreIR,
            ["measures", 0, "staffMeasures", 0, "voices", 0, "events", 0, "onset"],
            {"n": -1, "d": 1},
        ),
        ("layout", PageLayout, ["readingOrder"], ["pg0-sy0"]),
        ("symbols-0", SymbolGraph, ["id"], "pg0-sy9-st0"),
        ("lattice-0", StaffLattice, ["hypotheses", 0, "items", 0, "spanU"], [4.0, 2.0]),
        (
            "lattice-0",
            StaffLattice,
            ["hypotheses", 0, "items", 0, "attrTopK"],
            {"type": [["bar", 8000]]},
        ),
        (
            "text",
            TextIR,
            ["items", 0, "chord"],
            {"normalized": "N.C.", "kind": "none", "kindText": "", "degrees": []},
        ),
    ],
)
def test_structural_invalid_fields(stem, model, path, value):
    obj = raw(stem)
    target = obj
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        model.model_validate(obj)


def test_schema_generator_detects_drift(tmp_path, monkeypatch):
    import scripts.generate_schemas as generator

    contracts = tmp_path / "src/clavis/contracts"
    contracts.mkdir(parents=True)
    monkeypatch.setattr(generator, "__file__", str(tmp_path / "scripts/generate_schemas.py"))
    generator.generate()
    generator.generate(check=True)
    (contracts / "schemas/PageInput.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="stale schema"):
        generator.generate(check=True)


def test_hint_target_kind():
    data = bundle()
    data.hints.hints[0].target.kind = "harmony"
    with pytest.raises(ValueError, match="hint target kind"):
        data.validate()
