"""Activated only by the queue's child PYTHONPATH; fail closed on injection errors."""

import os
import sys

if "CLAVIS_CPU_LIMIT" in os.environ:
    try:
        from training.jobs.resources import configure

        configure()
    except Exception as error:
        print("CLAVIS_BOOTSTRAP_ERROR " + type(error).__name__, file=sys.stderr, flush=True)
        os._exit(78)
