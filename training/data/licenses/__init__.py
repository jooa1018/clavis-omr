"""Fail-closed source usage checks; melody admission is a separate W4 gate."""

import json
from pathlib import Path


def require_use(source_id: str, purpose: str) -> None:
    """Reject unknown, pending, or forbidden source uses."""
    registry = json.loads(Path(__file__).with_name("sources.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in registry["sources"]}
    entry = entries.get(source_id)
    if entry is None or entry["status"] != "verified" or purpose not in entry["allowed_uses"]:
        raise ValueError("Source use is not verified and permitted")
