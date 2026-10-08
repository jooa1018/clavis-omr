"""OR-003 admission and Custodian-local reverse screening."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from eval.integrity.leakage import check, validate
from eval.policy import config

SOURCES = frozenset({"eval-pool", "lieder", "dev-melodies", "dev-images"})


def protection_digest(bundle: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def inventories(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    if (
        set(bundle) != {"schema", "version", "sources"}
        or bundle["schema"] != "clavis-protected-set-1"
        or type(bundle["version"]) is not int
        or bundle["version"] < 1
        or not isinstance(bundle["sources"], dict)
        or not {"eval-pool", "lieder"} <= bundle["sources"].keys() <= SOURCES
    ):
        raise ValueError("protected v1 requires eval-pool and whole Lieder; sealed is forbidden")
    result = []
    for name, source in sorted(bundle["sources"].items()):
        if set(source) != {"complete", "inventory"} or source["complete"] is not True:
            raise ValueError("incomplete protection source")
        samples = validate(source["inventory"], "reserved")
        if name in {"eval-pool", "lieder"} and not samples:
            raise ValueError("mandatory protection source empty")
        result.append(source["inventory"])
    return result


def admit(train: dict[str, Any], bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = validate(train, "train")
    excluded: set[str] = set()
    for inventory in inventories(bundle):
        report, _ = check(train, inventory)
        excluded.update(c["sampleId"] for c in report["conflicts"])
    digest = protection_digest(bundle)
    accepted = [s for s in candidates if s["sampleId"] not in excluded]
    return (
        {
            "schema": "clavis-admission-report-1",
            "status": "PASS" if candidates else "NOT_RUN",
            "candidateCount": len(candidates),
            "excludedCount": len(excluded),
            "admittedCount": len(accepted),
            "protectedSetDigest": digest,
            "protectedSetVersion": bundle["version"],
        },
        {
            "schema": "clavis-training-admission-1",
            "protectedSetDigest": digest,
            "protectedSetVersion": bundle["version"],
            "inventory": {**train, "samples": accepted},
        },
    )


def recheck(
    prior: dict[str, Any], bundle: dict[str, Any], song_ids: dict[str, str]
) -> dict[str, Any]:
    """Local Dev contamination receipt; prior checkpoints are never modified."""
    if prior.get("schema") != "clavis-training-admission-1":
        raise ValueError("previous admission receipt required")
    train = prior["inventory"]
    samples = validate(train, "train")
    if set(song_ids) != {s["sampleId"] for s in samples} or any(
        not isinstance(v, str) or not v for v in song_ids.values()
    ):
        raise ValueError("explicit sample-to-song mapping required")
    inventories(bundle)
    if bundle["version"] <= prior["protectedSetVersion"]:
        raise ValueError("protection version must increase")
    hit_songs: set[str] = set()
    contaminated: set[str] = set()
    for name, source in sorted(bundle["sources"].items()):
        report, _ = check(train, source["inventory"])
        hit_songs.update(song_ids[c["sampleId"]] for c in report["conflicts"])
        if name.startswith("dev-") and samples:
            reverse, _ = check(
                {**source["inventory"], "role": "train"}, {**train, "role": "reserved"}
            )
            contaminated.update(c["sampleId"] for c in reverse["conflicts"])
    count = len(set(song_ids.values()))
    return {
        "schema": "clavis-protection-recheck-1",
        "status": "ESCALATE"
        if len(hit_songs) * 100
        > count * config("protection-policy.json")["newConflictSongPercentEscalation"]
        else "PASS",
        "previousProtectedSetDigest": prior["protectedSetDigest"],
        "protectedSetDigest": protection_digest(bundle),
        "trainingSongCount": count,
        "newlyExcludedSongCount": len(hit_songs),
        "newlyExcludedSongIds": sorted(hit_songs),
        "contaminatedDevPageIds": sorted(contaminated),
        "checkpointAction": "keep-existing; exclude-conflicts-before-next-training",
    }


def reverse_screen(
    candidates: dict[str, Any], train: dict[str, Any], dev: dict[str, Any]
) -> tuple[dict[str, int], dict[str, Any]]:
    """Never expose candidate IDs, fingerprints or matching reasons in receipt."""
    samples = validate(candidates, "reserved")
    validate(train, "train")
    validate(dev, "reserved")
    excluded: set[str] = set()
    for protected in ({**train, "role": "reserved"}, dev):
        report, _ = check({**candidates, "role": "train"}, protected)
        excluded.update(c["sampleId"] for c in report["conflicts"])
    return (
        {"candidateCount": len(samples), "excludedCount": len(excluded)},
        {**candidates, "samples": [s for s in samples if s["sampleId"] not in excluded]},
    )
