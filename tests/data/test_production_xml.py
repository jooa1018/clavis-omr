import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
import yaml

from training.data.production_plan import SongPlan
from training.data.production_rhythm import fit
from training.data.production_xml import generate


@pytest.fixture(scope="module")
def inputs():
    profile = yaml.safe_load(Path("configs/data/leadgen-production.yaml").read_text())
    notation = yaml.safe_load(Path("configs/data/leadgen-notation.yaml").read_text())
    rhythm = yaml.safe_load(Path("configs/data/leadgen-rhythm.yaml").read_text())
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


def test_all_meters_and_feature_combinations_are_exact(inputs) -> None:
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
