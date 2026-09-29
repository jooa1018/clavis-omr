"""External-only CPU baseline runner. Never imports baseline code."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from eval.policy import config
from eval.report import canonical


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def command(
    engine: str, image: str, directory: Path, suffix: str, docker: tuple[str, ...] = ("docker",)
) -> list[str]:
    policy = config("baselines.json")
    if engine not in policy["engines"] or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("unknown baseline or unpinned local image ID")
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("runner accepts one raster page per invocation")
    if "," in str(directory):
        raise ValueError("Docker mount path cannot contain comma")
    return [
        *docker,
        "run",
        "--rm",
        "--pull=never",
        "--network=none",
        "--read-only",
        "--memory=" + policy["memory"],
        "--memory-swap=" + policy["memory"],
        f"--cpus={policy['cpus']}",
        "--pids-limit=256",
        "--security-opt=no-new-privileges",
        "--cap-drop=ALL",
        "--cidfile",
        str(directory / "container.id"),
        "--mount",
        f"type=bind,source={directory},target=/work",
        "--workdir=/work",
        "--tmpfs=/tmp:rw,size=512m",
        "--env=HOME=/work/home",
        "--env=CUDA_VISIBLE_DEVICES=",
        "--env=OMP_NUM_THREADS=2",
        "--env=OPENBLAS_NUM_THREADS=2",
        "--env=MKL_NUM_THREADS=2",
        "--env=HF_HUB_OFFLINE=1",
        "--env=TRANSFORMERS_OFFLINE=1",
        image,
        *[
            arg.replace("{input}", "/work/input" + suffix)
            for arg in policy["engines"][engine]["command"]
        ],
    ]


def inspect(engine: str, image: str, docker: tuple[str, ...]) -> dict[str, str]:
    response = subprocess.run(
        [*docker, "image", "inspect", image], check=True, capture_output=True, timeout=30
    )
    infos = json.loads(response.stdout)
    if len(infos) != 1 or infos[0]["Id"] != image:
        raise ValueError("local image digest mismatch")
    labels = infos[0]["Config"].get("Labels") or {}
    if (
        labels.get("org.clavis.baseline") != engine
        or labels.get("org.clavis.version")
        != config("baselines.json")["engines"][engine]["version"]
    ):
        raise ValueError("baseline version provenance missing")
    for key in ("org.clavis.lockDigest", "org.clavis.weightsDigest"):
        if not re.fullmatch(r"[0-9a-f]{64}", labels.get(key, "")):
            raise ValueError("lock and preloaded weights digests required")
    return {
        key: labels[key]
        for key in ("org.clavis.version", "org.clavis.lockDigest", "org.clavis.weightsDigest")
    }


def run(
    engine: str,
    image: str,
    source: Path,
    cache: Path,
    dataset_digest: str,
    docker: tuple[str, ...] = ("docker",),
) -> dict[str, Any]:
    """One page, <=600s, network disabled by Docker; long batches require W1 queue."""
    policy = config("baselines.json")
    if not re.fullmatch(r"[0-9a-f]{64}", dataset_digest):
        raise ValueError("dataset digest required")
    source = source.resolve(strict=True)
    command(engine, image, cache.resolve(), source.suffix.lower(), docker)
    provenance = inspect(engine, image, docker)
    key_data = {
        "engine": engine,
        "image": image,
        "datasetDigest": dataset_digest,
        "inputDigest": file_digest(source),
        "policy": policy,
        "runnerDigest": file_digest(Path(__file__)),
    }
    key = hashlib.sha256(canonical(key_data).encode()).hexdigest()
    directory = cache.resolve() / key
    record = directory / "run.json"
    if record.exists():
        result: dict[str, Any] = json.loads(record.read_text(encoding="utf-8"))
        if any(
            not re.fullmatch(r"movement-[0-9]+\.(musicxml|xml|mxl)", output["file"])
            for output in result["outputs"]
        ):
            raise ValueError("invalid cache output path")
        if result["cacheKey"] != key or any(
            file_digest(directory / o["file"]) != o["sha256"] for o in result["outputs"]
        ):
            raise ValueError("baseline cache corrupted")
        return result
    # An interrupted run is not a complete cache entry; never mix it with a retry.
    directory.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(directory).free < 3 * 1024**3:
        raise ValueError("at least 3 GiB free disk required")
    (directory / "out").mkdir()
    (directory / "home").mkdir()
    staged = directory / ("input" + source.suffix.lower())
    shutil.copyfile(source, staged)
    invocation = command(engine, image, directory, staged.suffix, docker)
    started = time.perf_counter()
    result = {
        "schema": "clavis-baseline-run-1",
        "cacheKey": key,
        "engine": engine,
        "version": policy["engines"][engine]["version"],
        "imageId": image,
        "datasetDigest": dataset_digest,
        "inputDigest": key_data["inputDigest"],
        "provenance": provenance,
        "status": "FAIL",
        "reason": "process-failed",
        "outputs": [],
    }
    try:
        process = subprocess.run(
            invocation,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=int(policy["timeoutSeconds"]),
        )
        result["returnCode"] = process.returncode
        if process.returncode == 0:
            outputs = sorted(
                p
                for p in directory.rglob("*")
                if p.is_file() and p.suffix.lower() in {".musicxml", ".xml", ".mxl"}
            )
            if not outputs:
                result["reason"] = "no-musicxml"
            elif len(outputs) > policy["maxMovements"] or any(
                p.is_symlink()
                or not p.resolve().is_relative_to(directory)
                or p.stat().st_size > policy["maxOutputBytes"]
                for p in outputs
            ):
                result["reason"] = "output-limits"
            else:
                recorded = []
                for index, path in enumerate(outputs):
                    target = directory / f"movement-{index:03}{path.suffix.lower()}"
                    path.rename(target)
                    recorded.append({"file": target.name, "sha256": file_digest(target)})
                result.update(status="PASS", reason="outputs-collected", outputs=recorded)
    except subprocess.TimeoutExpired:
        result["reason"] = "timeout"
    except OSError:
        result["reason"] = "process-or-output-error"
    finally:
        cidfile = directory / "container.id"
        if cidfile.exists():
            cid = cidfile.read_text(encoding="utf-8").strip()
            if re.fullmatch(r"[0-9a-f]{64}", cid):
                try:
                    subprocess.run(
                        [*docker, "rm", "--force", cid],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=30,
                    )
                except (OSError, subprocess.SubprocessError):
                    result.update(status="FAIL", reason="container-cleanup-failed")
        result["elapsedSeconds"] = time.perf_counter() - started
        record.write_text(canonical(result), encoding="utf-8")
    return result
