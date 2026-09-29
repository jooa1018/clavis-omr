"""Measured mutation evidence, never a generator of expected test values."""

import sys
from pathlib import Path

from eval.aggregate import aggregate
from eval.report import canonical, evaluate
from tests.eval.test_extended import MUTATIONS, page


def main() -> None:
    evidence = {
        "mutationCount": len(MUTATIONS),
        "mutations": [
            {"name": name, "report": evaluate(reference, prediction)[0]}
            for name, reference, prediction, *_ in MUTATIONS
        ],
        "pairedSynthetic": aggregate(
            [page(i, 1) for i in range(5)], [page(i, 0) for i in range(5)]
        ),
    }
    Path(sys.argv[1]).write_text(canonical(evidence), encoding="utf-8")


if __name__ == "__main__":
    main()
