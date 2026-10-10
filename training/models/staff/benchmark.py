"""Queued synthetic strip benchmark; validity is assigned only by W1's monitor."""

import argparse
import hashlib
import json
from pathlib import Path

import cv2

from training.jobs.context import Context
from training.jobs.model import atomic_json
from training.models.staff.smoke import run


def verify_manifest(path: Path, expected_digest: str) -> None:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError("Benchmark manifest changed after registration")
    for item in json.loads(raw)["files"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Expected repository-relative benchmark input")
        if hashlib.sha256(relative.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Benchmark input or measured code changed after registration")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rasters", type=Path, required=True)
    args = parser.parse_args()
    context = Context()
    request = json.loads((context.directory / "request.json").read_text())
    if request.get("kind") != "benchmark" or cv2.getNumThreads() != 4:
        raise ValueError("Requires W1 exclusive four-thread benchmark job")
    verify_manifest(args.manifest, request["data_digest"])
    # A paused bounded smoke restarts in full; timings from different admissions are not pooled.
    result = run(args.root, args.rasters, context.directory / "smoke")
    atomic_json(
        context.directory / "strip-latency.json",
        {
            "scope": result["scope"],
            "opencv_threads": result["opencv_threads"],
            "data_digest": request["data_digest"],
            "slices": result["slices"],
            "validity": "PENDING_RUNNER_REPORT",
            "definition": "First call per detected matched staff; subsequent calls exclude first. "
            "Not a process-cold-start measurement. "
            "Accept only matching W1 benchmark.validity=valid.",
        },
    )


if __name__ == "__main__":
    main()
