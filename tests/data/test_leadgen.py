import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from training.data.leadgen import Key, Rhythm, Settings, generate, main, rhythm_plan
from training.data.smoke import CONFIG, ROOT


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        yaml.safe_load((ROOT / "configs/data/leadgen-development.yaml").read_text(encoding="utf-8"))
    )


def validate_music(xml: str) -> None:
    root = ET.fromstring(xml)
    divisions = int(root.findtext(".//divisions"))
    meter = Fraction(4 * int(root.findtext(".//beats")), int(root.findtext(".//beat-type")))
    units = {
        "whole": 4,
        "half": 2,
        "quarter": 1,
        "eighth": Fraction(1, 2),
        "16th": Fraction(1, 4),
        "32nd": Fraction(1, 8),
    }
    for measure in root.findall(".//measure"):
        total = Fraction(0)
        for note in measure.findall("note"):
            actual = Fraction(int(note.findtext("duration")), divisions)
            dots = len(note.findall("dot"))
            notated = units[note.findtext("type")] * (2 - Fraction(1, 2**dots))
            assert actual == notated
            assert (note.find("rest") is None) != (note.find("pitch") is None)
            total += actual
        assert total == (1 if measure.get("implicit") == "yes" else meter)


def test_full_key_meter_grid_and_seed_determinism(settings: Settings) -> None:
    for fifths in range(-7, 8):
        for meter in settings.meters:
            cfg = settings.model_copy(
                update={"keys": (Key(fifths=fifths, weight=1),), "meters": (meter,)}
            )
            seed = f"train-grid-{fifths + 7}-{meter.beats}-{meter.beat_type}"
            xml = generate(seed, cfg)
            assert xml == generate(seed, cfg)
            validate_music(xml)
            root = ET.fromstring(xml)
            altered = ("FCGDAEB" if fifths > 0 else "BEADGCF")[: abs(fifths)]
            for pitch in root.findall(".//pitch"):
                expected = (1 if fifths > 0 else -1) if pitch.findtext("step") in altered else 0
                assert int(pitch.findtext("alter", "0")) == expected


@pytest.mark.parametrize("seed", ["eval-bad", "train-../bad", "train-", "other"])
def test_seed_rejection(settings: Settings, seed: str) -> None:
    with pytest.raises(ValueError, match="train"):
        generate(seed, settings)


def test_disabled_invalid_and_unfillable_config(settings: Settings) -> None:
    with pytest.raises(ValueError, match="disabled"):
        generate("train-test", settings.model_copy(update={"enabled": False}))
    with pytest.raises(ValueError, match="weights"):
        generate("train-test", settings.model_copy(update={"step_weights": (1,)}))
    with pytest.raises(ValueError, match="range"):
        generate(
            "train-test",
            settings.model_copy(
                update={"clefs": (settings.clefs[0].model_copy(update={"low": 40, "high": 20}),)}
            ),
        )
    with pytest.raises(ValueError, match="fill"):
        rhythm_plan(
            np.random.default_rng(0),
            settings.model_copy(update={"rhythms": (Rhythm(kind="whole", dots=0, weight=1),)}),
            96,
        )
    with pytest.raises(ValueError, match="represent"):
        Rhythm(kind="32nd", dots=2, weight=1).ticks(1)
    for update in (
        {"purpose": "training"},
        {"steps": [100]},
        {"rest_probability": float("nan")},
        {"keys": []},
        {"unknown_field": True},
    ):
        with pytest.raises(ValidationError):
            Settings.model_validate({**settings.model_dump(), **update})


@pytest.mark.parametrize("index", [0, 1, 2])
def test_clefs_render_in_external_process(settings: Settings, index: int) -> None:
    cfg = settings.model_copy(update={"clefs": (settings.clefs[index],)})
    xml = generate("train-clef", cfg)
    result = subprocess.run(
        [sys.executable, "-m", "training.data.verovio_worker", str(CONFIG), "Leipzig"],
        input=xml.encode(),
        capture_output=True,
        cwd=ROOT,
        timeout=60,
        check=True,
    )
    assert json.loads(result.stdout)["pages"]
    validate_music(xml)


def test_cli_quarantine_and_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from training.data import leadgen

    monkeypatch.setattr(leadgen, "ROOT", tmp_path)
    args = [
        "leadgen",
        "--config",
        str(ROOT / "configs/data/leadgen-development.yaml"),
        "--seed",
        "train-cli",
        "--output",
        str(tmp_path / "work/sample"),
    ]
    monkeypatch.setattr(sys, "argv", args)
    main()
    provenance = json.loads((tmp_path / "work/sample/provenance.json").read_text())
    assert provenance["status"] == "quarantine"
    assert provenance["training_admission"].startswith("BLOCKED")
    assert not (tmp_path / "data").exists()
    monkeypatch.setattr(sys, "argv", [*args[:-1], str(tmp_path / "outside")])
    with pytest.raises(ValueError, match="work"):
        main()
