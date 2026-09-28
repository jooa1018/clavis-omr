"""Generate committed JSON Schema snapshots without touching private data."""

import argparse
import json
from pathlib import Path

from clavis.contracts import DOCUMENT_MODELS


def generate(*, check: bool = False) -> None:
    root = Path(__file__).resolve().parents[1] / "src/clavis/contracts/schemas"
    root.mkdir(exist_ok=True)
    for model in DOCUMENT_MODELS:
        schema = model.model_json_schema(by_alias=True)
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        expected = (
            json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        path = root / f"{model.__name__}.json"
        if check:
            if not path.exists() or path.read_bytes() != expected:
                raise ValueError(f"stale schema: {path.name}")
        else:
            path.write_bytes(expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    generate(check=parser.parse_args().check)
