"""Read evaluator-owned immutable policy files without engine dependencies."""

import json
from pathlib import Path
from typing import Any


def config(name: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "configs" / "eval" / name
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def limit(name: str) -> int:
    return int(config("limits.json")[name])
