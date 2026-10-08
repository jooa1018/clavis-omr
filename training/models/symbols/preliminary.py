"""OR-001 measurement-only CPU probes consuming W2 smoke; no model is saved."""

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from importlib.metadata import version
from itertools import product
from pathlib import Path

import numpy as np
from PIL import Image

from training.data.resources import peak_rss_bytes


def fcn_probe(x: np.ndarray, threads: int) -> dict[str, object]:
    """Time ~100k-parameter FCN backward passes on a grayscale proxy target."""
    import torch
    from torch import nn

    if torch.version.cuda is not None:
        raise ValueError("A CPU-only torch wheel is required")
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    torch.manual_seed(6)
    torch.use_deterministic_algorithms(True)
    network = nn.Sequential(
        nn.Conv2d(2, 32, 3, padding=1),
        nn.ReLU(),
        nn.Conv2d(32, 64, 3, padding=1, stride=2),
        nn.ReLU(),
        nn.Conv2d(64, 96, 3, padding=1, stride=2),
        nn.ReLU(),
        nn.Conv2d(96, 32, 3, padding=1),
        nn.ReLU(),
        nn.Conv2d(32, 1, 1),
    )
    # W5 channel is unavailable: duplicate original only for compute measurement.
    pixels = torch.from_numpy(x.reshape(-1, 1, 48, 48))
    inputs = pixels.repeat(1, 2, 1, 1)
    targets = nn.functional.avg_pool2d(1 - pixels, 4)
    optimizer = torch.optim.SGD(network.parameters(), lr=0.01)

    def step(start: int) -> None:
        optimizer.zero_grad(set_to_none=True)
        loss = nn.functional.binary_cross_entropy_with_logits(
            network(inputs[start : start + 8]), targets[start : start + 8]
        )
        loss.backward()
        optimizer.step()

    for _ in range(2):
        step(0)
    started = time.perf_counter()
    for start in range(0, len(x), 8):
        step(start)
    elapsed = time.perf_counter() - started
    return {
        "model": "FCN",
        "parameter_count": sum(p.numel() for p in network.parameters()),
        "patch_shape": [48, 48, 2],
        "fit_seconds": elapsed,
        "unique_patches_per_fit_second": len(x) / elapsed,
        "configuration": {
            "channels": [2, 32, 64, 96, 32, 1],
            "batch_size": 8,
            "warmup_steps": 2,
            "timed_steps": len(x) // 8,
            "optimizer": "SGD",
            "learning_rate": 0.01,
            "deterministic_algorithms": True,
            "seed": 6,
        },
        "versions": {n: version(n) for n in ("torch", "numpy", "resvg-py")},
    }


