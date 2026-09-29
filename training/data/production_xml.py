"""Quarantined production MusicXML candidates from complete-group rhythm profiles."""

import copy
import xml.etree.ElementTree as ET
from fractions import Fraction
from typing import Any

import numpy as np

from training.data.licenses import require_use
from training.data.production_notation import (
    attributes,
    child,
    direction,
    harmony,
    lyrics,
    navigation,
    notation,
    note,
    pitch,
    tie_pair,
)
from training.data.production_plan import SongPlan, grace_count
from training.data.production_rhythm import Fitted, Value, group_patterns, seeded


def changed[T](current: T, weights: dict[T, float], rng: np.random.Generator) -> T:
    keys = [key for key in weights if key != current]
    probabilities = np.array([weights[key] for key in keys], dtype=float)
    return keys[int(rng.choice(len(keys), p=probabilities / probabilities.sum()))]


def generate(
    plan: SongPlan,
    profiles: dict[str, Fitted],
    settings: dict[str, Any],
    distribution: dict[str, Any],
) -> str:
    """Author original notes; never admit outputs or infer elements from an image."""
    require_use("leadgen", "tool-test")
    if not distribution["enabled"]:
        raise ValueError("Production generation disabled")
    rng = seeded(plan.seed)
    marked = dict(plan.marked_measures)
    slash = set(marked.get("slash", ()))
    double = set(marked.get("two_voice", ()))
    triplet = set(marked.get("triplet", ()))
    change_slot = int(rng.integers(1, plan.bars)) if "key_meter_change" in plan.features else None
    new_meter = (
        changed(plan.meter, distribution["meter_weights"], rng)
        if change_slot is not None
        else plan.meter
    )
    new_key = (
        changed(plan.fifths, distribution["key_weights"][plan.mode], rng)
        if change_slot is not None
        else plan.fifths
    )
    meters = [
        new_meter if change_slot is not None and slot >= change_slot else plan.meter
        for slot in range(plan.bars)
    ]
    keys = [
        new_key if change_slot is not None and slot >= change_slot else plan.fifths
        for slot in range(plan.bars)
    ]
    clef = settings["clefs"][int(rng.integers(len(settings["clefs"])))]
    divisions = settings["divisions"]
    step_weights = np.array(settings["step_weights"], dtype=float)
    step_weights /= step_weights.sum()
    root = ET.Element("score-partwise", version="4.0")
    child(child(root, "work"), "work-title", "Clavis original study")
    child(root, "movement-title", "Procedural phrase")
    identification = child(root, "identification")
    child(identification, "creator", "Clavis generator", type="composer")
    child(identification, "creator", "Clavis original syllables", type="lyricist")
    part_info = child(child(root, "part-list"), "score-part", id="P1")
    child(part_info, "part-name", "Voice")
    part = child(root, "part", id="P1")
    for _ in range(settings["max_rhythm_attempts"]):
        part.clear()
        part.set("id", "P1")
        main_notes = []
        by_measure: list[list[ET.Element]] = []
        lengths = []
        degree = int(rng.integers(clef["low"], clef["high"] + 1))
        for slot, (meter, fifths) in enumerate(zip(meters, keys, strict=True)):
            measure = child(part, "measure", number=str(slot + 1))
            is_pickup = "pickup" in plan.features and not by_measure
            numerator, denominator = map(int, meter.split("/"))
            total = Fraction(4 * numerator, denominator)
            if is_pickup:
                measure.set("implicit", "yes")
                total = Fraction(1)
            lengths.append(total)
            beat_groups = profiles[meter].sample(rng)
            if is_pickup:
                pool = group_patterns(total)
                beat_groups = (pool[int(rng.integers(len(pool)))],)
            tuplet_group: int | None = None
            if slot in triplet:
                # A complete first beat plus a configured complete remainder motif.
                beat_groups = ((Value("eighth"),) * 3,) + tuple(
                    (Value(kind, dots),)
                    for kind, dots in settings["triplet_remainders"][str(total)]
                )
                tuplet_group = 0
            measure_notes = []
            for voice in range(1, 3 if slot in double else 2):
                if voice == 2:
                    child(child(measure, "backup"), "duration", int(total * divisions))
                groups = beat_groups if voice == 1 else profiles[meter].sample(rng)
                if voice == 2 and is_pickup:
                    pool = group_patterns(total)
                    groups = (pool[int(rng.integers(len(pool)))],)
                accidental_state: dict[tuple[str, int], int] = {}
                for group_index, group in enumerate(groups):
                    events = []
                    for value in group:
                        rest = rng.random() < settings["rest_probability"] and slot not in slash
                        degree = int(
                            np.clip(
                                degree + int(rng.choice(settings["steps"], p=step_weights)),
                                clef["low"],
                                clef["high"],
                            )
                        )
                        chromatic = (
                            int(rng.choice([-1, 1]))
                            if slot not in double
                            and rng.random() < settings["chromatic_probability"]
                            else 0
                        )
                        pv = pitch(degree, fifths, chromatic)
                        prior = accidental_state.get((pv[0], pv[1]), pitch(degree, fifths)[2])
                        event = note(
                            measure,
                            value,
                            None if rest else pv,
                            divisions,
                            voice=voice,
                            slash=slot in slash,
                            triplet=(voice == 1 and group_index == tuplet_group),
                            accidental=(pv[2] != prior),
                        )
                        if not rest:
                            accidental_state[(pv[0], pv[1])] = pv[2]
                        events.append(event)
                        if voice == 1:
                            main_notes.append(event)
                            measure_notes.append(event)
                    if voice == 1 and group_index == tuplet_group:
                        child(
                            notation(events[0]), "tuplet", type="start", number="1", bracket="yes"
                        )
                        child(notation(events[-1]), "tuplet", type="stop", number="1")
                # Beam/flag layout is left to the external renderer's metric engraving.
            by_measure.append(measure_notes)
        pitched = [event for event in main_notes if event.find("pitch") is not None]
        if "grace" not in plan.features or len(pitched) >= settings["minimum_grace_base_notes"]:
            break
    else:
        raise ValueError("Cannot satisfy grace denominator within configured attempt budget")
    measures = part.findall("measure")
    if "grace" not in plan.features and rng.random() < settings["whole_rest_song_probability"]:
        available = [
            slot
            for slot, measure in enumerate(measures)
            if slot not in slash | double | triplet and measure.get("implicit") != "yes"
        ]
        if available:
            selected = available[int(rng.integers(len(available)))]
            measure = measures[selected]
            measure[:] = []
            event = child(measure, "note")
            child(event, "rest", measure="yes")
            child(event, "duration", int(lengths[selected] * divisions))
            child(event, "voice", 1)
            by_measure[selected] = [event]
            main_notes = [event for events in by_measure for event in events]
            pitched = [event for event in main_notes if event.find("pitch") is not None]
    attributes(
        measures[0], plan.fifths, plan.mode, plan.meter, divisions=divisions, clef=clef["name"]
    )
    if change_slot is not None:
        attributes(measures[change_slot], new_key, plan.mode, new_meter)
    tempo = ET.Element("direction")
    met = child(child(tempo, "direction-type"), "metronome")
    child(met, "beat-unit", "quarter")
    child(met, "per-minute", settings["tempo"])
    measures[0].insert(1, tempo)
    for measure in measures:
        temporary = ET.Element("measure")
        direction(temporary, settings["sections"][int(rng.integers(len(settings["sections"])))])
        insertion = next(
            (index for index, item in enumerate(measure) if item.tag == "note"), len(measure)
        )
        measure.insert(insertion, temporary[0])
    # Additional chord heads share an existing stem, voice and exact duration.
    for slot, events in enumerate(by_measure):
        measure = measures[slot]
        for event in events:
            p = event.find("pitch")
            if p is None or rng.random() >= settings["chord_head_probability"]:
                continue
            clone = copy.deepcopy(event)
            for tag in ("notations", "beam", "lyric", "accidental"):
                for extra in clone.findall(tag):
                    clone.remove(extra)
            cp = clone.find("pitch")
            assert cp is not None
            degree = "CDEFGAB".index(p.findtext("step", "C")) + 7 * int(p.findtext("octave", "4"))
            step, octave, alter = pitch(
                degree + 2 if degree + 2 <= clef["high"] else degree - 2, keys[slot]
            )
            cp.clear()
            child(cp, "step", step)
            child(cp, "alter", alter)
            child(cp, "octave", octave)
            clone.insert(0, ET.Element("chord"))
            measure.insert(list(measure).index(event) + 1, clone)
    if rng.random() < settings["tie_song_probability"]:
        pairs = [
            (a, b)
            for a, b in zip(main_notes, main_notes[1:], strict=False)
            if a.find("pitch") is not None and b.find("pitch") is not None
        ]
        if pairs:
            first, second = pairs[int(rng.integers(len(pairs)))]
            tie_pair(first, second)
    for slot, measure in enumerate(measures):
        density = int(rng.integers(settings["max_harmonies_per_measure"] + 1))
        for chord_index in range(density):
            tonic = (4 * keys[slot] + (5 if plan.mode == "minor" else 0)) % 7
            root_pitch = pitch(28 + (tonic + int(rng.integers(7))) % 7, keys[slot])
            bass = (
                pitch(28 + int(rng.integers(7)), keys[slot])
                if rng.random() < settings["slash_chord_probability"]
                else None
            )
            temporary = ET.Element("measure")
            harmony(
                temporary,
                root_pitch,
                settings["harmonies"][int(rng.integers(len(settings["harmonies"])))],
                int(lengths[slot] * divisions * chord_index / max(1, density)),
                bass,
            )
            insertion = next(
                (index for index, item in enumerate(measure) if item.tag in ("note", "backup")),
                len(measure),
            )
            measure.insert(insertion, temporary[0])
    if "grace" in plan.features:
        ordinary = [event for event in part.iter("note") if event.find("pitch") is not None]
        low, high = distribution["features"]["grace"]["within_range"]
        count = grace_count(len(ordinary), low, high, rng)
        candidates = [
            (measure, event)
            for measure in measures
            for event in measure.findall("note")
            if event.find("pitch") is not None
            and event.find("chord") is None
            and not any(t.get("type") == "stop" for t in event.findall("tie"))
        ]
        for index in rng.choice(len(candidates), count, replace=False):
            measure, event = candidates[int(index)]
            temporary = ET.Element("measure")
            p = event.find("pitch")
            assert p is not None
            grace = note(
                temporary,
                Value("eighth"),
                (
                    p.findtext("step", "C"),
                    int(p.findtext("octave", "4")),
                    int(p.findtext("alter", "0")),
                ),
                divisions,
                grace=True,
            )
            measure.insert(list(measure).index(event), grace)
    if pitched and rng.random() < settings["fermata_song_probability"]:
        child(notation(pitched[int(rng.integers(len(pitched)))]), "fermata")
    lyrics(main_notes, settings, rng)
    if "repeat_volta_navigation" in plan.features:
        navigation(measures, rng)
    child(child(measures[-1], "barline", location="right"), "bar-style", "light-heavy")
    return ET.tostring(root, encoding="unicode")
