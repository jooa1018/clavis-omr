"""Custodian preparation and aggregate release only; no engine execution yet."""

import hashlib
import json
import re
from collections import Counter
from datetime import date
from math import isfinite
from pathlib import Path
from typing import Any

from eval.report import canonical

METRICS = frozenset(
    {
        "K1",
        "K1-L",
        "K2",
        "harmonizationReadyRate",
        "pitchExactRate",
        "durationExactRate",
        "restExactRate",
        "tieExactRate",
        "accidentalExactRate",
        "graceExact",
        "keySignatureExactRate",
        "timeSignatureExactRate",
        "chordSymbolExactRate",
        "measureExactMatchRate",
        "measureExactWithLyrics",
        "lyricExactRate",
        "flagBurden",
        "flagPrecision",
        "errorRecall",
    }
)
RATE_FIELDS = frozenset(
    {
        "numerator",
        "denominator",
        "micro",
        "macro",
        "macroDenominator",
        "ci95",
        "validReplicates",
        "undefinedReplicates",
    }
)


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def preflight(artifact: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    """Compare freeze artifact with a W9/Custodian observed-digest receipt."""
    required = {
        "schema",
        "engineBuildDigest",
        "models",
        "configDigest",
        "devManifestDigest",
        "evaluatorVersion",
        "reviewThresholds",
        "frozenTargets",
        "frozenAt",
        "approvedBy",
    }
    if not required <= artifact.keys():
        raise ValueError("incomplete freeze artifact")
    if (
        artifact.get("schema") != "clavis-threshold-artifact-0.1"
        or artifact.get("approvedBy") != "orchestrator"
        or not artifact.get("frozenAt")
    ):
        raise ValueError("approved frozen artifact required")
    keys = ("engineBuildDigest", "configDigest", "devManifestDigest")
    if any(not valid_digest(artifact.get(key)) for key in keys):
        raise ValueError("invalid artifact digests")
    if (
        not valid_digest(observed.get("engineBuildDigest"))
        or observed["engineBuildDigest"] != artifact["engineBuildDigest"]
    ):
        raise ValueError("build receipt mismatch")
    if (
        observed.get("configDigest") != artifact["configDigest"]
        or observed.get("models") != artifact.get("models")
        or observed.get("evaluatorVersion") != artifact.get("evaluatorVersion")
    ):
        raise ValueError("model/config/evaluator receipt mismatch")
    for model in artifact.get("models", []):
        if set(model) != {"name", "sha256"} or not valid_digest(model["sha256"]):
            raise ValueError("model digest missing")
    if set(artifact.get("reviewThresholds", {})) != {"event", "harmony", "measure"} or any(
        type(v) is not int or not 0 <= v <= 10000 for v in artifact["reviewThresholds"].values()
    ):
        raise ValueError("review thresholds missing")
    if not artifact.get("frozenTargets"):
        raise ValueError("frozen targets missing")
    return {
        "status": "PARTIAL",
        "digestMatch": True,
        "artifactDigest": sha(artifact),
        "execution": "NOT_RUN",
        "reason": "W9 offline execution boundary and Custodian run required",
    }


def error_histogram(pairs: list[dict[str, Any]], aggregate: dict[str, Any]) -> dict[str, int]:
    """Field diagnostics only, not additive K1 operations or page details."""
    if len(pairs) != aggregate["overall"]["pageCount"] or any(
        p.get("status") != "evaluated" for p in pairs
    ):
        raise ValueError("complete evaluated pair set required")
    total = sum(g["k1Operations"] for p in pairs for g in p["measures"])
    if total != aggregate["overall"]["metrics"]["K1"]["numerator"]:
        raise ValueError("pair/aggregate operation mismatch")
    counts: Counter[str] = Counter()
    allowed = {
        "kind",
        "pitch",
        "duration",
        "tie_start",
        "tie_stop",
        "onset",
        "missing",
        "extra",
        "value",
    }
    for page in pairs:
        for key in ("evaluatorVersion", "evaluatorDigest", "protocol"):
            if page[key] != aggregate["evaluator"][key]:
                raise ValueError("pair evaluator mismatch")
        for group in page["measures"]:
            for category in ("events", "harmonies", "attributes"):
                for pair in group[category]:
                    for error in pair["errors"]:
                        if error not in allowed:
                            raise ValueError("unknown diagnostic")
                        counts[f"{category}.{error}"] += 1
                    if category == "events":
                        counts["lyrics"] += sum(bool(lyric["errors"]) for lyric in pair["lyrics"])
            if group["operation"] in {"split", "merge", "delete", "insert"}:
                counts["structure." + group["operation"]] += 1
            counts["repeatOrVolta"] += "repeatOrVolta" in group["measureErrors"]
    return {key: value for key, value in sorted(counts.items()) if value}


def release(
    aggregate: dict[str, Any],
    vocabulary: dict[str, list[str]],
    pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Allowlist only numeric aggregate fields; never copy arbitrary payloads."""
    if aggregate.get("schema") != "clavis-page-aggregate-1" or aggregate.get("paired") is not False:
        raise ValueError("expected a single-run page aggregate")

    def group(value: dict[str, Any]) -> dict[str, Any] | None:
        if type(value.get("pageCount")) is not int or value["pageCount"] < 5:
            return None
        if value.get("status") != "evaluated":
            raise ValueError("incomplete aggregate cannot be released as evaluated")
        metrics = {}
        for name in sorted(METRICS & value.get("metrics", {}).keys()):
            metric = value["metrics"][name]
            if metric.get("status") != "evaluated":
                continue
            selected = {k: v for k, v in metric.items() if k in RATE_FIELDS}
            for item in selected.values():
                numbers = item if isinstance(item, list) else [item]
                if any(
                    v is not None and (type(v) not in {int, float} or not isfinite(v))
                    for v in numbers
                ):
                    raise ValueError("nonnumeric aggregate content")
            metrics[name] = selected
        return {"pageCount": value["pageCount"], "metrics": metrics}

    overall = group(aggregate["overall"])
    if overall is None:
        return {
            "schema": "clavis-sealed-aggregate-1",
            "status": "SUPPRESSED",
            "reason": "insufficient-sample",
        }
    retained = []
    for item in aggregate["slices"]:
        field, label = item["field"], item["value"]
        if field not in vocabulary or label not in vocabulary[field]:
            continue
        result = group(item)
        if result is not None:
            retained.append({"field": field, "value": label, **result})
    return {
        "schema": "clavis-sealed-aggregate-1",
        "status": "AGGREGATE_ONLY",
        "overall": overall,
        "slices": retained,
        "errorHistogram": error_histogram(pairs, aggregate) if pairs is not None else None,
        "errorHistogramStatus": "evaluated" if pairs is not None else "NOT_RUN",
    }


def append_ledger(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    required = {
        "date",
        "sealedSetDigest",
        "buildDigest",
        "artifactDigest",
        "resultDigest",
        "verdict",
    }
    if set(entry) != required or entry["verdict"] not in {"PASS", "CONDITIONAL PASS", "FAIL"}:
        raise ValueError("invalid ledger fields")
    date.fromisoformat(entry["date"])
    if any(not valid_digest(entry[key]) for key in required - {"date", "verdict"}):
        raise ValueError("invalid ledger digest")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        records = (
            [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            if path.exists()
            else []
        )
        previous = "0" * 64
        for record in records:
            body = {k: v for k, v in record.items() if k != "entryDigest"}
            if record.get("previousEntryDigest") != previous or record.get("entryDigest") != sha(
                body
            ):
                raise ValueError("ledger chain mismatch")
            previous = record["entryDigest"]
        count = sum(r["sealedSetDigest"] == entry["sealedSetDigest"] for r in records)
        if count >= 2:
            raise ValueError("official run limit reached")
        if any(r["resultDigest"] == entry["resultDigest"] for r in records):
            raise ValueError("duplicate result receipt")
        body = {**entry, "officialRunIndex": count + 1, "previousEntryDigest": previous}
        output = {**body, "entryDigest": sha(body)}
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(output, sort_keys=True) + "\n")
        return output
    finally:
        lock.unlink()
