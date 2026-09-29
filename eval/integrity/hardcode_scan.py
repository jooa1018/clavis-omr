"""Conservative AST review gate for charter H1--H9, not a security sandbox."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

NETWORK = frozenset({"socket", "requests", "httpx", "urllib", "http", "aiohttp", "ftplib"})
RANDOM_METHODS = frozenset(
    {
        "random",
        "randint",
        "randrange",
        "choice",
        "choices",
        "shuffle",
        "uniform",
        "normal",
        "rand",
        "randn",
        "sample",
        "permutation",
    }
)


@dataclass(frozen=True, order=True)
class Finding:
    file: str
    line: int
    rule: str
    owner: str
    evidence_digest: str


def owner(path: str) -> str:
    for worker, prefixes in {
        "W4": ("eval/", "configs/eval/", "configs/integrity/", "tests/eval/"),
        "W2": ("training/data/", "tests/data/", "configs/data/"),
        "W3": ("training/degrade/", "tests/degrade/", "configs/degrade/"),
        "W5": ("src/clavis/ingest/", "src/clavis/geometry/"),
        "W6": ("src/clavis/symbols/",),
        "W7": ("src/clavis/text/",),
        "W8": ("src/clavis/assemble/", "src/clavis/export/", "src/clavis/calibrate/"),
        "W9": ("src/clavis/service/", "deploy/"),
    }.items():
        if path.startswith(prefixes):
            return worker
    return "W1"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return dotted(node.value) + "." + node.attr
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def scan_source(source: str, path: str, identifiers: frozenset[str] = frozenset()) -> list[Finding]:
    tree = ast.parse(source, filename=path)
    guards = {
        id(part)
        for statement in ast.walk(tree)
        if isinstance(statement, ast.If)
        and not statement.orelse
        and all(isinstance(action, ast.Raise) for action in statement.body)
        for part in ast.walk(statement.test)
    }
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def qualified(node: ast.AST) -> str:
        name = dotted(node)
        head, sep, tail = name.partition(".")
        return aliases.get(head, head) + sep + tail

    def clock_call(node: ast.AST) -> bool:
        return isinstance(node, ast.Call) and qualified(node.func) in {
            "time.time",
            "time.time_ns",
            "time.monotonic",
            "time.perf_counter",
            "datetime.datetime.now",
            "datetime.datetime.utcnow",
            "datetime.date.today",
        }

    # Propagate local time aliases to predicates; mere duration logging is allowed.
    clock_names: set[str] = set()
    for _ in range(len(list(ast.walk(tree)))):
        previous = set(clock_names)
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.Assign, ast.AnnAssign))
                and node.value is not None
                and not isinstance(node.value, (ast.Dict, ast.List, ast.Tuple, ast.Set))
            ):
                if any(
                    clock_call(n) or isinstance(n, ast.Name) and n.id in clock_names
                    for n in ast.walk(node.value)
                ):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    clock_names.update(dotted(t) for t in targets)
        if previous == clock_names:
            break

    findings: set[Finding] = set()
    runtime = path.startswith("src/clavis/")

    def add(node: ast.AST, rule: str) -> None:
        evidence = ast.dump(node, include_attributes=False).encode()
        findings.add(
            Finding(
                path,
                node.lineno,  # type: ignore[attr-defined]
                rule,
                owner(path),
                hashlib.sha256(evidence).hexdigest(),
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, str):
                if re.fullmatch(r"(?:0x)?[0-9a-fA-F]{16,}", value):
                    add(node, "H1")
                if (
                    value in identifiers
                    or value.replace("\\", "/").rsplit("/", 1)[-1] in identifiers
                ):
                    add(node, "H2")
                if runtime and re.search(
                    r"(?:^|[/\\])(?:eval|gt|ground[_-]?truth)(?:[/\\.]|$)|data[/\\]manifests",
                    value,
                    re.I,
                ):
                    add(node, "H6")
            if type(value) is int:
                segment = ast.get_source_segment(source, node) or ""
                if re.fullmatch(r"0[xX][0-9a-fA-F_]{16,}", segment):
                    add(node, "H1")
            if runtime and isinstance(value, float):
                if len(Decimal(str(value)).normalize().as_tuple().digits) > 3:
                    add(node, "H5")
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            names = " ".join(dotted(n).lower() for n in ast.walk(node))
            numbers = [
                n.value for n in operands if isinstance(n, ast.Constant) and type(n.value) is int
            ]
            if numbers:
                if re.search(
                    r"(?:image|img|page|pixels?).*\.(?:width|height|size|shape)|(?:^|\s)(?:width|height|shape)(?:\s|$)",
                    names,
                ):
                    # Charter §4 permits obvious zero bounds. RGB channel count is
                    # a format invariant, not a spatial image identity (W3 review).
                    channel = any(
                        isinstance(n, ast.Subscript)
                        and dotted(n.value).endswith(".shape")
                        and isinstance(n.slice, ast.Constant)
                        and n.slice.value == 2
                        for n in operands
                    )
                    format_guard = id(node) in guards and (
                        numbers == [0] or channel and numbers == [3]
                    )
                    if not format_guard:
                        add(node, "H3")
                if not path.startswith("tests/") and re.search(
                    r"(?:measure|page|staff|system)(?:_?(?:index|idx|number|no))", names
                ):
                    add(node, "H4")
        if runtime and isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = (
                [n.name for n in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            if any(m.split(".")[0] in NETWORK for m in modules):
                add(node, "H7")
            if any(m == "eval" or m.startswith("eval.") for m in modules):
                add(node, "H6")
        if isinstance(node, ast.Call):
            name = qualified(node.func)
            root = name.split(".")[0]
            if name in {
                "numpy.random.default_rng",
                "numpy.random.RandomState",
                "random.Random",
                "random.seed",
                "numpy.random.seed",
            }:
                seed = (
                    node.args[0]
                    if node.args
                    else next((k.value for k in node.keywords if k.arg in {"seed", "a"}), None)
                )
                if seed is None or isinstance(seed, ast.Constant) and seed.value is None:
                    add(node, "H8")
            elif (
                name.startswith(("random.", "numpy.random."))
                and name.rsplit(".", 1)[-1] in RANDOM_METHODS
            ) or root == "secrets":
                # Global RNG state is not an explicit, passed seeded Generator.
                add(node, "H8")
        predicates: list[ast.AST] = []
        if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            predicates = [node.test]
        elif isinstance(node, ast.comprehension):
            predicates = list(node.ifs)
        for predicate in predicates:
            if any(
                clock_call(n) or isinstance(n, ast.Name) and n.id in clock_names
                for n in ast.walk(predicate)
            ):
                add(node, "H9")
    return sorted(findings)


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = sorted(set(result.stdout.decode("utf-8").split("\0")) - {""})
    selected = [
        root / p
        for p in paths
        if p.endswith(".py") or p.startswith("data/manifests/") and p.endswith(".json")
    ]
    if any(p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) for p in selected):
        raise ValueError("out-of-root or symbolic source path")
    return selected


def manifest_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {
                "id",
                "pageId",
                "songId",
                "captureId",
                "filename",
                "fileName",
                "path",
                "imagePath",
            } and isinstance(item, str):
                found.add(item)
                found.add(item.replace("\\", "/").rsplit("/", 1)[-1])
            found.update(manifest_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(manifest_ids(item))
    return found


def scan(root: Path) -> dict[str, Any]:
    files = tracked_files(root)
    identifiers: set[str] = set()
    for path in files:
        if path.suffix == ".json":
            identifiers.update(manifest_ids(json.loads(path.read_text(encoding="utf-8"))))
    findings = [
        f
        for p in files
        if p.suffix == ".py"
        for f in scan_source(
            p.read_text(encoding="utf-8-sig"),
            p.relative_to(root).as_posix(),
            frozenset(identifiers),
        )
    ]
    allowpath = root / "configs/integrity/allowlist.yaml"
    # JSON is a YAML subset: no dependency or executable YAML tags needed.
    allow = json.loads(allowpath.read_text(encoding="utf-8")) if allowpath.exists() else []
    if not isinstance(allow, list):
        raise ValueError("allowlist must be a JSON-subset YAML array")
    suppressed: list[Finding] = []
    for entry in allow:
        if (
            not isinstance(entry, dict)
            or not {"file", "line", "rule", "reason", "approvedBy", "evidence_digest"}
            <= entry.keys()
            or not entry["reason"]
            or not isinstance(entry["approvedBy"], list)
            or set(entry["approvedBy"]) != {"W4", "orchestrator"}
        ):
            raise ValueError("unapproved or invalid allowlist entry")
        matches = [
            f
            for f in findings
            if all(getattr(f, k) == entry[k] for k in ("file", "line", "rule", "evidence_digest"))
        ]
        if len(matches) != 1:
            raise ValueError("stale or duplicate allowlist entry")
        findings.remove(matches[0])
        suppressed.extend(matches)
    return {
        "schema": "clavis-hardcode-scan-1",
        "status": "FAIL" if findings else "PASS",
        "pythonFiles": sum(p.suffix == ".py" for p in files),
        "manifestIdentifiers": len(identifiers),
        "findings": [asdict(f) for f in findings],
        "suppressed": [asdict(f) for f in suppressed],
        "byOwner": {
            w: sum(f.owner == w for f in findings) for w in sorted({f.owner for f in findings})
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = scan(args.root.resolve())
    except (ValueError, OSError, SyntaxError, subprocess.CalledProcessError):
        report = {"status": "ERROR", "reason": "invalid-source-or-configuration"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
