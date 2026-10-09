"""Custodian/local Dev hash producer. Only hashes leave the local process."""

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from eval.gt.__main__ import contained, digest
from eval.integrity.leakage import MELODY, PHASH, SCHEMA, melody_fingerprint, validate
from eval.policy import config
from eval.projection import project
from eval.projection.model import EvaluationUnsupported


def phash_pixels(pixels: NDArray[np.float64]) -> str:
    """Orthonormal 32-point DCT-II, 8x8 low band, median of 63 AC terms."""
    if (
        pixels.shape != tuple(config("hash-limits.json")["phashInputShape"])
        or not np.isfinite(pixels).all()
    ):
        raise ValueError("pHash requires finite 32x32 grayscale pixels")
    indices = np.arange(32)
    frequencies = np.arange(8)[:, None]
    basis = np.cos(np.pi * (2 * indices + 1) * frequencies / 64) * np.sqrt(2 / 32)
    basis[0] = np.sqrt(1 / 32)
    # Centering is mathematically DC-only and keeps constant-image AC exactly zero.
    low = np.round((basis @ (pixels - pixels.mean()) @ basis.T).ravel(), 8)
    threshold = np.median(low[1:])
    bits = low > threshold
    bits[0] = False
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def image_phash(path: Path) -> str:
    limits = config("hash-limits.json")
    if path.stat().st_size > limits["maxImageBytes"]:
        raise ValueError("image byte limit")
    with Image.open(path) as image:
        if (
            image.width * image.height > limits["maxImagePixels"]
            or getattr(image, "n_frames", 1) != 1
        ):
            raise ValueError("image pixel/frame limit")
        pixels = np.asarray(
            image.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64
        )
    return phash_pixels(pixels)


def produce(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if (
        set(manifest) != {"role", "samples"}
        or manifest["role"] not in {"train", "reserved"}
        or not 1 <= len(manifest["samples"]) <= 100
    ):
        raise ValueError("expected 1-100 explicit local samples and role")
    samples = []
    for sample in manifest["samples"]:
        if set(sample) != {"sampleId", "imagePath", "musicXmlPath", "voice"}:
            raise ValueError("invalid local hash manifest fields")
        image = contained(root, sample["imagePath"])
        xml = contained(root, sample["musicXmlPath"])
        if xml.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("XML byte limit")
        score = project(xml.read_bytes())
        notes = []
        for measure in score.measures:
            for event in measure.events:
                if event.kind == "note" and not event.grace and event.voice == sample["voice"]:
                    if event.chord_member:
                        raise EvaluationUnsupported("fingerprint-needs-monophonic-selected-voice")
                    assert event.pitch is not None
                    step, alter, octave = event.pitch
                    if alter.denominator != 1:
                        raise EvaluationUnsupported("microtonal-fingerprint")
                    midi = (
                        12 * (octave + 1)
                        + {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step]
                        + int(alter)
                    )
                    notes.append((midi, event.duration))
        samples.append(
            {
                "sampleId": sample["sampleId"],
                "imageSha256": digest(image),
                "phash": image_phash(image),
                "melodyMinhash": melody_fingerprint(notes),
            }
        )
    inventory = {
        "schema": SCHEMA,
        "role": manifest["role"],
        "phashAlgorithm": PHASH,
        "melodyAlgorithm": MELODY,
        "samples": samples,
    }
    validate(inventory, manifest["role"])
    return inventory
