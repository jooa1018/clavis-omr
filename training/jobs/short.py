"""OR-005: run one bounded Python module in a shared development slot."""

import argparse
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from training.jobs import store
from training.jobs.model import JobSpec
from training.jobs.runner import execute
from training.jobs.slots import configure_slots, short_slot, slot_count

THREADS = 2
WALL_SECONDS = 600
MAX_ITEMS = 100


def run_short(
    module: str,
    arguments: list[str],
    *,
    wall_seconds: int = WALL_SECONDS,
    items: int = 0,
    seed: int = 0,
    data_digest: str = "0" * 64,
) -> dict[str, Any]:
    if not 1 <= wall_seconds <= WALL_SECONDS or not 0 <= items <= MAX_ITEMS:
        raise ValueError("OR-001 requires <=600 seconds and <=100 rendered items/images")
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    spec = JobSpec(
        module=module,
        arguments=arguments,
        cwd=str(Path.cwd()),
        config={"purpose": "OR-005 manual short run", "declaredItems": items},
        seed=seed,
        data_digest=data_digest,
        git_sha=sha,
        threads=THREADS,
        wall_seconds=wall_seconds,
    )
    with short_slot() as index:
        queue = store.Queue(store.home().parent / "short-runs" / uuid.uuid4().hex)
        identity = queue.submit(spec)
        row = queue.claim()
        assert row is not None
        result = execute(queue, row, manual=True)
        # Request/arguments and raw child output remain local; print aggregate evidence only.
        return {
            "status": result["status"],
            "reason": result["reason"],
            "slot": index,
            "runId": queue.root.name,
            "jobId": identity,
            "wallSeconds": result["wallSeconds"],
            "cpuSecondsSampled": result["cpuSecondsSampled"],
            "peakRssBytesSampled": result["peakRssBytesSampled"],
            "cpuLimit": result["cpuLimit"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("configure").add_argument("--slots", type=int, required=True)
    commands.add_parser("status")
    run = commands.add_parser("run")
    run.add_argument("--wall-seconds", type=int, default=WALL_SECONDS)
    run.add_argument("--items", type=int, default=0)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--data-digest", default="0" * 64)
    run.add_argument("module")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == "configure":
            configure_slots(args.slots)
            result: dict[str, Any] = {"status": "configured", "slots": slot_count()}
        elif args.action == "status":
            result = {"status": "configured", "slots": slot_count()}
        else:
            result = run_short(
                args.module,
                args.arguments,
                wall_seconds=args.wall_seconds,
                items=args.items,
                seed=args.seed,
                data_digest=args.data_digest,
            )
    except OSError:
        print(json.dumps({"status": "not-started", "reason": "slot-or-worker-unavailable"}))
        return 75
    except (ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        print(json.dumps({"status": "not-started", "reason": "invalid-request-or-config"}))
        return 2
    print(json.dumps(result))
    return 0 if result["status"] in {"configured", "succeeded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
