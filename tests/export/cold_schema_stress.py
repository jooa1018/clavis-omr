"""Opt-in functional stress reproduction; three W1 slots, not a latency benchmark."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from threading import Barrier

from training.jobs.model import atomic_json
from training.jobs.short import run_short
from training.jobs.slots import short_slot

TARGET = "tests/export/test_musicxml.py::test_cold_schema_load_without_network_and_instance_hints"


def load(directory: Path, index: int) -> None:
    barrier = Barrier(3)

    def compute() -> int:
        block = bytes(262144)
        iterations = 0
        barrier.wait()
        while not (directory / "stop").exists():
            hashlib.sha256(block).digest()
            iterations += 1
        return iterations

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(compute) for _ in range(2)]
        barrier.wait()
        started = time.monotonic_ns()
        atomic_json(directory / f"load-{index}-ready.json", {"startedNs": started})
        iterations = [future.result() for future in futures]
    atomic_json(
        directory / f"load-{index}-finished.json",
        {"startedNs": started, "finishedNs": time.monotonic_ns(), "iterations": iterations},
    )


def redact(text: str) -> str:
    for path, label in ((Path.cwd(), "<repo>"), (Path.home(), "<user-profile>")):
        for spelling in (str(path), path.as_posix()):
            text = text.replace(spelling, label)
    return text


def probe(directory: Path) -> int:
    attempts = []
    for number in range(1, 11):
        junit = directory / f"attempt-{number:02}.xml"
        started = time.monotonic_ns()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", TARGET, "-q", f"--junitxml={junit}"],
            capture_output=True,
            text=True,
        )
        row = {
            "iteration": number,
            "startedNs": started,
            "finishedNs": time.monotonic_ns(),
            "exitCode": result.returncode,
        }
        if junit.exists():
            suite = ET.parse(junit).getroot().find("testsuite")
            assert suite is not None, "pytest JUnit has no testsuite"
            row["tests"] = {k: suite.get(k) for k in ("tests", "failures", "errors", "skipped")}
        if result.returncode:
            row["failure"] = redact(result.stdout + "\n" + result.stderr)
        attempts.append(row)
        atomic_json(directory / "attempts.json", {"attempts": attempts})
    return int(any(row["exitCode"] for row in attempts))


def coordinate(directory: Path) -> int:
    # Admission only. Each subsequent worker independently acquires a real W1 slot.
    try:
        with ExitStack() as stack:
            for _ in range(3):
                stack.enter_context(short_slot())
    except OSError:
        print(json.dumps({"status": "not-started", "reason": "three-slots-unavailable"}))
        return 75
    directory.mkdir(parents=True, exist_ok=False)
    module = "tests.export.cold_schema_stress"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(run_short, module, ["load", "--out", str(directory), "--index", str(i)])
            for i in (1, 2)
        ]
        test_result = {"status": "not-started", "reason": "load-not-ready"}
        try:
            while not all((directory / f"load-{i}-ready.json").exists() for i in (1, 2)):
                if any(future.done() for future in futures):
                    break
                time.sleep(0.1)
            else:
                print(
                    "Two CPU load slots ready; starting ten cold-schema pytest invocations.",
                    flush=True,
                )
                test_result = run_short(module, ["probe", "--out", str(directory)])
        except OSError:
            test_result = {"status": "not-started", "reason": "probe-slot-unavailable"}
        finally:
            (directory / "stop").touch()
            loads = []
            for future in futures:
                try:
                    loads.append(future.result())
                except OSError:
                    loads.append({"status": "not-started", "reason": "load-slot-unavailable"})
    attempts_path = directory / "attempts.json"
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else {"attempts": []}
    intervals = [
        json.loads(path.read_text())
        for i in (1, 2)
        if (path := directory / f"load-{i}-finished.json").exists()
    ]
    for row in attempts["attempts"]:
        row["bothLoadsOverlap"] = all(
            load["startedNs"] <= row["startedNs"] < row["finishedNs"] <= load["finishedNs"]
            for load in intervals
        )
    successful = (
        test_result["status"] == "succeeded"
        and all(row["status"] == "succeeded" for row in loads)
        and len({row["slot"] for row in [*loads, test_result]}) == 3
        and len(intervals) == 2
        and len(attempts["attempts"]) == 10
        and all(
            row["exitCode"] == 0
            and row["bothLoadsOverlap"]
            and row.get("tests") == {"tests": "1", "failures": "0", "errors": "0", "skipped": "0"}
            for row in attempts["attempts"]
        )
        and all(all(count > 0 for count in load["iterations"]) for load in intervals)
    )
    report = {
        "status": "PASS" if successful else "FAIL",
        "scope": "synthetic CPU slot contention; functional test only; not latency benchmark",
        "target": TARGET,
        "attempts": attempts["attempts"],
        "probeSlot": test_result,
        "loadSlots": loads,
        "loadIntervals": intervals,
    }
    atomic_json(directory / "report.json", report)
    print(json.dumps(report), flush=True)
    return 0 if successful else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["load", "probe", "coordinate"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--index", type=int, choices=(1, 2))
    args = parser.parse_args()
    if args.mode == "load":
        load(args.out, args.index)
    else:
        raise SystemExit(probe(args.out) if args.mode == "probe" else coordinate(args.out))
