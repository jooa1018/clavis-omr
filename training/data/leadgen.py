"""LeadGen development core: deterministic, configured single-voice MusicXML."""

import argparse
import hashlib
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from training.data.licenses import require_use
from training.data.smoke import ROOT, write_json


class Weighted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    weight: float = Field(gt=0, allow_inf_nan=False)


class Key(Weighted):
    fifths: int = Field(ge=-7, le=7)


class Meter(Weighted):
    beats: int = Field(ge=1, le=16)
    beat_type: Literal[2, 4, 8]


class Clef(Weighted):
    name: Literal["G2", "F4", "G2_8vb"]
    low: int = Field(ge=7, le=49)
    high: int = Field(ge=7, le=49)


class Rhythm(Weighted):
    kind: Literal["whole", "half", "quarter", "eighth", "16th", "32nd"]
    dots: int = Field(ge=0, le=2)

    def ticks(self, divisions: int) -> int:
        """Exact notated duration in MusicXML quarter-note division units."""
        denominator = {"whole": 1, "half": 2, "quarter": 4, "eighth": 8, "16th": 16, "32nd": 32}[
            self.kind
        ]
        value = Fraction(4 * divisions, denominator) * sum(
            (Fraction(1, 2**dot) for dot in range(self.dots + 1)), Fraction(0)
        )
        if value.denominator != 1:
            raise ValueError("divisions cannot exactly represent configured rhythm")
        return int(value)


class Settings(BaseModel):
    """No adopted training profile: callers must supply a development configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    purpose: Literal["development"]
    enabled: bool
    divisions: int = Field(ge=1, le=16383)
    bars: tuple[Literal[4, 8], ...] = Field(min_length=1)
    keys: tuple[Key, ...] = Field(min_length=1)
    meters: tuple[Meter, ...] = Field(min_length=1)
    clefs: tuple[Clef, ...] = Field(min_length=1)
    rhythms: tuple[Rhythm, ...] = Field(min_length=1)
    steps: tuple[int, ...] = Field(min_length=1)
    step_weights: tuple[Annotated[float, Field(gt=0, allow_inf_nan=False)], ...]
    rest_probability: float = Field(ge=0, le=1, allow_inf_nan=False)
    pickup_probability: float = Field(ge=0, le=1, allow_inf_nan=False)
    tempo: int = Field(ge=30, le=240)

    @field_validator("steps")
    @classmethod
    def bounded_steps(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if any(abs(value) > 7 for value in values):
            raise ValueError("Development steps must stay within one diatonic octave")
        return values


def pick[T: Weighted](rng: np.random.Generator, choices: tuple[T, ...]) -> T:
    """Sample only the caller's explicit weights."""
    weights = np.array([item.weight for item in choices], dtype=float)
    return choices[int(rng.choice(len(choices), p=weights / weights.sum()))]


def rhythm_plan(rng: np.random.Generator, settings: Settings, target: int) -> list[Rhythm]:
    """Compose a fillable rhythm before drawing notes, without padding after the fact."""
    ticks = [rhythm.ticks(settings.divisions) for rhythm in settings.rhythms]
    reachable = [True] + [False] * target
    for remaining in range(1, target + 1):
        reachable[remaining] = any(t <= remaining and reachable[remaining - t] for t in ticks)
    if not reachable[target]:
        raise ValueError("Configured rhythms cannot fill meter/pickup exactly")
    plan: list[Rhythm] = []
    while target:
        candidates = tuple(
            r
            for r, t in zip(settings.rhythms, ticks, strict=True)
            if t <= target and reachable[target - t]
        )
        rhythm = pick(rng, candidates)
        plan.append(rhythm)
        target -= rhythm.ticks(settings.divisions)
    return plan


