import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
import xmlschema
import yaml

from training.data.production_audit import audit
from training.data.production_plan import SongPlan
from training.data.production_rhythm import fit
from training.data.production_xml import generate


@pytest.fixture(scope="module")
def inputs():
    profile = yaml.safe_load(
        Path("configs/data/leadgen-production.yaml").read_text(encoding="utf-8")
    )
    notation = yaml.safe_load(
        Path("configs/data/leadgen-notation.yaml").read_text(encoding="utf-8")
    )
    rhythm = yaml.safe_load(Path("configs/data/leadgen-rhythm.yaml").read_text(encoding="utf-8"))
    rhythm.update(mixed_patterns_per_grouping=4, fit_iterations=100)
    target = {"note:eighth:dots=0": 70, "note:quarter:dots=0": 20, "note:16th:dots=0": 10}
    profiles = {meter: fit(meter, target, rhythm) for meter in profile["meter_weights"]}
    return profile, notation, profiles


def validate(xml: str) -> ET.Element:
    root = ET.fromstring(xml)
    divisions = 0
    full = Fraction()
    ties = Counter()
    denoms = {"whole": 1, "half": 2, "quarter": 4, "eighth": 8, "16th": 16, "32nd": 32}
    for measure in root.findall("./part/measure"):
        attributes = measure.find("attributes")
        if attributes is not None:
            divisions = int(attributes.findtext("divisions", str(divisions)))
            full = (
                Fraction(
                    4 * int(attributes.findtext("time/beats")),
                    int(attributes.findtext("time/beat-type")),
                )
                * divisions
            )
        voices = Counter()
        for event in measure.findall("note"):
            if event.find("grace") is not None:
                assert event.find("duration") is None
                continue
            duration = int(event.findtext("duration"))
            voice = event.findtext("voice")
            if event.find("chord") is None:
                voices[voice] += duration
            rest = event.find("rest")
            if rest is None or rest.get("measure") != "yes":
                written = Fraction(4 * divisions, denoms[event.findtext("type")]) * sum(
                    (Fraction(1, 2**dot) for dot in range(1 + len(event.findall("dot")))),
                    Fraction(),
                )
                if event.find("time-modification") is not None:
                    written *= Fraction(
                        int(event.findtext("time-modification/normal-notes")),
                        int(event.findtext("time-modification/actual-notes")),
                    )
                assert duration == written
            for tie in event.findall("tie"):
                identity = (
                    voice,
                    event.findtext("pitch/step"),
                    event.findtext("pitch/alter"),
                    event.findtext("pitch/octave"),
                )
                ties[(identity, tie.get("type"))] += 1
        expected = divisions if measure.get("implicit") == "yes" else full
        assert voices and all(total == expected for total in voices.values())
    assert Counter({k[0]: v for k, v in ties.items() if k[1] == "start"}) == Counter(
        {k[0]: v for k, v in ties.items() if k[1] == "stop"}
    )
    return root


def test_all_meters_and_feature_combinations_are_exact(inputs, schema) -> None:
    profile, notation, profiles = inputs
    for meter in profile["meter_weights"]:
        for pickup in (False, True):
            plan = SongPlan(
                f"train-fixture-{meter.replace('/', '-')}-{pickup}",
                "minor",
                -3,
                meter,
                8,
                ("grace", "key_meter_change", "repeat_volta_navigation")
                + (("pickup",) if pickup else ()),
                (("slash", (1,)), ("two_voice", (2, 3)), ("triplet", (4,))),
            )
            xml = generate(plan, profiles, notation, profile)
            assert xml == generate(plan, profiles, notation, profile)
            schema.validate(xml)
            root = validate(xml)
            assert root.find(".//key/mode").text == "minor"
            assert root.find(".//backup") is not None
            assert root.find(".//time-modification") is not None
            assert root.find(".//notehead").text == "slash"
            notes = root.findall(".//note")
            pitched = [n for n in notes if n.find("pitch") is not None]
            grace = [n for n in pitched if n.find("grace") is not None]
            assert 0.02 <= len(grace) / len(pitched) <= 0.05
            assert root.findall(".//harmony") and root.findall(".//lyric")


