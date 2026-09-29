"""Reproduce the negative fixtures for PR #4 approval conditions 1–8."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "fixtures/contracts"


def read(stem):
    return json.loads((ROOT / "valid" / f"{stem}.json").read_bytes())


def build():
    cases = []

    def case(condition, label, model, stem, mutate, error):
        data = read(stem)
        mutate(data)
        cases.append(
            (
                f"condition-{condition}-{label}",
                {
                    "condition": condition,
                    "model": model,
                    "expectedError": error,
                    "payload": data,
                },
            )
        )

    def change(path, value):
        def mutate(data):
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = copy.deepcopy(value)

        return mutate

    root = ["hypotheses", 0, "items"]
    items = read("lattice-0")["hypotheses"][0]["items"]
    note = next(i for i, x in enumerate(items) if x["item"]["type"] == "note")
    event = ["measures", 0, "staffMeasures", 0, "voices", 0, "events", 0]

    def reverse_header(data):
        items = data["hypotheses"][0]["items"]
        items[:3] = [items[2], items[0], items[1]]

    case(1, "printed-order", "StaffLattice", "lattice-0", reverse_header, "printed x order")
    for attr, value in [
        ("acc", "none"),
        ("accParen", False),
        ("tie", "none"),
        ("slur", "none"),
        ("chord", 0),
        ("grace", "none"),
        ("tup3", "none"),
        ("fermata", False),
        ("stem", "none"),
        ("beam", "none"),
    ]:
        case(
            2,
            f"note-{attr}",
            "StaffLattice",
            "lattice-0",
            change(root + [note, "item", attr], value),
            "default must be omitted",
        )
    case(
        2,
        "courtesy",
        "StaffLattice",
        "lattice-0",
        change(root + [0, "item", "courtesy"], False),
        "default must be omitted",
    )
    case(
        2,
        "cancel",
        "StaffLattice",
        "lattice-0",
        change(root + [0, "item"], {"type": "key", "fifths": 0, "cancel": 0}),
        "default must be omitted",
    )
    case(
        2,
        "measure-rest",
        "StaffLattice",
        "lattice-0",
        change(
            root + [note, "item"],
            {"type": "rest", "dur": "whole", "dots": 0, "v": 1, "measureRest": False},
        ),
        "default must be omitted",
    )
    for attr in ["grace", "accidentalVisible"]:
        case(
            2,
            f"event-{attr}",
            "ScoreIR",
            "score",
            change(event + [attr], "none"),
            "default must be omitted",
        )
    case(
        2,
        "empty-attrs",
        "SymbolGraph",
        "symbols-0",
        change(["symbols", 0, "attrs"], {}),
        "default must be omitted",
    )
    case(
        3,
        "nested-pos",
        "SymbolGraph",
        "symbols-0",
        change(["symbols", 0, "attrs"], {"posTopK": [[0, 9000]]}),
        "Extra inputs",
    )
    case(
        3,
        "voice-relation",
        "SymbolGraph",
        "symbols-0",
        change(["relations", 0, "kind"], "voiceOf"),
        "Input should be",
    )
    head_ids = [
        s["symbolId"]
        for s in read("symbols-0")["symbols"]
        if s["classTopK"][0][0].startswith("notehead")
    ]
    a, b = sorted(head_ids)[:2]
    case(
        3,
        "chord-direction",
        "SymbolGraph",
        "symbols-0",
        change(["relations", 0], {"kind": "chordWith", "from": b, "to": a, "probBp": 9000}),
        "from id < to id",
    )
    case(
        3,
        "voice-range",
        "SymbolGraph",
        "symbols-0",
        change(["symbols", 0, "attrs"], {"voiceTopK": [[5, 9000]]}),
        "less than or equal to 4",
    )
    for label, values, error in [
        ("class-duplicate", [["stem", 5000], ["stem", 4000]], "duplicate top-k"),
        ("class-empty", [], "at least 1"),
        (
            "class-long",
            [[v, 1000] for v in ["stem", "beam", "flag", "augDot", "barline", "curve"]],
            "at most 5",
        ),
        ("class-bp-order", [["stem", 4000], ["beam", 5000]], "descending bp"),
        ("class-tie-order", [["stem", 5000], ["beam", 5000]], "canonical value"),
        ("class-sum", [["stem", 6000], ["beam", 5000]], "sum exceeds"),
    ]:
        case(
            4, label, "SymbolGraph", "symbols-0", change(["symbols", 0, "classTopK"], values), error
        )
    for label, values, error in [
        ("pos-empty", [], "at least 1"),
        ("pos-duplicate", [[0, 5000], [0, 4000]], "duplicate top-k"),
        ("pos-long", [[0, 4000], [1, 3000], [2, 2000], [3, 1000]], "at most 3"),
        ("pos-tie-order", [[1, 5000], [-1, 5000]], "canonical value"),
    ]:
        case(4, label, "SymbolGraph", "symbols-0", change(["symbols", 0, "posTopK"], values), error)
    case(
        4,
        "attrs-duplicate",
        "SymbolGraph",
        "symbols-0",
        change(["symbols", 0, "attrs"], {"voiceTopK": [[1, 5000], [1, 4000]]}),
        "duplicate top-k",
    )
    case(
        4,
        "attribute-sum",
        "StaffLattice",
        "lattice-0",
        change(root + [note, "attrTopK"], {"dur": [["quarter", 7000], ["eighth", 4000]]}),
        "sum exceeds",
    )
    case(
        5,
        "current-missing",
        "StaffLattice",
        "lattice-0",
        change(root + [note, "attrTopK"], {"dur": [["eighth", 9000]]}),
        "current/default item value",
    )
    case(
        5,
        "default-missing",
        "StaffLattice",
        "lattice-0",
        change(root + [note, "attrTopK"], {"acc": [["sharp", 9000]]}),
        "current/default item value",
    )
    case(
        5,
        "rank-start",
        "StaffLattice",
        "lattice-0",
        change(["hypotheses", 0, "rank"], 1),
        "consecutive from zero",
    )
    case(
        5,
        "rank-gap",
        "StaffLattice",
        "lattice-1",
        change(["hypotheses", 1, "rank"], 2),
        "consecutive from zero",
    )
    case(
        5,
        "log-increase",
        "StaffLattice",
        "lattice-1",
        change(["hypotheses", 1, "logProbMicro"], 0),
        "must not increase",
    )
    case(
        6,
        "event-zero",
        "ScoreIR",
        "score",
        change(event + ["duration"], {"n": 0, "d": 1}),
        "zero duration requires",
    )
    case(
        6,
        "patch-zero",
        "ReviewHints",
        "hints",
        change(["hints", 0, "alternatives", 0, "patch", "duration"], {"n": 0, "d": 1}),
        "must be positive",
    )
    case(
        7,
        "index-start",
        "ScoreIR",
        "score",
        change(["measures", 0, "index"], 1),
        "consecutive per part",
    )
    case(
        7,
        "index-gap",
        "ScoreIR",
        "score",
        change(["measures", 2, "index"], 3),
        "consecutive per part",
    )
    case(
        8,
        "duplicate-target",
        "EvidenceBundle",
        "evidence",
        change(
            ["evidence", 1, "vendorTargetId"], read("evidence")["evidence"][0]["vendorTargetId"]
        ),
        "duplicate evidence target",
    )
    for dimension in ["widthMu", "heightMu"]:
        case(
            8,
            f"zero-{dimension}",
            "EvidenceBundle",
            "evidence",
            change(["evidence", 0, "box", dimension], 0),
            "greater than or equal to 1",
        )
    case(
        8,
        "extension-zero-width",
        "EvidenceBundle",
        "evidence",
        change(["extensions", "measureBoxes", 0, "box", "widthMu"], 0),
        "greater than or equal to 1",
    )
    for stem, payload in cases:
        (ROOT / "invalid" / f"{stem}.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )


if __name__ == "__main__":
    build()
