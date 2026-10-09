import itertools
import json
import math
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest

from clavis.contracts.text import StaffLink, Syllable, TextIR
from clavis.text.beam import BeamLimits, ChordCandidate, chord_beam
from clavis.text.bridge import TextObservation, text_ir
from clavis.text.chord import ChordGrammar
from clavis.text.ctc import CtcLimits
from clavis.text.detection import DbLimits, TextRegion, detection_regions
from clavis.text.lyrics import lyric_segments
from clavis.text.ppocr import PpOcrOutput

ROOT = Path(__file__).resolve().parents[2]
VALUES = {
    r["name"]: r["value"] for r in json.loads((ROOT / "configs/text/constants.yaml").read_text())
}
GRAMMAR = ChordGrammar(ROOT / "configs/text/rules.yaml", max_chars=256, max_states=4096)
CTC = CtcLimits(2048, 16384, 2000000)
BEAM = BeamLimits(256, 20, 2000000)
DB = DbLimits(
    **{
        n: VALUES["text.db." + n]
        for n in (
            "threshold_bp",
            "box_threshold_bp",
            "unclip_ratio",
            "max_components",
            "max_pixels",
        )
    }
)


def decode(rows, alphabet=("", "C", "7"), limits=BEAM, enabled=True):
    return chord_beam(
        rows,
        alphabet,
        blank_index=0,
        grammar=GRAMMAR,
        ctc_limits=CTC,
        limits=limits,
        enabled=enabled,
    )


@pytest.mark.parametrize("alphabet", [("", "C", "7"), ("", "C", "C"), ("", "C", "M")])
def test_beam_matches_exhaustive_ctc_path_sum(alphabet):
    rows = [[0.2, 0.5, 0.3], [0.3, 0.4, 0.3], [0.5, 0.2, 0.3]]
    expected = {}
    for path in itertools.product(range(3), repeat=3):
        collapsed = [c for i, c in enumerate(path) if c and (not i or path[i - 1] != c)]
        spelling = GRAMMAR.parse("".join(alphabet[c] for c in collapsed))
        if spelling:
            mass = math.prod(row[c] for row, c in zip(rows, path, strict=True))
            expected[spelling.normalized] = expected.get(spelling.normalized, 0) + mass
    actual = {c.normalized: c.mass_bp for c in decode(rows, alphabet)}
    assert actual.keys() == expected.keys()
    for k in actual:
        assert abs(actual[k] - expected[k] * 10000) <= 1.000001


def test_beam_retains_visual_alternative_not_invalid_greedy():
    result = decode([[0, 0.3, 0.7]], ("", "C", "X"))
    assert result == (ChordCandidate("C", "C", 3000),)
    assert decode([[0, 0, 1]], ("", "C", "X")) == ()
    assert decode([[0, 1, 0]], enabled=False) == ()
    assert decode([[1, 0, 0]]) == ()


def test_beam_aliases_do_not_force_probability_to_one():
    result = decode([[0, 1, 0, 0], [0.2, 0, 0.4, 0.4]], ("", "C", "M", "Δ"))
    assert result[0].normalized == "C"
    assert 9999 <= result[0].mass_bp <= 10000
    with pytest.raises(ValueError, match="budget"):
        decode([[0, 1, 0]] * 2, limits=BeamLimits(1, 1, 1))
    with pytest.raises(ValueError):
        BeamLimits(0, 1, 10)
    with pytest.raises(ValueError):
        decode([[0.9, 0.9, 0]])
    with pytest.raises(ValueError, match="alphabet"):
        decode(
            [[1 / 30000] * 30000], ("",) + ("C",) * 29999, limits=BEAM
        )  # alphabet budget is checked first


def test_beam_repeat_requires_blank_and_pruning_is_not_renormalized():
    alphabet = ("", "C", "1")
    assert decode([[0, 1, 0], [0, 0, 1], [0, 0, 1]], alphabet) == ()
    repeated = decode([[0, 1, 0], [0, 0, 1], [1, 0, 0], [0, 0, 1]], alphabet)
    assert repeated == (ChordCandidate("C11", "C11", 10000),)
    pruned = decode([[0.1, 0.6, 0.3]], ("", "C", "D"), BeamLimits(1, 1, 100))
    assert pruned == (ChordCandidate("C", "C", 6000),)


def test_smoke_metrics_keep_spacing_and_syllable_geometry_separate():
    from training.models.text.integration_smoke import matches, no_space, spacing, syllable_scores

    assert no_space("가 나\t다") == "가나다"
    assert spacing("가 나다") == {1}
    assert spacing("가나 다") == {2}
    assert spacing("  가 \t 나  ") == {1}
    assert matches([(0, 0, 10, 10), (1, 0, 10, 10)], [(0, 0, 10, 10)]) == [(0, 0)]
    boxes = [(0, 0, 10, 10), (20, 0, 10, 10)]
    assert syllable_scores(boxes, boxes, ["각", None], "가나") == dict(
        attempted=1, correct=0, edits=1, characters=1
    )


def det_map():
    data = np.zeros((30, 60), np.float32)
    data[5:15, 10:30] = 0.9
    return PpOcrOutput(data, (60, 120), (30, 60))


def test_db_geometry_scaling_order_and_offset():
    output = det_map()
    regions = detection_regions(output, limits=DB, enabled=True)
    assert len(regions) == 1 and regions[0].score_bp == 9000
    x, y, w, h = regions[0].box
    assert x < 20 and y < 10 and x + w > 58 and y + h > 28
    moved = detection_regions(output, limits=DB, enabled=True, offset=(7.0, 13.0))[0]
    assert moved.box == pytest.approx((x + 7, y + 13, w, h))
    assert detection_regions(output, limits=DB, enabled=False) == ()