def test_optional_denied_generation(inputs) -> None:
    profile, notation, profiles = inputs
    plan = SongPlan("train-minimal", "major", 0, "4/4", 4, (), ())
    validate(generate(plan, profiles, notation, profile))
    with pytest.raises(ValueError):
        generate(plan, profiles, notation, dict(profile, enabled=False))
    with pytest.raises(ValueError):
        generate(replace(plan, seed="wrong"), profiles, notation, profile)


@pytest.fixture(scope="module")
def schema():
    root = Path("src/clavis/export/schemas/musicxml-4.0").resolve()
    return xmlschema.XMLSchema(
        root / "musicxml.xsd",
        locations={
            "http://www.w3.org/XML/1998/namespace": str(root / "xml.xsd"),
            "http://www.w3.org/1999/xlink": str(root / "xlink.xsd"),
        },
        allow="local",
        defuse="always",
        use_fallback=False,
    )


@pytest.mark.parametrize("variant", range(20))
def test_notation_relationships_across_generated_family(inputs, schema, variant):
    profile, notation, profiles = inputs
    settings = {**notation, "tie_song_probability": 1, "chord_head_probability": 0.3}
    plan = SongPlan(
        f"train-notation-family-{variant}",
        "major",
        variant % 15 - 7,
        "4/4",
        8,
        ("grace", "repeat_volta_navigation", "key_meter_change"),
        (("two_voice", (1, 2, 3, 4)),),
    )
    xml = generate(plan, profiles, settings, profile)
    schema.validate(xml)
    root = validate(xml)
    audit(xml)
    for measure in root.findall("./part/measure"):
        assert len(measure.findall("barline[@location='right']")) <= 1
        notes = measure.findall("note")
        for index, event in enumerate(notes):
            if event.find("grace") is not None:
                principal = next(n for n in notes[index + 1 :] if n.find("grace") is None)
                assert event.findtext("voice") == principal.findtext("voice")
            accidental = event.findtext("accidental")
            if accidental is not None:
                assert {"flat-flat": -2, "flat": -1, "natural": 0, "sharp": 1, "double-sharp": 2}[
                    accidental
                ] == int(event.findtext("pitch/alter", "0"))


def test_final_accidental_spelling_accounts_for_tie_replacement():
    from training.data.production_notation import child, note, spell_accidentals, tie_pair
    from training.data.production_rhythm import Value

    part = ET.Element("part")
    a = child(part, "measure")
    child(child(child(a, "attributes"), "key"), "fifths", 0)
    first = note(a, Value("quarter"), ("F", 4, 1), 96)
    b = child(part, "measure")
    second = note(b, Value("quarter"), ("E", 4, 0), 96)
    third = note(b, Value("quarter"), ("F", 4, 0), 96)
    tie_pair(first, second)
    spell_accidentals(part)
    assert first.findtext("accidental") == "sharp"
    assert second.findtext("accidental") == "sharp"
    assert third.findtext("accidental") == "natural"
    before = ET.tostring(part)
    spell_accidentals(part)
    assert ET.tostring(part) == before


def test_simultaneous_conflicting_alters_are_explicit_and_not_carried():
    from training.data.production_notation import child, note, spell_accidentals
    from training.data.production_rhythm import Value

    part = ET.Element("part")
    measure = child(part, "measure")
    first = note(measure, Value("quarter"), ("C", 4, 1), 96)
    child(child(measure, "backup"), "duration", 96)
    second = note(measure, Value("quarter"), ("C", 4, 0), 96, voice=2)
    third = note(measure, Value("quarter"), ("C", 4, 0), 96, voice=2)
    spell_accidentals(part)
    assert first.findtext("accidental") == "sharp"
    assert second.findtext("accidental") == "natural"
    assert third.findtext("accidental") == "natural"
