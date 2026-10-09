"""Cooperative, atomic checkpoint protocol for queue clients."""

import json
import os
from pathlib import Path
from typing import Any

from training.jobs.model import atomic_json


class Context:
    def __init__(self) -> None:
        self.directory = Path(os.environ["CLAVIS_JOB_DIR"])
        self.digest = os.environ["CLAVIS_JOB_DIGEST"]
        self.checkpoint = self.directory / "checkpoint.json"

    def stopping(self) -> bool:
        return (self.directory / "stop").exists()

    def load(self) -> dict[str, Any] | None:
        if not self.checkpoint.exists():
            return None
        value = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        if value["jobDigest"] != self.digest:
            raise ValueError("checkpoint job digest mismatch")
        return dict(value["state"])

    def save(self, state: dict[str, Any]) -> None:
        atomic_json(self.checkpoint, {"jobDigest": self.digest, "state": state})
