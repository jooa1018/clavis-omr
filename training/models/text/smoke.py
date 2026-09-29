"""Synthetic tensor smoke, NOT SYN-Val and NOT image/OCR accuracy evaluation."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from clavis.text.ctc import CtcLimits, greedy_observation


def run(root: Path) -> dict[str, object]:
    """Exercise CTC blank/repeat paths without a font, image, or pretrained model."""
    values = {
        entry["name"]: entry["value"]
        for entry in json.loads((root / "configs/text/constants.yaml").read_text(encoding="utf-8"))
    }
    limits = CtcLimits(
        *(values[f"text.ctc.{key}"] for key in ("max_frames", "max_classes", "max_cells"))
    )
    rules = json.loads((root / "configs/text/rules.yaml").read_text(encoding="utf-8"))
    enabled = rules[0]["enabled"]
    words = ("", "a", "aa", "aba", "book", "hello", "가", "가가", "가나다", "나나", "ab가", "  ")
    exact = 0
    repeats_identical = True
    disabled_abstentions = 0
    for word in words:
        alphabet = ("", *sorted(set(word)))
        rows = []
        for char in word:
            row = [float(token == char) for token in alphabet]
            rows.extend([row, row, [float(i == 0) for i in range(len(alphabet))]])
        observations = [
            greedy_observation(rows, alphabet, blank_index=0, limits=limits, enabled=enabled)
            for _ in range(3)
        ]
        exact += int(observations[0] is not None and observations[0].text == word)
        repeats_identical &= all(item == observations[0] for item in observations)
        disabled_abstentions += int(
            greedy_observation(rows, alphabet, blank_index=0, limits=limits, enabled=False) is None
        )
    return {
        "scope": "synthetic-CTC-tensor-tool-test; SYN-Val 아님; image OCR accuracy 아님",
        "cases": len(words),
        "exactTextMatches": exact,
        "exactMatchRate": exact / len(words),
        "threeRepeatsIdentical": repeats_identical,
        "ruleDisabledAbstentions": disabled_abstentions,
        "pretrainedModel": "NOT_RUN",
        "onnxRuntimeThreadDeterminism": "NOT_RUN",
        "dev": "NOT_RUN",
        "sealed": "NOT_ACCESSED",
        "renderedImages": 0,
        "training": "NOT_RUN",
        "confidenceInterval": "NOT_APPLICABLE_tool_test",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter()
    result = run(Path(__file__).resolve().parents[3])
    result["wallSeconds"] = perf_counter() - started
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
