"""Bounded synthetic CPU smoke: 72 pages, one thread, two timing samples per route."""

import argparse
import ctypes
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw

from training.degrade.demo import render
from training.degrade.presets import run_preset


def peak_rss_bytes() -> int:
    """Read process high-water memory without adding a runtime dependency."""
    if sys.platform == "win32":

        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak_rss",
                    "rss",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(Counters),
            ctypes.c_ulong,
        ]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError(ctypes.get_last_error(), "Cannot measure peak working set")
        return int(counters.peak_rss)
    import resource

    return int(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if platform.system() == "Darwin" else 1024)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/degrade/presets.yaml"))
    parser.add_argument("--output", type=Path, default=Path("work/preset-smoke"))
    args = parser.parse_args()
    catalog = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    started = time.perf_counter()
    timings, previews, manifests = [], [], []
    for size in ([1280, 1600], [1600, 2500]):
        image, labels = render(
            {"size": size, "interline": 40, "systems": 3, "note_steps": [4, 3, 2, 5, 6]}
        )
        for name in catalog["presets"]:
            samples = []
            for index in range(3):
                start = time.perf_counter()
                output, _, record = run_preset(
                    image, labels, np.random.default_rng(index), catalog, name
                )
                elapsed = time.perf_counter() - start
                if index:
                    samples.append(elapsed)
            timings.append(
                {
                    "preset": name,
                    "source_pixels": size[0] * size[1],
                    "timed_seconds": samples,
                    "pages_per_second": len(samples) / sum(samples),
                    "truncated": record["truncated"],
                    "illegible_candidate": record["illegible_candidate"],
                    "actual_interline_median": float(np.median(record["actual_interlines"])),
                }
            )
            if size[0] == 1280:
                path = args.output / f"{name}.png"
                Image.fromarray(output).save(path)
                (args.output / f"{name}.json").write_text(
                    json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
                )
                manifests.append(
                    {
                        "path": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "bytes": path.stat().st_size,
                        "source": "self-authored synthetic staff schematic",
                        "license": "CC0-1.0",
                        "split": "synthetic-smoke",
                    }
                )
                preview = Image.fromarray(output)
                preview.thumbnail((300, 270))
                previews.append((name, preview))
    sheet = Image.new("RGB", (1200, 900), "#eeeeee")
    draw = ImageDraw.Draw(sheet)
    for index, (name, preview) in enumerate(previews):
        x, y = (index % 4) * 300, (index // 4) * 300
        draw.text((x + 8, y + 6), name, fill="black")
        sheet.paste(preview, (x, y + 28))
    sheet.save(args.output / "overview.png")
    report = {
        "scope": "synthetic local CPU manual smoke; automatic measurements; no real/sealed data",
        "status": "PARTIAL",
        "reason": "Two timings per slice are not a sustained throughput or realism gate",
        "threads": 1,
        "seeds": [0, 1, 2],
        "warmups_per_slice": 1,
        "timed_per_slice": 2,
        "pages_executed": len(timings) * 3,
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_rss_bytes(),
        "catalog_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
        },
        "slices": timings,
        "manifest": manifests,
        "realism_ks_auc": "NOT_RUN: W4 aggregate statistics/domain-classifier results unavailable",
        "baseline_delta_95pct_ci": None,
    }
    (args.output / "smoke.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
