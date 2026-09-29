"""Authored symbolic oracle, explicitly NOT SYN-Val. W4 invoked as a black box."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from clavis.export.musicxml import write_musicxml
from tests.assemble.helpers import assemble, bar, note, prefix


def oracle_items():
    items = prefix(3)
    items[1] = dict(type="key", fifths=-1)
    return items + [
        bar("repeatStart"),
        note(dur="eighth", pos=5),
        note(dur="eighth", pos=6),
        note(dots=1, pos=7),
        note(dur="eighth", pos=6, tie="start"),
        bar(),
        note(dur="half", pos=6, tie="stop"),
        dict(type="rest", dur="quarter", dots=0, v=1),
        bar("repeatEnd"),
    ]


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
