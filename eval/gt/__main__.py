"""Validate Dev intake locally; never follows a sealed manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from eval.gt import Manifest, Selection, Sidecar

REPOSITORY = Path(__file__).resolve().parents[2]


def private_root() -> Path:
    value = os.environ.get("CLAVIS_PRIVATE_ROOT")
    if not value:
        raise ValueError("CLAVIS_PRIVATE_ROOT is required")
    path = Path(value).resolve()
    if not path.is_dir() or path.is_relative_to(REPOSITORY) or REPOSITORY.is_relative_to(path):
        raise ValueError("private root must be a separate existing directory")
    if any((ancestor / ".git").exists() for ancestor in (path, *path.parents)):
        raise ValueError("private root must not belong to any Git worktree")
    return path


def contained(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or ":" in relative or "\\" in relative:
        raise ValueError("expected a private-root relative POSIX path")
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()) or any(
        p.is_symlink() for p in (target, *target.parents) if p != root.parent
    ):
        raise ValueError("private path escape")
    return target


def read_json(path: Path) -> Any:
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("metadata too large")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def selected_systems(page_id: str, total: int, count: int, seed: str) -> list[int]:
    if not 2 <= count <= 4 or total < count or total > 100 or not seed:
        raise ValueError("need 2-4 systems, count <= total <= 100, and a seed")
    ranked = sorted(
        range(1, total + 1),
        key=lambda n: (
            hashlib.sha256(f"clavis-system-selection-v1:{seed}:{page_id}:{n}".encode()).digest(),
            n,
        ),
    )
    return sorted(ranked[:count])


def validate_page(root: Path, relative: str) -> Sidecar:
    raw = read_json(contained(root, relative))
    # Do not open any referenced content when the sidecar identifies sealed data.
    if not isinstance(raw, dict) or raw.get("split") != "dev":
        raise ValueError("Dev intake accepts Dev sidecars only")
    page = Sidecar.model_validate_json(json.dumps(raw))
    if (
        page.selection.method == "sha256-rank-v1"
        and selected_systems(
            page.pageId,
            page.selection.totalSystems,
            len(page.selection.selectedSystems),
            page.selection.seed,
        )
        != page.selection.selectedSystems
    ):
        raise ValueError("selection record does not reproduce")
    for filename, expected in (
        (page.imagePath, page.imageDigest),
        (page.musicXmlPath, page.groundTruthDigest),
        (page.renderPath, page.renderDigest),
    ):
        if digest(contained(root, filename)) != expected:
            raise ValueError("file digest mismatch")
    xml = contained(root, page.musicXmlPath)
    if xml.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("MusicXML too large")
    data = xml.read_bytes()
    if b"<!ENTITY" in data or b"<![" in data or b"\x00" in data:
        raise ValueError("entities and non-UTF8 MusicXML are unsupported")
    score = ET.fromstring(data)
    if score.tag != "score-partwise" or score.get("version") != "4.0":
        raise ValueError("intake requires uncompressed partwise MusicXML 4.0")
    part = next((p for p in score.findall("part") if p.get("id") == page.leadStaff.part), None)
    if part is None:
        raise ValueError("lead part missing")
    measures = part.findall("measure")
    covered: list[int] = []
    for region in page.evalRegions:
        covered.extend(range(region.xmlMeasureStart, region.xmlMeasureEnd + 1))
    if page.evalRegions and covered != list(range(1, len(measures) + 1)):
        raise ValueError("partial XML must map each measure exactly once, in selected system order")
    if not measures:
        raise ValueError("empty GT")
    return page


def audit(pages: list[Sidecar]) -> dict[str, Any]:
    issues: list[str] = []
    if len({p.pageId for p in pages}) != len(pages):
        issues.append("duplicate-page")
    for attr in ("songId", "captureId", "printId"):
        groups: dict[str, set[str]] = defaultdict(set)
        for page in pages:
            value = getattr(page, attr)
            if value is not None:
                groups[value].add(f"{page.split}:{page.devPartition}")
        if any(len(partitions) > 1 for partitions in groups.values()):
            issues.append(f"split-overlap:{attr}")
    bins = Counter(
        "7-9"
        if 7 <= p.measuredInterlinePx < 9
        else "9-11"
        if 9 <= p.measuredInterlinePx < 11
        else "11-14"
        if 11 <= p.measuredInterlinePx < 14
        else "14+"
        if p.measuredInterlinePx >= 14
        else "below7"
        for p in pages
    )
    gaps: list[str] = []
    for attr, expected in (
        ("sourceKind", {"digital-pdf", "scanned-pdf", "camera-photo"}),
        ("meter", {"4/4", "6/8"}),
        ("keyMode", {"major", "minor"}),
    ):
        gaps.extend(
            f"missing:{attr}:{v}" for v in sorted(expected - {getattr(p, attr) for p in pages})
        )
    available = {feature for p in pages for feature in p.features}
    gaps.extend(
        f"missing:features:{v}" for v in sorted({"accidentals", "dotted-notes", "ties"} - available)
    )
    gaps.extend(
        f"insufficient-interline:{name}"
        for name in ("7-9", "9-11", "11-14", "14+")
        if bins[name] < 5
    )
    for partition in ("Dev-Tune", "Dev-Check"):
        members = [p for p in pages if p.devPartition == partition]
        if not members:
            gaps.append(f"missing-partition:{partition}")
        for attr in ("engravingTool", "musicFont"):
            counts = Counter(getattr(p, attr) for p in members)
            if None in counts:
                gaps.append(f"unknown:{partition}:{attr}")
            if any(count * 2 > len(members) for key, count in counts.items() if key is not None):
                gaps.append(f"imbalance:{partition}:{attr}")
    if len(pages) < 20:
        gaps.append("Dev-v0-below20")
    return {
        "schema": "clavis-gt-audit-1",
        "status": "FAIL" if issues else "PARTIAL" if gaps else "PASS",
        "pageCount": len(pages),
        "issues": issues,
        "coverageGaps": gaps,
        "interlineBins": dict(sorted(bins.items())),
        "legacyPages": sum(p.legacy for p in pages),
        "partialPages": sum(bool(p.evalRegions) for p in pages),
        "scope": "local Dev intake, no recognition accuracy measurement",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("select")
    select.add_argument("--page-id", required=True)
    select.add_argument("--systems", type=int, required=True)
    select.add_argument("--count", type=int, default=3)
    select.add_argument("--seed", required=True)
    select.add_argument("--date", required=True)
    select.add_argument("--out", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        root = private_root()
        target = contained(root, args.out)
        if args.command == "select":
            selection = Selection(
                method="sha256-rank-v1",
                seed=args.seed,
                totalSystems=args.systems,
                selectedSystems=selected_systems(args.page_id, args.systems, args.count, args.seed),
                recordedOn=date.fromisoformat(args.date),
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as stream:
                stream.write(selection.model_dump_json(indent=2) + "\n")
            print("selection recorded; existing records cannot be overwritten")
            return 0
        if target.exists():
            raise ValueError("audit output must be a new file")
        manifest = Manifest.model_validate_json(
            json.dumps(read_json(contained(root, args.manifest)))
        )
        pages = [validate_page(root, relative) for relative in manifest.sidecars]
        result = audit(pages)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
        print(result["status"])
        return 1 if result["status"] == "FAIL" else 0
    except (ValueError, OSError, ValidationError, ET.ParseError):
        # Pydantic/XML exceptions can contain private lyrics, paths and titles.
        print(
            "ERROR: private intake invalid; check format, digests, paths, "
            "selection and review dates"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
