"""Local SYN-Val 아님 diagnostics, not a W4 KPI evaluator.

16 self-authored Hangul rows (64 blocks), 12 chord crops, 4 synthetic text
canvases and at most 68 derived segment crops = at most 100 unique images.
Predeclared font/size/spacing sweep; never tune runtime rules on its failures.
Run with OR-005 --items 100. Model/font admission still requires W2 confirmation.
"""

import argparse
import io
import json
from dataclasses import asdict
from itertools import product
from pathlib import Path
from time import perf_counter
from unicodedata import normalize

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from clavis.contracts.text import StaffLink, Syllable
from clavis.text.beam import BeamLimits, chord_beam
from clavis.text.bridge import TextObservation, text_ir
from clavis.text.ctc import greedy_observation
from clavis.text.detection import DbLimits, TextRegion, detection_regions
from clavis.text.lyrics import lyric_segments
from clavis.text.ppocr import infer_image
from training.models.text.artifacts import load_artifacts
from training.models.text.ppocr_smoke import edit_distance


def no_space(text):
    return "".join(c for c in normalize("NFC", text) if not c.isspace())


def spacing(text):
    """Inter-character boundary offsets, independent of the observed characters.

    Insertions/deletions can shift offsets; report this limitation with CER.
    Consecutive whitespace is one boundary; leading/trailing space is ignored.
    """
    result, index, pending = set(), 0, False
    for c in normalize("NFC", text).strip():
        if c.isspace():
            pending = True
        else:
            if pending and index:
                result.add(index)
            pending = False
            index += 1
    return result


def iou(a, b):
    x, y, w, h = a
    u, v, s, t = b
    intersection = max(0, min(x + w, u + s) - max(x, u)) * max(0, min(y + h, v + t) - max(y, v))
    return intersection / (w * h + s * t - intersection) if w * h + s * t else 0.0


def matches(predicted, expected):
    # Diagnostic IoU 0.5 is predeclared here; this is not an engine threshold.
    pairs = sorted(
        (-iou(a, b), i, j) for i, a in enumerate(predicted) for j, b in enumerate(expected)
    )
    used_p, used_g, result = set(), set(), []
    for negative, i, j in pairs:
        if -negative >= 0.5 and i not in used_p and j not in used_g:
            used_p.add(i)
            used_g.add(j)
            result.append((i, j))
    return result


def syllable_scores(predicted, expected, observed, reference):
    """Keep segmentation misses separate from transcription on matched crops."""
    measured = [
        (observed[i], reference[j])
        for i, j in matches(predicted, expected)
        if observed[i] is not None
    ]
    return dict(
        attempted=len(measured),
        correct=sum(a == b for a, b in measured),
        edits=sum(edit_distance(b, a) for a, b in measured),
        characters=sum(len(b) for _, b in measured),
    )


