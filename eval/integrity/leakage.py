"""Hash-only training admission. No source image, GT or sealed paths are opened."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA = "clavis-hash-inventory-1"
MELODY = "interval-rhythm-ngram4-minhash64-sha256-v1"
PHASH = "phash-dct32-low8-median63-v1"


def melody_fingerprint(notes: list[tuple[int, Fraction]]) -> list[str]:
    """Transpose/tempo invariant adjacent intervals + rational duration ratios.

    Four-note shingles; short melodies use the complete available sequence.
    SHA256 with 64 fixed permutation labels gives a deterministic MinHash sketch.
    This accepts symbolic notes supplied by the caller, never reads GT itself.
    """
    if not notes or any(d <= 0 for _, d in notes):
        raise ValueError("empty melody or nonpositive duration")
    tokens = [f"{b[0] - a[0]}:{b[1] / a[1]}" for a, b in zip(notes, notes[1:], strict=False)]
    size = min(3, len(tokens))
    shingles = {"|".join(tokens[i : i + size]) for i in range(max(1, len(tokens) - size + 1))}
    return [
        min(hashlib.sha256(f"{MELODY}:{i}:{s}".encode()).hexdigest() for s in shingles)
        for i in range(64)
    ]


def validate(value: Any, role: str) -> list[dict[str, Any]]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "role", "phashAlgorithm", "melodyAlgorithm", "samples"}
        or value["schema"] != SCHEMA
        or value["role"] != role
        or value["phashAlgorithm"] != PHASH
        or value["melodyAlgorithm"] != MELODY
        or not isinstance(value["samples"], list)
    ):
        raise ValueError("inventory format or algorithm mismatch")
    ids: set[str] = set()
    for sample in value["samples"]:
        if not isinstance(sample, dict) or set(sample) != {
            "sampleId",
            "imageSha256",
            "phash",
            "melodyMinhash",
        }:
            raise ValueError("invalid sample fields; source paths are not accepted")
        if (
            not isinstance(sample["sampleId"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", sample["sampleId"])
            or sample["sampleId"] in ids
        ):
            raise ValueError("invalid or duplicate sample identifier")
        ids.add(sample["sampleId"])
        for name, length in (("imageSha256", 64), ("phash", 16)):
            if not isinstance(sample[name], str) or not re.fullmatch(
                "[0-9a-f]{" + str(length) + "}", sample[name]
            ):
                raise ValueError("missing or invalid image hash")
        sketch = sample["melodyMinhash"]
        if (
            not isinstance(sketch, list)
            or len(sketch) != 64
            or any(not isinstance(x, str) or not re.fullmatch(r"[0-9a-f]{64}", x) for x in sketch)
        ):
            raise ValueError("missing or invalid melody fingerprint")
    return list(value["samples"])


def check(train: Any, reserved: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates, protected = validate(train, "train"), validate(reserved, "reserved")
    conflicts: list[dict[str, Any]] = []
    excluded: set[str] = set()
    for sample in candidates:
        for reference in protected:
            distance = (int(sample["phash"], 16) ^ int(reference["phash"], 16)).bit_count()
            reasons = []
            if sample["imageSha256"] == reference["imageSha256"]:
                reasons.append("image-sha256")
            if distance <= 6:
                reasons.append("phash-distance-le6")
            if sample["melodyMinhash"] == reference["melodyMinhash"]:
                reasons.append("melody-minhash-duplicate")
            if reasons:
                excluded.add(sample["sampleId"])
                # Reserved IDs and hashes are deliberately omitted from shared reports.
                conflicts.append({"sampleId": sample["sampleId"], "reasons": reasons})
    complete = bool(candidates and protected)
    accepted = [s for s in candidates if s["sampleId"] not in excluded] if complete else []
    report = {
        "schema": "clavis-leakage-report-1",
        "status": "NOT_RUN" if not complete else "FAIL" if conflicts else "PASS",
        "trainCount": len(candidates),
        "reservedCount": len(protected),
        "excludedCount": len(excluded),
        "admittedCount": len(accepted),
        "conflicts": conflicts,
    }
    return report, {**train, "samples": accepted}


def main() -> int:
    from eval.integrity.protection import admit

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--reserved", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--admitted", type=Path, required=True)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.train, args.reserved, args.out, args.admitted)}) != 4:
        parser.error("input and output paths must be distinct")
    report: dict[str, Any]
    admitted: dict[str, Any]
    try:
        report, admitted = admit(
            json.loads(args.train.read_text(encoding="utf-8")),
            json.loads(args.reserved.read_text(encoding="utf-8")),
        )
    except (ValueError, OSError):
        report, admitted = {"status": "ERROR", "reason": "invalid-inventory"}, {"samples": []}
    for path, value in ((args.out, report), (args.admitted, admitted)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    return {"PASS": 0, "NOT_RUN": 2}.get(report["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
