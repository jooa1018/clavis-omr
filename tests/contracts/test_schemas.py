"""Bootstrap slot: T1.2 replaces this skip with model/schema/fixture checks."""

from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


def test_committed_schemas_are_valid() -> None:
    import json

    root = Path(__file__).resolve().parents[2]
    schemas = sorted((root / "src/clavis/contracts/schemas").glob("*.json"))
    if not schemas:
        pytest.skip("NOT_RUN: contract implementation and fixtures belong to T1.2")
    for schema in schemas:
        Draft202012Validator.check_schema(json.loads(schema.read_text(encoding="utf-8")))