def test_db_holes_empty_noise_thresholds_and_limits():
    output = det_map()
    output.probabilities[8:12, 15:25] = 0
    assert len(detection_regions(output, limits=DB, enabled=True)) == 1
    assert not detection_regions(output, limits=replace(DB, box_threshold_bp=9900), enabled=True)
    output.probabilities[:] = 0
    output.probabilities[2, 2] = 1
    assert not detection_regions(output, limits=DB, enabled=True)
    output.probabilities[8:12, 15:25] = 1
    with pytest.raises(ValueError, match="budget"):
        detection_regions(output, limits=replace(DB, max_components=1), enabled=True)
    with pytest.raises(ValueError):
        detection_regions(output, limits=replace(DB, max_pixels=1), enabled=True)
    output.probabilities[0, 0] = np.nan
    with pytest.raises(ValueError):
        detection_regions(output, limits=DB, enabled=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(threshold_bp=-1),
        dict(box_threshold_bp=True),
        dict(unclip_ratio=float("inf")),
        dict(max_components=0),
    ],
)
def test_db_invalid_config(kwargs):
    with pytest.raises(ValueError):
        replace(DB, **kwargs)


def segments(image, **extra):
    args = dict(staff_space=8.0, gap_spaces=0.25, max_pixels=100000, max_segments=128, enabled=True)
    args.update(extra)
    return lyric_segments(image, **args)


def ink_image():
    image = np.full((20, 40, 3), 255, np.uint8)
    image[4:14, 2:6] = 0
    image[6:12, 8:12] = 0
    image[4:14, 25:35] = 0
    return image


def test_lyric_segments_are_measured_ink_not_equal_divisions():
    assert segments(ink_image()) == ((2.0, 4.0, 10.0, 10.0), (25.0, 4.0, 10.0, 10.0))
    assert segments(ink_image(), offset=(10.0, 20.0))[0] == (12.0, 24.0, 10.0, 10.0)
    assert segments(ink_image(), enabled=False) == ()
    assert segments(np.full((4, 4, 3), 255, np.uint8)) == ()
    with pytest.raises(ValueError, match="budget"):
        segments(ink_image(), max_segments=1)
    with pytest.raises(ValueError):
        segments(ink_image(), staff_space=0.0)


def observation():
    return TextObservation(
        TextRegion(
            (0.0, 0.0, 40.0, 20.0), [(0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0)], 9000
        ),
        "CΔ7",
        "chord",
        {"chord": 10000},
        StaffLink(staff_id="st1", relation="above", distance_spaces=2.0),
        8000,
        (ChordCandidate("CΔ7", "Cmaj7", 8000),),
    )


def test_textir_preserves_printed_form_and_reports_missing_semantics():
    result = text_ir((observation(),), page_index=0, grammar=GRAMMAR, enabled=True)
    item = result.ir.items[0]
    assert item.text == "CΔ7" and item.alternatives[0].text == "Cmaj7"
    assert item.chord is None and item.glyphs is None
    assert "harmonic interpretation" in result.diagnostics[0]
    assert TextIR.model_validate_json(result.ir.model_dump_json(by_alias=True)) == result.ir
    import jsonschema

    schema = json.loads((ROOT / "src/clavis/contracts/schemas/TextIR.json").read_text())
    jsonschema.validate(
        json.loads(result.ir.model_dump_json(by_alias=True, exclude_none=True)), schema
    )


def test_bridge_abstention_and_validation():
    obs = observation()
    assert not text_ir((obs,), page_index=0, grammar=GRAMMAR, enabled=False).ir.items
    assert not text_ir(
        (replace(obs, text="not a chord"),), page_index=0, grammar=GRAMMAR, enabled=True
    ).ir.items
    for changed in [
        replace(obs, candidates=(ChordCandidate("X", "C", 100),)),
        replace(obs, candidates=obs.candidates * 2),
        replace(obs, role="lyric"),
    ]:
        with pytest.raises(ValueError):
            text_ir((changed,), page_index=0, grammar=GRAMMAR, enabled=True)
    syllable = Syllable(text="가", box=(2.0, 4.0, 10.0, 10.0), hyphen_after=False, extender=False)
    lyric = replace(
        obs,
        text="가",
        role="lyric",
        role_probs={"lyric": 10000},
        candidates=(),
        syllables=(syllable,),
    )
    assert text_ir((lyric,), page_index=0, grammar=GRAMMAR, enabled=True).ir.items[0].syllables
    with pytest.raises(ValueError):
        text_ir(
            (replace(lyric, region=replace(obs.region, box=(0.0, 0.0, 1.0, 1.0))),),
            page_index=0,
            grammar=GRAMMAR,
            enabled=True,
        )


def test_three_runs_one_four_threads_deterministic():
    results = []
    before = cv2.getNumThreads()
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(3):
                results.append(
                    (
                        decode([[0.2, 0.5, 0.3]] * 3),
                        detection_regions(det_map(), limits=DB, enabled=True),
                        segments(ink_image()),
                        text_ir(
                            (observation(),), page_index=0, grammar=GRAMMAR, enabled=True
                        ).ir.model_dump_json(by_alias=True),
                    )
                )
    finally:
        cv2.setNumThreads(before)
    assert all(r == results[0] for r in results)
