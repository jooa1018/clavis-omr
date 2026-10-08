"""Activated only by the queue's child PYTHONPATH; fail closed on injection errors."""

import os

if "CLAVIS_CPU_LIMIT" in os.environ:
    try:
        from training.jobs.resources import configure

        configure()
    except Exception:
        os._exit(78)
