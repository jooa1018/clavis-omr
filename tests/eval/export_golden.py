"""Export measured golden results; never rewrite independent expectations."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

from eval.report import canonical, evaluate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).parent / "fixtures/golden"
    cases = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    started = perf_counter()
    records = []
    for case in cases:
        a = (root / f"{case['case']}.reference.musicxml").read_bytes()
        b = (root / f"{case['case']}.prediction.musicxml").read_bytes()
        report, pairs = evaluate(a, b)
        records.append(
            {
                "case": case["case"],
                "report": report,
                "pairsDigest": hashlib.sha256(canonical(pairs).encode()).hexdigest(),
            }
        )
    artifact = {
        "schema": "clavis-golden-results-0.1",
        "kind": "synthetic-hand-authored-fixtures",
        "datasetEvaluation": "NOT_RUN",
        "sealedAccess": False,
        "cases": records,
        "runtime": {"wallSeconds": perf_counter() - started},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(canonical(artifact), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
