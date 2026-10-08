"""Bounded 90-page CPU comparison with matched final sizes and resolved effects."""

import argparse
import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image

from training.degrade.demo import render
from training.degrade.presets import replay, run_preset
from training.degrade.sampling import SamplingStats
from training.degrade.smoke import peak_rss_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("work/intermediate-comparison"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    path = Path("configs/degrade/presets.yaml")
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    cv2.setNumThreads(1)
    started = time.perf_counter()
    rows, manifest = [], []
    pages_executed = 0
    stats = SamplingStats(catalog["rejection_rate_limit"])
    for size in ([1280, 1600], [1600, 2500]):
        image, labels = render(dict(size=size, interline=40, systems=3, note_steps=[4, 3, 2, 5, 6]))
        for name, preset in catalog["presets"].items():
            if "resolution_stage_variant" not in preset:
                continue
            for placement in ("before_resize", "after_resize"):
                config = deepcopy(catalog)
                config["presets"][name]["resolution_stage_variant"]["placements"] = [placement]
                timings, baseline_times, differences = [], [], []
                for seed in range(3):
                    start = time.perf_counter()
                    output, moved, record = run_preset(
                        image,
                        labels,
                        np.random.default_rng(seed),
                        config,
                        name,
                        stats,
                        vary_resolution_stage=True,
                    )
                    elapsed = time.perf_counter() - start
                    pages_executed += 1
                    if seed:
                        timings.append(elapsed)
                    if placement == "before_resize":
                        reference = {
                            **record,
                            "operations": [
                                step
                                for step in record["operations"]
                                if not step.get("capture_intermediate")
                            ],
                        }
                        start = time.perf_counter()
                        original, original_labels = replay(
                            image, labels, np.random.default_rng(seed), reference
                        )
                        baseline_elapsed = time.perf_counter() - start
                        pages_executed += 1
                        error = output.astype(np.float64) - original.astype(np.float64)
                        differences.append(
                            dict(
                                seed=seed,
                                final_size=list(output.shape[::-1]),
                                mae=float(np.abs(error).mean()),
                                rmse=float(np.sqrt(np.square(error).mean())),
                                max_abs=float(np.abs(error).max()),
                                p95_abs=float(np.percentile(np.abs(error), 95)),
                                changed_pixel_fraction=float(np.mean(error != 0)),
                                label_point_max_error_px=float(
                                    np.max(np.abs(moved.points - original_labels.points))
                                ),
                            )
                        )
                        if seed:
                            baseline_times.append(baseline_elapsed)
                        if seed == 1 and size[0] == 1280:
                            for suffix, pixels in (
                                ("intermediate", output),
                                ("original", original),
                            ):
                                target = args.output / f"{name}-{suffix}.png"
                                Image.fromarray(pixels).save(target)
                                manifest.append(
                                    dict(
                                        path=target.name,
                                        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                                        bytes=target.stat().st_size,
                                        source="self-authored synthetic schematic",
                                        license="CC0-1.0",
                                        split="synthetic-comparison",
                                    )
                                )
                            (args.output / f"{name}-trace.json").write_text(
                                json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
                            )
                rows.append(
                    dict(
                        preset=name,
                        placement=placement,
                        source_pixels=size[0] * size[1],
                        timed_seconds=timings,
                        pages_per_second=len(timings) / sum(timings),
                        original_timed_seconds=baseline_times,
                        original_pages_per_second=len(baseline_times) / sum(baseline_times)
                        if baseline_times
                        else None,
                        differences=differences,
                    )
                )
    rates = [row["pages_per_second"] for row in rows]
    report = dict(
        scope="synthetic local manual CPU; no real/Dev/sealed data",
        pages_executed=pages_executed,
        threads=1,
        warmups_per_slice=1,
        timed_per_slice=2,
        seeds=[0, 1, 2],
        source_interline_px=40,
        mean_pages_per_core_second=sum(rates) / len(rates),
        slowest_pages_per_second=min(rates),
        performance_status="PASS"
        if min(rates) >= 3 and sum(rates) / len(rates) >= 5
        else "PARTIAL",
        merge_condition=(
            "default variant probability <= 0.3 if slowest < 3; Orchestrator 2026-09-29"
        ),
        default_use_probability=catalog["definitions"]["phone_stage"]["default_use_probability"],
        sampling=stats.summary(),
        wall_seconds=time.perf_counter() - started,
        peak_rss_bytes=peak_rss_bytes(),
        catalog_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        pixel_units=(
            "uint8 levels 0..255; independent noise field sizes with same recorded "
            "initial RNG state; geometry/effect strengths/JPEG parameters fixed"
        ),
        slices=rows,
        manifest=manifest,
        realism_ks_quantiles_auc="NOT_RUN",
        delta_95pct_ci=None,
    )
    (args.output / "comparison.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
