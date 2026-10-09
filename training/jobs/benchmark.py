"""Run a benchmark with exclusive machine admission and four library threads."""

import argparse
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from training.jobs import store
from training.jobs.model import JobSpec
from training.jobs.runner import execute


def run_benchmark(
    module: str, arguments: list[str], *, wall_seconds: int = 14400
) -> dict[str, Any]:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    spec = JobSpec(
        kind="benchmark",
        module=module,
        arguments=arguments,
        cwd=str(Path.cwd()),
        config={"purpose": "exclusive latency benchmark"},
        seed=0,
        data_digest="0" * 64,
        git_sha=sha,
        threads=4,
        wall_seconds=wall_seconds,
    )
    queue = store.Queue(store.home().parent / "benchmark-runs" / uuid.uuid4().hex)
    identity = queue.submit(spec)
    try:
        lease = store.worker_lock()
        lease.__enter__()
    except OSError:
        result: dict[str, Any] = {
            "jobId": identity,
            "status": "busy",
            "reason": "machine-occupied",
            "benchmark": {"validity": "not-run"},
        }
        queue.record(result)
        queue.update(identity, status="busy", reason="machine-occupied")
        return result
    try:
        row = queue.claim()
        assert row is not None
        result = execute(queue, row, manual=True)
        result["runId"] = queue.root.name
        return result
    finally:
        lease.__exit__(None, None, None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wall-seconds", type=int, default=14400)
    parser.add_argument("module")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    result = run_benchmark(args.module, args.arguments, wall_seconds=args.wall_seconds)
    print(json.dumps(result))
    return 0 if result["status"] == "succeeded" else 75 if result["status"] == "busy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
