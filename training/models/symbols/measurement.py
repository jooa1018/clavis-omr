"""Resumable CPU timing trials; measurement-only, never model selection."""

import argparse
import hashlib
import json
import os
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np
import psutil

from training.data.resources import peak_rss_bytes
from training.jobs.context import Context
from training.jobs.model import atomic_json


def fcn_trial(patches: np.ndarray, config: dict, seed: int) -> dict:
    import torch
    from torch import nn

    if torch.version.cuda is not None:
        raise ValueError("CPU-only torch is required")
    torch.manual_seed(seed)
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
    x = torch.from_numpy(patches.astype(np.float32) / 255)
    y = nn.functional.avg_pool2d(1 - x[:, :1], 4)
    optimizer = torch.optim.SGD(network.parameters(), lr=0.01)
    batch = config["fcn_batch"]

    def step(start: int) -> None:
        optimizer.zero_grad(set_to_none=True)
        loss = nn.functional.binary_cross_entropy_with_logits(
            network(x[start : start + batch]), y[start : start + batch]
        )
        loss.backward()
        optimizer.step()

    for _ in range(config["fcn_warmup_steps"]):
        step(0)
    epochs = []
    for _ in range(config["fcn_epochs"]):
        start = time.perf_counter()
        for index in range(0, len(x), batch):
            step(index)
        epochs.append(time.perf_counter() - start)
    return {
        "fit_seconds": sum(epochs),
        "epoch_seconds": epochs,
        "patch_presentations": len(x) * len(epochs),
        "patch_presentations_per_second": len(x) * len(epochs) / sum(epochs),
        "parameter_count": sum(p.numel() for p in network.parameters()),
        "effective_threads": torch.get_num_threads(),
        "cpu_only": torch.version.cuda is None,
    }


def lgb_trial(patches: np.ndarray, config: dict, seed: int) -> dict:
    import lightgbm as lgb

    x = patches.reshape(len(patches), -1).astype(np.float32) / 255
    density = np.mean(1 - x, axis=1)
    y = (density > np.median(density)).astype(np.int32)
    params = {
        "objective": "binary",
        "verbosity": -1,
        "num_threads": int(os.environ["CLAVIS_CPU_LIMIT"]),
        "deterministic": True,
        "force_col_wise": True,
        "seed": seed,
        "num_leaves": 15,
        "min_data_in_leaf": 4,
        "max_bin": 31,
    }
    lgb.train(params, lgb.Dataset(x, label=y), num_boost_round=1)
    start = time.perf_counter()
    model = lgb.train(params, lgb.Dataset(x, label=y), num_boost_round=config["lgb_rounds"])
    elapsed = time.perf_counter() - start
    return {
        "fit_seconds": elapsed,
        "patch_records_per_fit_second": len(x) / elapsed,
        "patch_rounds_per_second": len(x) * config["lgb_rounds"] / elapsed,
        "boosting_rounds": config["lgb_rounds"],
        "effective_threads": model.params["num_threads"],
        "tree_count": model.num_trees(),
        "cpu_only": model.params.get("device_type", "cpu") == "cpu",
    }


def run(data: Path, config_path: Path, model: str, *, probe: bool = False) -> dict:
    context = Context()
    request = json.loads((context.directory / "request.json").read_text(encoding="utf-8"))
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    manifest_bytes = (data / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["purpose"] != "measurement-only" or config["purpose"] != "measurement-only":
        raise ValueError("Measurement-only inputs required")
    source_digest = manifest.get(
        "source_descriptor_sha256", hashlib.sha256(manifest_bytes).hexdigest()
    )
    if source_digest != request["data_digest"]:
        raise ValueError("Queue data digest mismatch")
    expected = request["config"].get("measurement_config_sha256", manifest["config_sha256"])
    if hashlib.sha256(config_bytes).hexdigest() != expected:
        raise ValueError("Queue measurement configuration mismatch")
    code_digest = request["config"].get("measurement_code_sha256")
    if code_digest and hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != code_digest:
        raise ValueError("Measurement code differs from queued revision")
    if (
        hashlib.sha256((data / "patches.npz").read_bytes()).hexdigest()
        != manifest["patches_sha256"]
    ):
        raise ValueError("Patch cache digest mismatch")
    limit = int(os.environ["CLAVIS_CPU_LIMIT"])
    if not probe and limit not in config["threads"]:
        raise ValueError("Formal comparison requires a queued 4/8 CPU budget")
    with np.load(data / "patches.npz", allow_pickle=False) as arrays:
        patches = arrays["patches"]
    if patches.dtype != np.uint8 or list(patches.shape[1:]) != manifest["patch_shape"]:
        raise ValueError("Patch format mismatch")
    state = context.load() or {"purpose": "measurement-only", "trials": []}
    schedule = [(n, repeat) for n in config["sample_sizes"] for repeat in range(config["repeats"])]
    for n, repeat in schedule[len(state["trials"]) :]:
        if n > len(patches) or n < config["fcn_batch"]:
            raise ValueError("Sample size outside frozen cache")
        if context.stopping():
            return state
        started = time.perf_counter()
        result = (fcn_trial if model == "fcn" else lgb_trial)(
            patches[:n], config, config["seed"] + repeat
        )
        state["trials"].append(
            {
                "sample_records": n,
                "repeat": repeat,
                **result,
                "trial_wall_seconds": time.perf_counter() - started,
                "process_peak_rss_bytes": peak_rss_bytes(),
                "logical_cpu_affinity_count": len(psutil.Process().cpu_affinity()),
            }
        )
        # Each trial starts from a fixed seed. Interrupted trials are rerun in
        # full; completed timings are durable, with no weight checkpoint saved.
        context.save(state)
    result = {
        "status": "PASS",
        "purpose": "measurement-only",
        "model": model,
        "probe": probe,
        "threads": limit,
        "trials": state["trials"],
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "data_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "versions": {name: version(name) for name in ("torch", "lightgbm", "numpy", "scipy")},
        "memory_configuration": config["memory_configuration"],
        "scope": "synthetic compute timing; NOT SYN-Val; NOT recognition accuracy",
        "checkpoints": "progress JSON only; no model weights saved or selected",
    }
    atomic_json(context.directory / "measurement.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("model", choices=("fcn", "lightgbm"))
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    run(args.data, args.config, args.model, probe=args.probe)


if __name__ == "__main__":
    main()
