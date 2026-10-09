"""Synthetic CPU activity held by explicit ready/stop files for slot stress tests."""

import hashlib
import sys
import threading
from pathlib import Path

from training.jobs.context import Context


def main():
    directory = Path(sys.argv[1])
    stop = threading.Event()
    context = Context()

    def work():
        payload = b"synthetic-platform-load" * 4096
        while not stop.is_set():
            hashlib.sha256(payload).digest()
            stop.wait(0.001)

    workers = [threading.Thread(target=work) for _ in range(2)]
    for worker in workers:
        worker.start()
    (directory / "ready").touch()
    try:
        while not (directory / "stop").exists() and not context.stopping():
            stop.wait(0.05)
    finally:
        stop.set()
        for worker in workers:
            worker.join()


if __name__ == "__main__":
    main()
