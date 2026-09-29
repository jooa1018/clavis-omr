"""First-PR pair CLI. Dataset/engine runners are separate follow-up work."""

import argparse
from pathlib import Path

from eval.policy import limit
from eval.report import evaluate, write_report


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m eval")
    parser.add_argument("reference", type=Path)
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--confidence", type=Path)
    args = parser.parse_args()
    # Read at most one byte over the projection limit, before allocating a full input.
    data = []
    for path in (args.reference, args.prediction):
        with path.open("rb") as stream:
            data.append(stream.read(limit("maxXmlBytes") + 1))
    confidence = None
    if args.confidence is not None:
        with args.confidence.open("rb") as stream:
            confidence = stream.read(limit("maxXmlBytes") + 1)
    report, pairs = evaluate(data[0], data[1], confidence)
    write_report(report, pairs, args.out)
    return 0 if report["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
