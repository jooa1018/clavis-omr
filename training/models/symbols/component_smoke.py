"""Record authored component smoke counts; never a W4 accuracy evaluator."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2

from clavis.contracts import canonical_json
from clavis.contracts.symbols import SymbolGraph
from clavis.symbols.reading import draft_reading
from tests.symbols.test_baseline import PRODUCER, graph, run_detection, scene
from training.data.resources import peak_rss_bytes


def counts(result: SymbolGraph) -> dict[str, int]:
    classes = [s.class_top_k[0][0] for s in result.symbols]
    return {
        "symbols": len(classes),
        "heads": classes.count("noteheadFilled"),
        "stems": classes.count("stem"),
        "bars": classes.count("barline"),
        "relations": len(result.relations),
        "rejected": len(result.rejected_candidates),
        "positions": sum(s.pos_top_k is not None for s in result.symbols),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prior = cv2.getNumThreads()
    timings, digests = [], []
    image, bank = scene()
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for repeat in range(3):
                started = time.perf_counter()
                result = run_detection(image, bank)
                timings.append(
                    {"threads": threads, "repeat": repeat, "seconds": time.perf_counter() - started}
                )
                digests.append(hashlib.sha256(canonical_json(result)).hexdigest())
        cv2.setNumThreads(1)
        ablations = {"all_enabled": counts(run_detection(image, bank))}
        for rule in ("SYM-TEMPLATE-001", "SYM-VLINE-001", "SYM-POS-001", "SYM-REL-001"):
            ablations[rule] = counts(run_detection(image, bank, disabled=frozenset([rule])))
        scaled = []
        for scale in (0.8, 1.0, 1.25):
            scaled_image, scaled_bank = scene(scale)
            scaled.append(
                {
                    "scale": scale,
                    **counts(
                        run_detection(
                            scaled_image, scaled_bank, staff_space=16 * scale, v_top=96 * scale
                        )
                    ),
                }
            )
        reading = draft_reading(graph(), PRODUCER)
        items = [h.items[0] for h in reading.lattice.hypotheses]
        report = {
            "status": "PASS",
            "scope": "authored component mocks; NOT SYN-Val; NOT recognition accuracy",
            "determinism": {"trials": len(digests), "unique_digests": len(set(digests))},
            "timings": timings,
            "scaled_mock_counts": scaled,
            "ablation_component_counts": ablations,
            "reading": {
                "hypotheses": len(reading.lattice.hypotheses),
                "stem_evidence_variants": len({tuple(i.symbol_ids) for i in items}),
                "pos_alternatives": items[0].attr_top_k["pos"],
                "dots_alternatives": items[0].attr_top_k["dots"],
                "duration_distributions": [i.attr_top_k["dur"] for i in items],
                "disabled_reading_items": len(
                    draft_reading(graph(), PRODUCER, enabled=False).lattice.hypotheses[0].items
                ),
                "disabled_duration_items": len(
                    draft_reading(graph(), PRODUCER, durations_enabled=False)
                    .lattice.hypotheses[0]
                    .items
                ),
            },
            "oracle_at_k": "NOT_RUN: no labeled evaluation set / W4 symbol metric",
            "reading_IER": "NOT_RUN: no W2 LSTL / W4 reading metric",
            "peak_rss_bytes": peak_rss_bytes(),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(report))
    finally:
        cv2.setNumThreads(prior)


if __name__ == "__main__":
    main()
