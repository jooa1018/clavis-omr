"""Explicit geometry registries; JSON syntax is a YAML subset (no YAML runtime)."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeometryConfig:
    values: dict[str, float]
    enabled: frozenset[str]

    def __getitem__(self, key: str) -> float:
        return self.values[key]


def load_config(directory: Path | None = None) -> GeometryConfig:
    """Load a caller-supplied bundle, or the repository development registry."""
    directory = directory or Path(__file__).resolve().parents[3] / "configs" / "geometry"
    entries = json.loads((directory / "constants.yaml").read_text(encoding="utf-8"))
    rules = json.loads((directory / "rules.yaml").read_text(encoding="utf-8"))
    return GeometryConfig(
        {entry["name"]: float(entry["value"]) for entry in entries},
        frozenset(rule["id"] for rule in rules if rule["enabled"]),
    )
