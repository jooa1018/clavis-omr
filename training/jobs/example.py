"""Tiny synthetic checkpoint example; performs no training or image processing."""

import json
import os
import subprocess
import sys
import time

import psutil

from training.jobs.context import Context
from training.jobs.model import atomic_json


def main() -> None:
    context = Context()
    request = json.loads((context.directory / "request.json").read_text(encoding="utf-8"))
    count = request["config"].get("steps", 10)
    if request["config"].get("probe"):
        child = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "import json,psutil,os; print(json.dumps({'cpus':psutil.Process().cpu_affinity(),"
                "'omp':os.environ['OMP_NUM_THREADS'],'priority':int(psutil.Process().nice())}))",
            ],
            text=True,
        )
        atomic_json(
            context.directory / "probe.json",
            {
                "cpus": psutil.Process().cpu_affinity(),
                "omp": os.environ["OMP_NUM_THREADS"],
                "priority": int(psutil.Process().nice()),
                "child": json.loads(child),
            },
        )
    state = context.load() or {"step": 0, "total": 0}
    while state["step"] < count:
        if context.stopping():
            return
        state["total"] += state["step"]
        state["step"] += 1
        context.save(state)
        time.sleep(0.05)


if __name__ == "__main__":
    main()
