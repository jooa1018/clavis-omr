"""Regenerate committed GT schemas; no private files involved."""

import json

from eval.gt import Manifest, Sidecar
from eval.gt.__main__ import REPOSITORY


def main() -> None:
    for name, model in (("gt", Sidecar), ("gt-manifest", Manifest)):
        target = REPOSITORY / "configs" / "eval" / f"{name}.schema.json"
        target.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