def worker(smoke: Path, threads: int, model: str) -> dict[str, object]:
    """Time a small surrogate objective; this is not symbol-classifier training."""
    import lightgbm as lgb
    import resvg_py

    if threads not in (4, 8):
        raise ValueError("The preliminary comparison is limited to 4/8 CPU threads")
    if shutil.disk_usage(smoke).free < 3_000_000_000:
        raise ValueError("Free disk is below the project minimum")
    report_bytes = (smoke / "report.json").read_bytes()
    report = json.loads(report_bytes)
    rng = np.random.default_rng(6)
    patches, sources = [], []
    # The first two ordered smoke jobs are predetermined, not selected by accuracy.
    for job in report["jobs"][:2]:
        if job["source"] != "clavis-smoke" or not job["seed"].startswith("train-smoke-"):
            raise ValueError("Only W2 development smoke sources are permitted")
        folder = (smoke / f"{job['seed']}-{job['font']}").resolve()
        if not folder.is_relative_to(smoke.resolve()):
            raise ValueError("Smoke artifact escapes quarantine")
        for name, sha in sorted(job["artifacts"].items()):
            if not name.endswith(".svg.gz") or ".overlay." in name:
                continue
            path = (folder / name).resolve()
            if not path.is_relative_to(folder):
                raise ValueError("Invalid artifact path")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError("Smoke artifact digest mismatch")
            png = resvg_py.svg_to_bytes(
                svg_string=gzip.decompress(raw).decode(),
                width=1200,
                background="white",
                skip_system_fonts=True,
            )
            pixels = np.asarray(Image.open(io.BytesIO(png)).convert("L"))
            ys, xs = np.where(pixels < 128)
            for i in rng.choice(len(xs), size=32, replace=len(xs) < 32):
                x = int(np.clip(xs[i] - 24, 0, pixels.shape[1] - 48))
                y = int(np.clip(ys[i] - 24, 0, pixels.shape[0] - 48))
                patches.append(pixels[y : y + 48, x : x + 48])
            sources.append({"seed": job["seed"], "font": job["font"], "sha256": sha})
    x = np.stack(patches).astype(np.float32).reshape(len(patches), -1) / 255
    common = {
        "threads": threads,
        "unique_patches": len(x),
        "source_artifacts": sources,
        "data_manifest_digest": hashlib.sha256(report_bytes).hexdigest(),
    }
    if model == "fcn":
        measurement = {**common, **fcn_probe(x, threads), "peak_rss_bytes": peak_rss_bytes()}
        if measurement["peak_rss_bytes"] > 3_000_000_000:
            raise MemoryError("OR-001 process RSS exceeded")
        return measurement
    # Ink density is a proxy target only; W2 T2.5 has not supplied symbol labels.
    density = np.mean(1 - x, axis=1)
    y = (density > np.median(density)).astype(np.int32)
    params = {
        "objective": "binary",
        "verbosity": -1,
        "num_threads": threads,
        "deterministic": True,
        "force_col_wise": True,
        "seed": 6,
        "num_leaves": 15,
        "min_data_in_leaf": 4,
        "max_bin": 31,
    }
    lgb.train(params, lgb.Dataset(x, label=y), num_boost_round=1)
    started = time.perf_counter()
    lgb.train(params, lgb.Dataset(x, label=y), num_boost_round=20)
    elapsed = time.perf_counter() - started
    peak = peak_rss_bytes()
    if peak > 3_000_000_000:
        raise MemoryError("OR-001 process RSS exceeded")
    return {
        "model": "LightGBM",
        "threads": threads,
        "unique_patches": len(x),
        "patch_shape": [48, 48, 1],
        "boosting_rounds": 20,
        "fit_seconds": elapsed,
        "unique_patches_per_fit_second": len(x) / elapsed,
        "patch_rounds_per_second": len(x) * 20 / elapsed,
        "peak_rss_bytes": peak,
        "source_artifacts": sources,
        "data_manifest_digest": hashlib.sha256(report_bytes).hexdigest(),
        "versions": {n: version(n) for n in ("lightgbm", "numpy", "resvg-py")},
        "configuration": {
            "lightgbm": params,
            "warmup_rounds": 1,
            "timed_rounds": 20,
            "raster_width": 1200,
            "patches_per_page": 32,
            "patch_size": 48,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("smoke", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker", type=int, choices=(4, 8))
    parser.add_argument("--model", choices=("fcn", "lightgbm"), default="lightgbm")
    args = parser.parse_args()
    if args.worker:
        result = worker(args.smoke, args.worker, args.model)
    else:
        started = time.perf_counter()
        measurements = []
        for model, threads in product(("lightgbm", "fcn"), (4, 8)):
            env = {
                **os.environ,
                "OMP_NUM_THREADS": str(threads),
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": str(threads),
            }
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "training.models.symbols.preliminary",
                    str(args.smoke),
                    str(args.output),
                    "--worker",
                    str(threads),
                    "--model",
                    model,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
            measurements.append(json.loads(process.stdout))
        result = {
            "status": "PARTIAL",
            "label": "예비 / preliminary / measurement-only",
            "scope": "local Windows CPU; W2 synthetic development smoke; NOT SYN-Val",
            "objective": (
                "ink-density / dense grayscale proxy; NOT symbol labels; "
                "no W5 normalization; FCN channels duplicated"
            ),
            "checkpoint": "none; never eligible for evaluation, selection, or engine use",
            "seed": 6,
            "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "measurements": measurements,
            "wall_seconds": time.perf_counter() - started,
            "limitations": [
                "single brief trial per setting; shared laptop; no sustained thermal test",
                "not a four-hour extrapolation; feature/label semantics are provisional",
            ],
            "formal_measurement": "T1.9 single queue, 01:00–07:00; not scheduled here",
        }
        result["configuration_digest"] = hashlib.sha256(
            json.dumps([m["configuration"] for m in measurements], sort_keys=True).encode()
        ).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
