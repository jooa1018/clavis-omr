"""Authored symbolic oracle, explicitly NOT SYN-Val. W4 invoked as a black box."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from clavis.contracts.lstl import parse
from clavis.export.musicxml import write_musicxml
from tests.assemble.helpers import assemble


def oracle_items():
    data = (Path(__file__).parent / "fixtures" / "oracle.lstl").read_bytes()
    return [item.model_dump(by_alias=True, exclude_none=True) for item in parse(data)]


def run_smoke(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    data, timing = write_musicxml(assemble(oracle_items()).score)
    prediction = output / "prediction.musicxml"
    prediction.write_bytes(data)
    reference = Path(__file__).parent / "fixtures" / "oracle.musicxml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "eval",
            str(reference),
            str(prediction),
            "--out",
            str(output / "evaluation"),
        ],
        check=True,
    )
    (output / "runtime.json").write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
    return json.loads((output / "evaluation" / "report.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    run_smoke(parser.parse_args().out)
