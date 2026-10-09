"""Repeat platform tests while two other bounded short slots remain active."""

import json
import subprocess
import threading
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from training.jobs.model import JobSpec, atomic_json
from training.jobs.runner import execute
from training.jobs.slots import short_slot
from training.jobs.store import Queue


def task(root: Path, sha: str, module: str, args: list[str]) -> dict[str, Any]:
    queue = Queue(root)
    queue.submit(
        JobSpec(
            module=module,
            arguments=args,
            cwd=str(Path.cwd()),
            config={"purpose": "synthetic platform concurrency validation"},
            seed=0,
            data_digest="0" * 64,
            git_sha=sha,
            threads=2,
            wall_seconds=600,
        )
    )
    row = queue.claim()
    assert row is not None
    return execute(queue, row, manual=True)


def main() -> int:
    root = Path("work/platform-stress") / uuid.uuid4().hex
    root.mkdir(parents=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    rounds = []
    # These are the real machine slots, not the isolated locks used by unit tests.
    with ExitStack() as leases, ThreadPoolExecutor(max_workers=2) as pool:
        try:
            indices = [leases.enter_context(short_slot()) for _ in range(3)]
        except OSError:
            print(json.dumps({"status": "not-started", "reason": "three-slots-unavailable"}))
            return 75
        for index in range(20):
            directory = root / str(index)
            directory.mkdir()
            controls = [directory / str(worker) for worker in range(2)]
            for control in controls:
                control.mkdir()
            companions = [
                pool.submit(
                    task,
                    control / "queue",
                    sha,
                    "tests.platform.load_companion",
                    [str(control.resolve())],
                )
                for control in controls
            ]
            result: dict[str, Any] = {"round": index + 1, "slots": indices}
            try:
                while not all((control / "ready").exists() for control in controls):
                    if any(future.done() for future in companions):
                        raise RuntimeError("companion stopped before readiness")
                    threading.Event().wait(0.05)
                xml = directory / "tests.xml"
                result["tests"] = task(
                    directory / "test-queue",
                    sha,
                    "pytest",
                    ["tests/platform", "-q", "--junitxml=" + str(xml)],
                )
                result["companionsAliveAtEnd"] = all(not f.done() for f in companions)
                if xml.exists():
                    suite = ET.parse(xml).getroot().find("testsuite")
                    assert suite is not None
                    result["counts"] = {
                        key: int(suite.attrib[key])
                        for key in ("tests", "failures", "errors", "skipped")
                    }
            finally:
                for control in controls:
                    (control / "stop").touch()
                result["companions"] = [future.result() for future in companions]
            counts = result.get("counts", {})
            result["passed"] = (
                result["tests"]["status"] == "succeeded"
                and result["companionsAliveAtEnd"]
                and all(v["status"] == "succeeded" for v in result["companions"])
                and counts.get("tests", 0) > 0
                and all(counts.get(key) == 0 for key in ("failures", "errors", "skipped"))
            )
            rounds.append(result)
            atomic_json(root / "result.json", {"rounds": rounds, "gitSha": sha})
            print(
                json.dumps(
                    {
                        "round": index + 1,
                        "passed": result["passed"],
                        "counts": counts,
                        "evidence": root.as_posix(),
                    }
                ),
                flush=True,
            )
            if not result["passed"]:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
