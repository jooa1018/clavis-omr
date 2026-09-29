"""Page bootstrap and paired comparisons; unsupported pages are never hidden."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from eval.policy import config
from eval.report import canonical

FIELDS = ("tier", "devPartition", "sourceKind", "captureChannel", "engravingTool", "musicFont")
FEATURES = (
    "ties",
    "dotted-notes",
    "accidentals",
    "6/8",
    "two-voices",
    "slash",
    "lyrics-ko",
    "lyrics-en",
)


def validate(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for record in records:
        if not isinstance(record.get("pageId"), str) or record["pageId"] in result:
            raise ValueError("missing or duplicate page ID")
        meta = record["metadata"]
        if (
            not set((*FIELDS, "measuredInterlinePx", "notationFeatures", "chordDensity"))
            <= meta.keys()
        ):
            raise ValueError("missing required slice metadata")
        if not isinstance(meta["notationFeatures"], list) or any(
            not isinstance(v, str) for v in meta["notationFeatures"]
        ):
            raise ValueError("invalid notation features")
        result[record["pageId"]] = record
    if not result:
        raise ValueError("no pages")
    reports = [r["report"] for r in records]
    for field in ("evaluatorVersion", "evaluatorDigest", "protocol"):
        if len({r[field] for r in reports}) != 1:
            raise ValueError("mixed evaluator definitions")
    return result


def slices(record: dict[str, Any]) -> dict[str, str]:
    meta = record["metadata"]
    labels = {field: str(meta[field]) if meta[field] is not None else "unknown" for field in FIELDS}
    interline = meta["measuredInterlinePx"]
    labels["interline"] = (
        "unknown"
        if interline is None
        else "below7"
        if interline < 7
        else "7-9"
        if interline < 9
        else "9-11"
        if interline < 11
        else "11-14"
        if interline < 14
        else "14+"
    )
    labels.update(
        {
            feature: "present" if feature in meta["notationFeatures"] else "absent"
            for feature in FEATURES
        }
    )
    labels["chordDensity"] = (
        str(meta["chordDensity"]) if meta["chordDensity"] is not None else "unknown"
    )
    return labels


def summary(
    pages: list[dict[str, Any]], other: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    policy = config("bootstrap.json")
    count, repeats = len(pages), int(policy["replicates"])
    result: dict[str, Any] = {
        "pageCount": count,
        "insufficientSample": count < 5,
        "conclusionWithheld": count < 5,
        "replicates": repeats,
        "seed": policy["seed"],
        "metrics": {},
    }
    failed = sum(p["report"]["status"] != "evaluated" for p in pages)
    failed_other = sum(p["report"]["status"] != "evaluated" for p in other) if other else 0
    if failed or failed_other:
        return {
            **result,
            "status": "PARTIAL",
            "unsupportedPagesA": failed,
            "unsupportedPagesB": failed_other,
        }
    names = sorted({key for page in (*pages, *(other or [])) for key in page["report"]["metrics"]})
    rng = np.random.default_rng(int(policy["seed"]))
    # Bounded batches avoid a replicates x pageCount allocation for large datasets.
    samples: dict[str, list[float]] = {name: [] for name in names}
    available = {
        name: all(name in p["report"]["metrics"] for p in (*pages, *(other or [])))
        for name in names
    }
    arrays = {}
    for name in names:
        if available[name]:
            arrays[name] = [
                np.asarray(
                    [
                        [p["report"]["metrics"][name][key] for key in ("numerator", "denominator")]
                        for p in group
                    ],
                    dtype=np.float64,
                )
                for group in (pages, other)
                if group is not None
            ]
            for matrix in arrays[name]:
                if not np.isfinite(matrix).all() or (matrix < 0).any():
                    raise ValueError("invalid metric counts")
    for start in range(0, repeats, 256):
        indices = rng.integers(0, count, size=(min(256, repeats - start), count))
        for name, values in arrays.items():
            ratios = []
            for group in values:
                sums = group[indices].sum(axis=1)
                ratios.append(
                    np.divide(
                        sums[:, 0],
                        sums[:, 1],
                        out=np.full(len(indices), np.nan),
                        where=sums[:, 1] != 0,
                    )
                )
            samples[name].extend((ratios[-1] - ratios[0] if other else ratios[0]).tolist())
    for name in names:
        if not available[name]:
            result["metrics"][name] = {
                "status": "NOT_RUN",
                "reason": "metric-missing-on-some-pages",
            }
            continue
        scale = 100 if name in {"K1", "K1-L"} else 1
        values = arrays[name]
        summaries = []
        for group in values:
            sums = group.sum(axis=0)
            mask = group[:, 1] != 0
            summaries.append(
                {
                    "numerator": int(sums[0]),
                    "denominator": int(sums[1]),
                    "micro": float(sums[0] / sums[1] * scale) if sums[1] else None,
                    "macro": float(np.mean(group[mask, 0] / group[mask, 1]) * scale)
                    if mask.any()
                    else None,
                    "macroDenominator": int(mask.sum()),
                }
            )
        draws = np.asarray(samples[name]) * scale
        finite = draws[np.isfinite(draws)]
        ci = np.quantile(finite, [0.025, 0.975]).tolist() if len(finite) else None
        item: dict[str, Any] = {
            "status": "evaluated",
            **summaries[0],
            "ci95": ci,
            "validReplicates": len(finite),
            "undefinedReplicates": repeats - len(finite),
        }
        if other:
            a, b = summaries[0]["micro"], summaries[1]["micro"]
            item = {
                "status": "evaluated",
                "A": summaries[0],
                "B": summaries[1],
                "deltaBMinusA": b - a if a is not None and b is not None else None,
                "ci95": ci,
                "validReplicates": len(finite),
                "undefinedReplicates": repeats - len(finite),
            }
        result["metrics"][name] = item
    result["status"] = "evaluated"
    return result


def aggregate(
    records: list[dict[str, Any]], comparison: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    a = validate(records)
    b = validate(comparison) if comparison is not None else None
    if b is not None:
        if a.keys() != b.keys():
            raise ValueError("paired comparison requires the same complete page set")
        for key in a:
            if a[key]["metadata"] != b[key]["metadata"]:
                raise ValueError("paired metadata mismatch")
            for field in ("evaluatorVersion", "evaluatorDigest", "protocol"):
                if a[key]["report"][field] != b[key]["report"][field]:
                    raise ValueError("paired evaluator mismatch; rerun both")
    ids = sorted(a)
    overall = summary([a[key] for key in ids], [b[key] for key in ids] if b else None)
    groups: dict[tuple[str, str], list[str]] = {}
    for key in ids:
        for field, value in slices(a[key]).items():
            groups.setdefault((field, value), []).append(key)
    return {
        "schema": "clavis-page-aggregate-1",
        "paired": b is not None,
        "evaluator": {
            field: a[ids[0]]["report"][field]
            for field in ("evaluatorVersion", "evaluatorDigest", "protocol")
        },
        "overall": overall,
        "slices": [
            {
                "field": field,
                "value": value,
                **summary([a[key] for key in keys], [b[key] for key in keys] if b else None),
            }
            for (field, value), keys in sorted(groups.items())
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        pages = json.loads(args.pages.read_text(encoding="utf-8"))
        comparison = json.loads(args.compare.read_text(encoding="utf-8")) if args.compare else None
        result = aggregate(pages, comparison)
    except (ValueError, KeyError, TypeError, OSError):
        print("ERROR: invalid page reports or incomparable page sets")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(canonical(result), encoding="utf-8")
    return 0 if result["overall"]["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
