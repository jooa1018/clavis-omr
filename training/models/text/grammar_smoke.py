"""Self-authored symbolic smoke, NOT SYN-Val and NOT OCR accuracy."""

import argparse
import json
from pathlib import Path

from clavis.text.chord import ChordGrammar


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    catalog = root / "configs/text/rules.yaml"
    limits = {
        r["name"].removeprefix("text.grammar."): r["value"]
        for r in json.loads((root / "configs/text/constants.yaml").read_text())
        if r["name"].startswith("text.grammar.")
    }
    cases = [
        (root + suffix, root + canonical)
        for root in ("C", "F#", "Bb")
        for suffix, canonical in (
            ("M7", "maj7"),
            ("Δ9", "maj9"),
            ("△⁷", "maj7"),
            ("ø", "m7b5"),
            ("minMaj7", "mMaj7"),
            ("sus", "sus4"),
            ("7(#11,b9)", "7b9#11"),
            ("6/9/E", "6/9/E"),
            ("-7", "m7"),
            ("°7", "dim7"),
        )
    ]
    rules = json.loads(catalog.read_text(encoding="utf-8"))
    results = {}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for flag in (
        None,
        "TEXT-GRAMMAR-001",
        "TEXT-NORMALIZE-001",
        "TEXT-GLYPH-001",
        "TEXT-CONSUMER-001",
    ):
        modified = [dict(r, enabled=False) if r["id"] == flag else r for r in rules]
        config = args.out.parent / "grammar-smoke-rules.json"
        config.write_text(json.dumps(modified), encoding="utf-8")
        grammar = ChordGrammar(config, **limits)
        parsed = [grammar.parse(text) for text, _ in cases]
        results[flag or "all_enabled"] = {
            "count": len(cases),
            "exact": sum(
                result is not None and result.normalized == expected
                for result, (_, expected) in zip(parsed, cases, strict=True)
            ),
            "abstained": sum(result is None for result in parsed),
            "outside_consumer_hint": grammar.parse("C13").outside_consumer_vocab
            if grammar.parse("C13")
            else None,
        }
    args.out.write_text(
        json.dumps(
            {
                "scope": "synthetic-symbolic-smoke; SYN-Val 아님; OCR accuracy 아님",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