def generate(seed: str, settings: Settings) -> str:
    """Generate self-authored notation only; this API does not admit training data."""
    if not re.fullmatch(r"train-[A-Za-z0-9][A-Za-z0-9_-]*", seed):
        raise ValueError("A safe train-* seed namespace is required")
    require_use("leadgen", "tool-test")
    if not settings.enabled:
        raise ValueError("DATA-GEN-001 disabled")
    if len(settings.steps) != len(settings.step_weights):
        raise ValueError("step weights do not match steps")
    if any(clef.low > clef.high for clef in settings.clefs):
        raise ValueError("Inverted voice range")
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed.encode()).digest(), "big"))
    key, meter, clef = (
        pick(rng, settings.keys),
        pick(rng, settings.meters),
        pick(rng, settings.clefs),
    )
    bars = int(rng.choice(settings.bars))
    full = Fraction(settings.divisions * 4 * meter.beats, meter.beat_type)
    if full.denominator != 1:
        raise ValueError("divisions cannot exactly represent meter")
    pickup = bool(rng.random() < settings.pickup_probability)
    if pickup and settings.divisions >= full:
        raise ValueError("Pickup must be shorter than the meter")
    plans = [
        rhythm_plan(rng, settings, settings.divisions if pickup and i == 0 else int(full))
        for i in range(bars)
    ]
    root = ET.Element("score-partwise", version="4.0")
    ET.SubElement(ET.SubElement(root, "work"), "work-title").text = "Clavis synthetic study"
    part_info = ET.SubElement(ET.SubElement(root, "part-list"), "score-part", id="P1")
    ET.SubElement(part_info, "part-name").text = "Voice"
    part = ET.SubElement(root, "part", id="P1")
    degree = int(rng.integers(clef.low, clef.high + 1))
    step_weights = np.array(settings.step_weights)
    alterations = ("FCGDAEB" if key.fifths > 0 else "BEADGCF")[: abs(key.fifths)]
    for index, plan in enumerate(plans):
        measure = ET.SubElement(part, "measure", number=str(index + 1))
        if index == 0:
            if pickup:
                measure.set("implicit", "yes")
            attrs = ET.SubElement(measure, "attributes")
            ET.SubElement(attrs, "divisions").text = str(settings.divisions)
            ET.SubElement(ET.SubElement(attrs, "key"), "fifths").text = str(key.fifths)
            time = ET.SubElement(attrs, "time")
            ET.SubElement(time, "beats").text = str(meter.beats)
            ET.SubElement(time, "beat-type").text = str(meter.beat_type)
            cg = ET.SubElement(attrs, "clef")
            ET.SubElement(cg, "sign").text = "F" if clef.name == "F4" else "G"
            ET.SubElement(cg, "line").text = "4" if clef.name == "F4" else "2"
            if clef.name == "G2_8vb":
                ET.SubElement(cg, "clef-octave-change").text = "-1"
            metronome = ET.SubElement(
                ET.SubElement(ET.SubElement(measure, "direction"), "direction-type"), "metronome"
            )
            ET.SubElement(metronome, "beat-unit").text = "quarter"
            ET.SubElement(metronome, "per-minute").text = str(settings.tempo)
        for rhythm in plan:
            note = ET.SubElement(measure, "note")
            if rng.random() < settings.rest_probability:
                ET.SubElement(note, "rest")
            else:
                step_delta = int(rng.choice(settings.steps, p=step_weights / step_weights.sum()))
                degree = int(np.clip(degree + step_delta, clef.low, clef.high))
                step = "CDEFGAB"[degree % 7]
                pitch = ET.SubElement(note, "pitch")
                ET.SubElement(pitch, "step").text = step
                if step in alterations:
                    ET.SubElement(pitch, "alter").text = "1" if key.fifths > 0 else "-1"
                ET.SubElement(pitch, "octave").text = str(degree // 7)
            ET.SubElement(note, "duration").text = str(rhythm.ticks(settings.divisions))
            ET.SubElement(note, "voice").text = "1"
            ET.SubElement(note, "type").text = rhythm.kind
            for _ in range(rhythm.dots):
                ET.SubElement(note, "dot")
    ET.SubElement(
        ET.SubElement(measure, "barline", location="right"), "bar-style"
    ).text = "light-heavy"
    return ET.tostring(root, encoding="unicode")


def main() -> None:
    """Export one development sample and provenance to the work quarantine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "work"):
        raise ValueError("Development output must stay under work/")
    raw = args.config.read_bytes()
    settings = Settings.model_validate(yaml.safe_load(raw))
    xml = generate(args.seed, settings).encode()
    output.mkdir(parents=True, exist_ok=True)
    (output / "score.musicxml").write_bytes(xml)
    write_json(
        output / "provenance.json",
        {
            "seed": args.seed,
            "source": "leadgen",
            "status": "quarantine",
            "config_sha256": hashlib.sha256(raw).hexdigest(),
            "musicxml_sha256": hashlib.sha256(xml).hexdigest(),
            "training_admission": "BLOCKED_PENDING_W4_AND_APPROVED_PROFILE",
        },
    )


if __name__ == "__main__":
    main()
