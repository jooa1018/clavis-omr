"""Generate the versioned head-index vocabulary from the approved item schemas."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from clavis.contracts.lstl import VERSION
from clavis.contracts.lstl.automaton import ITEM


def document() -> dict[str, Any]:
    heads: dict[str, list[Any]] = {}
    for definition in ITEM.json_schema()["$defs"].values():
        for name, field in definition["properties"].items():
            if "anyOf" in field:
                field = next(v for v in field["anyOf"] if v.get("type") != "null")
            if "enum" in field:
                values = field["enum"]
            elif "const" in field:
                values = [field["const"]]
            elif field.get("type") == "boolean":
                values = [False, True]
            elif "minimum" in field and "maximum" in field:
                values = list(range(field["minimum"], field["maximum"] + 1))
            elif name == "numbers":
                # CONTRACTS 4.4 head only: bit masks for ending numbers 1..4.
                # The wire model/text retains JSON lists, not these integer masks.
                values = list(range(1, 16))
            else:
                raise ValueError(f"unbounded vocabulary: {name}")
            bucket = heads.setdefault(name, [])
            for value in values:
                if value not in bucket:
                    bucket.append(value)
    payload = json.dumps(heads, sort_keys=True, separators=(",", ":")).encode()
    return {"version": VERSION, "sha256": hashlib.sha256(payload).hexdigest(), "heads": heads}


def generate(*, check: bool = False) -> None:
    path = (
        Path(__file__).resolve().parents[1] / "src/clavis/contracts/lstl" / f"{VERSION}-vocab.json"
    )
    expected = (json.dumps(document(), sort_keys=True, indent=2) + "\n").encode()
    if check:
        if path.read_bytes() != expected:
            raise ValueError("stale LSTL vocabulary")
    else:
        path.write_bytes(expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    generate(check=parser.parse_args().check)
