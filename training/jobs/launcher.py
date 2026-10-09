"""Keep child work gated until registered; stop it if the queue owner dies."""

import json
import os
import runpy
import sys
import threading
import time
from pathlib import Path

import psutil


def alive(pid: int, born: float) -> bool:
    try:
        return psutil.Process(pid).create_time() == born
    except psutil.NoSuchProcess:
        return False


def kill_tree(process: psutil.Process) -> None:
    try:
        children = process.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for child in [*reversed(children), process]:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs([*children, process], timeout=3)


def main() -> int:
    directory = Path(os.environ["CLAVIS_JOB_DIR"])
    parent = int(os.environ["CLAVIS_RUNNER_PID"])
    born = float(os.environ["CLAVIS_RUNNER_BORN"])
    while not (directory / "go").exists():
        if not alive(parent, born):
            return 1
        time.sleep(0.05)
    spec = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    os.chdir(spec["cwd"])

    def watch_parent() -> None:
        while alive(parent, born):
            time.sleep(0.1)
        kill_tree(psutil.Process())

    threading.Thread(target=watch_parent, daemon=True).start()
    sys.argv = [spec["module"], *spec["arguments"]]
    runpy.run_module(spec["module"], run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