def render_blocks(text, font, gap):
    # Individual raster glyphs define expected ink boxes without invoking OCR.
    glyphs = []
    for c in text:
        if c.isspace():
            continue
        left, t, r, b = font.getbbox(c)
        tile = Image.new("RGB", (r - left, b - t), "white")
        ImageDraw.Draw(tile).text((-left, -t), c, font=font, fill="black")
        ink = np.any(np.asarray(tile) < 255, axis=2)
        ys, xs = np.nonzero(ink)
        box = (
            int(xs.min()),
            int(ys.min()),
            int(xs.max() - xs.min() + 1),
            int(ys.max() - ys.min() + 1),
        )
        glyphs.append((tile, box))
    margin = 8
    image = Image.new(
        "RGB",
        (
            sum(t.width for t, _ in glyphs) + gap * (len(glyphs) - 1) + 2 * margin,
            max(t.height for t, _ in glyphs) + 2 * margin,
        ),
        "white",
    )
    boxes = []
    x = margin
    for tile, (u, v, w, h) in glyphs:
        image.paste(tile, (x, margin))
        boxes.append((x + u, margin + v, w, h))
        x += tile.width + gap
    return image, boxes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter()
    models, profiles, grammar, image_limits, ctc_limits, values, verified = load_artifacts(
        args.manifest
    )
    beam = BeamLimits(
        **{n: values["text.beam." + n] for n in ("width", "top_k", "max_transitions")}
    )
    db = DbLimits(
        **{
            n: values["text.db." + n]
            for n in (
                "threshold_bp",
                "box_threshold_bp",
                "unclip_ratio",
                "max_components",
                "max_pixels",
            )
        }
    )
    crops = args.out.parent / "integration-crops"
    crops.mkdir(parents=True, exist_ok=True)
    artifacts = json.loads(args.manifest.read_text())["artifacts"]
    fonts = {
        family: verified(f"{family}/{family}-Regular.otf")
        for family in ("NotoSansCJKkr", "NotoSerifCJKkr")
    }
    calls = 0

    def recognize(image, key):
        nonlocal calls
        calls += 1
        bgr = np.asarray(image)[:, :, ::-1].copy()
        output = infer_image(models[key], bgr, profiles[key], image_limits, enabled=True)
        raw = greedy_observation(
            output.probabilities.tolist(),
            profiles[key].alphabet,
            blank_index=0,
            limits=ctc_limits,
            enabled=True,
            preserve_export_alphabet=True,
        )
        return raw, output

    lyric_rows = []
    segment_calls = 0
    # Unicode syllable arithmetic, not a lyric dictionary or song-derived corpus.
    syllables = [
        chr(0xAC00 + ((i * 7) % 19) * 21 * 28 + ((i * 5) % 21) * 28 + ((i * 3) % 28))
        for i in range(64)
    ]
    for index, (family, size, gap_factor) in enumerate(
        product(fonts, (12, 24), (0.5, 1.0, 1.5, 2.0))
    ):
        printed = "".join(syllables[index * 4 : index * 4 + 4])
        # Arbitrary reference word boundary is intentionally invisible in equal
        # note spacing: spacing correctness cannot be assumed from ink gaps.
        printed = printed[:2] + " " + printed[2:]
        font = ImageFont.truetype(io.BytesIO(fonts[family]), size)
        image, expected = render_blocks(printed, font, round(size * gap_factor))
        image.save(crops / f"lyric-{index:02d}.png")
        raw, _ = recognize(image, "korean")
        bgr = np.asarray(image)[:, :, ::-1].copy()
        predicted = lyric_segments(
            bgr,
            staff_space=size / 2,
            gap_spaces=values["text.lyrics.gap_spaces"],
            max_pixels=image_limits.max_pixels,
            max_segments=values["text.lyrics.max_segments"],
            enabled=True,
        )
        pairs = matches(predicted, expected)
        recognized = []
        wire_syllables = []
        for box in predicted:
            if segment_calls >= 68:
                recognized.append(None)
                continue
            x, y, w, h = box
            crop = image.crop((int(x), int(y), int(x + w), int(y + h)))
            observed, _ = recognize(crop, "korean")
            segment_calls += 1
            recognized.append(observed.text)
            if len(observed.text) == 1 and 0xAC00 <= ord(observed.text) <= 0xD7A3:
                wire_syllables.append(
                    Syllable(text=observed.text, box=box, hyphen_after=False, extender=False)
                )
        reference = no_space(printed)
        line_spaces, observed_spaces = spacing(printed), spacing(raw.text)
        boundaries = max(len(reference), len(no_space(raw.text))) - 1
        region = TextRegion(
            (0.0, 0.0, float(image.width), float(image.height)),
            [
                (0.0, 0.0),
                (float(image.width), 0.0),
                (float(image.width), float(image.height)),
                (0.0, float(image.height)),
            ],
            10000,
        )
        obs = TextObservation(
            region,
            raw.text,
            "lyric",
            {"lyric": 10000},
            StaffLink(staff_id="synthetic-staff", relation="below", distance_spaces=2.0),
            min(raw.token_prob_bp, default=0),
            syllables=tuple(wire_syllables),
        )
        wire = text_ir((obs,), page_index=0, grammar=grammar, enabled=True)
        lyric_rows.append(
            dict(
                family=family,
                fontPx=size,
                gapFactor=gap_factor,
                printed=printed,
                observed=raw.text,
                cerEdits=edit_distance(reference, no_space(raw.text)),
                cerCharacters=len(reference),
                expectedBoxes=expected,
                predictedBoxes=predicted,
                matched=len(pairs),
                exactSegmentation=len(pairs) == len(expected) == len(predicted),
                segmentTexts=recognized,
                syllableTextCorrect=sum(recognized[i] == reference[j] for i, j in pairs),
                syllableScores=syllable_scores(predicted, expected, recognized, reference),
                spaceCorrect=boundaries - len(line_spaces ^ observed_spaces),
                spaceBoundaries=boundaries,
                spaceTP=len(line_spaces & observed_spaces),
                spaceFP=len(observed_spaces - line_spaces),
                spaceFN=len(line_spaces - observed_spaces),
                spaceExact=line_spaces == observed_spaces,
                textIR=wire.ir.model_dump(by_alias=True, exclude_none=True),
            )
        )

    chord_rows = []
    for index, (family, size, printed) in enumerate(
        product(fonts, (12, 24), ("Cø", "F#M7", "C7(b9)"))
    ):
        font = ImageFont.truetype(io.BytesIO(fonts[family]), size)
        left, t, r, b = font.getbbox(printed)
        image = Image.new("RGB", (r - left + 16, b - t + 16), "white")
        ImageDraw.Draw(image).text((8 - left, 8 - t), printed, font=font, fill="black")
        image.save(crops / f"chord-{index:02d}.png")
        raw, output = recognize(image, "latin")
        repeat = []
        tick = perf_counter()
        for _ in range(3):
            repeat.append(
                chord_beam(
                    output.probabilities.tolist(),
                    profiles["latin"].alphabet,
                    blank_index=0,
                    grammar=grammar,
                    ctc_limits=ctc_limits,
                    limits=beam,
                    enabled=True,
                )
            )
        candidates = repeat[0]
        reference = grammar.parse(printed).normalized
        greedy = grammar.parse(raw.text)
        region = TextRegion(
            (0.0, 0.0, float(image.width), float(image.height)),
            [
                (0.0, 0.0),
                (float(image.width), 0.0),
                (float(image.width), float(image.height)),
                (0.0, float(image.height)),
            ],
            10000,
        )
        observations = (
            ()
            if not candidates
            else (
                TextObservation(
                    region,
                    candidates[0].text,
                    "chord",
                    {"chord": 10000},
                    StaffLink(staff_id="synthetic-staff", relation="above", distance_spaces=2.0),
                    candidates[0].mass_bp,
                    candidates=candidates,
                ),
            )
        )
        wire = text_ir(observations, page_index=0, grammar=grammar, enabled=True)
        chord_rows.append(
            dict(
                family=family,
                fontPx=size,
                printed=printed,
                greedy=raw.text,
                greedyExact=greedy is not None and greedy.normalized == reference,
                beamExact=bool(candidates and candidates[0].normalized == reference),
                candidates=[asdict(c) for c in candidates],
                repeat3Equal=len(set(repeat)) == 1,
                threeBeamSeconds=perf_counter() - tick,
                textIR=wire.ir.model_dump(by_alias=True, exclude_none=True),
                diagnostics=wire.diagnostics,
            )
        )

    detector_rows = []
    for _index, (family, size) in enumerate(product(fonts, (12, 24))):
        image = Image.new("RGB", (320, 160), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(io.BytesIO(fonts[family]), size)
        expected = []
        for text, x, y in [("Cmaj7", 30, 20), ("Blue river", 90, 90)]:
            left, t, r, b = draw.textbbox((x, y), text, font=font)
            draw.text((x, y), text, font=font, fill="black")
            expected.append((left, t, r - left, b - t))
        output = infer_image(
            models["det"],
            np.asarray(image)[:, :, ::-1].copy(),
            profiles["det"],
            image_limits,
            enabled=True,
        )
        repeated = [detection_regions(output, limits=db, enabled=True) for _ in range(3)]
        predicted = [r.box for r in repeated[0]]
        detector_rows.append(
            dict(
                family=family,
                fontPx=size,
                expectedBoxes=expected,
                regions=[asdict(r) for r in repeated[0]],
                matched=len(matches(predicted, expected)),
                repeat3Equal=all(r == repeated[0] for r in repeated),
            )
        )

    summary = dict(
        scope="SYN-Val 아님; synthetic component smoke, no B0/Dev improvement claim",
        artifactStatus="W2 received request; independent verification pending",
        artifactSha256={r["id"]: r["sha256"] for r in artifacts},
        generation=dict(
            hangulRows=16,
            blocksPerRow=4,
            sizes=[12, 24],
            gapFactors=[0.5, 1.0, 1.5, 2.0],
            seed="deterministic Unicode arithmetic",
            spacing="one invisible reference boundary after block 2",
        ),
        uniqueImages=16 + segment_calls + 12 + 4,
        recognizerCalls=calls,
        derivedCropsBudget=68,
        derivedCropsSkipped=sum(t is None for r in lyric_rows for t in r["segmentTexts"]),
        korean=dict(
            cerEdits=sum(r["cerEdits"] for r in lyric_rows),
            cerCharacters=sum(r["cerCharacters"] for r in lyric_rows),
            segmentMatches=sum(r["matched"] for r in lyric_rows),
            segmentsPredicted=sum(len(r["predictedBoxes"]) for r in lyric_rows),
            segmentsExpected=64,
            exactSegmentedLines=sum(r["exactSegmentation"] for r in lyric_rows),
            syllableTextCorrect=sum(r["syllableTextCorrect"] for r in lyric_rows),
            syllableCropsMatchedAttempted=sum(r["syllableScores"]["attempted"] for r in lyric_rows),
            syllableCerEdits=sum(r["syllableScores"]["edits"] for r in lyric_rows),
            syllableCerCharacters=sum(r["syllableScores"]["characters"] for r in lyric_rows),
            spaceCorrect=sum(r["spaceCorrect"] for r in lyric_rows),
            spaceBoundaries=sum(r["spaceBoundaries"] for r in lyric_rows),
            spaceTP=sum(r["spaceTP"] for r in lyric_rows),
            spaceFP=sum(r["spaceFP"] for r in lyric_rows),
            spaceFN=sum(r["spaceFN"] for r in lyric_rows),
            spaceExactLines=sum(r["spaceExact"] for r in lyric_rows),
        ),
        chords=dict(
            count=len(chord_rows),
            greedyExact=sum(r["greedyExact"] for r in chord_rows),
            beamExact=sum(r["beamExact"] for r in chord_rows),
        ),
        detection=dict(
            canvases=4,
            expected=8,
            predicted=sum(len(r["regions"]) for r in detector_rows),
            matched=sum(r["matched"] for r in detector_rows),
        ),
        roleConfusionMatrix="NOT_RUN: supplied synthetic oracle roles; no classifier claim",
        threads="OR-005 compute threads 2; pure postprocessing tested 1/4 separately",
        limitations=[
            "CER excludes whitespace; spacing offsets are affected by insertions/deletions.",
            "Spacing reference is not encoded by note spacing; no word inference is attempted.",
            "Syllable boxes use image projection, IoU>=0.5 one-to-one diagnostic matching.",
            "Only single Hangul blocks enter syllables; hyphen/extender evaluation NOT_RUN.",
            "No confidence intervals, adoption decision or real-page recall from this smoke.",
        ],
        lyricRows=lyric_rows,
        chordRows=chord_rows,
        detectorRows=detector_rows,
    )
    summary["korean"]["cerNoWhitespace"] = (
        summary["korean"]["cerEdits"] / summary["korean"]["cerCharacters"]
    )
    summary["korean"]["segmentationAccuracy"] = summary["korean"]["segmentMatches"] / 64
    summary["korean"]["syllableCER"] = (
        summary["korean"]["syllableCerEdits"] / summary["korean"]["syllableCerCharacters"]
        if summary["korean"]["syllableCerCharacters"]
        else None
    )
    summary["korean"]["spacingAccuracy"] = (
        summary["korean"]["spaceCorrect"] / summary["korean"]["spaceBoundaries"]
    )
    # Timing is diagnostic metadata, kept separate from metric decisions.
    summary["totalSeconds"] = perf_counter() - started
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
