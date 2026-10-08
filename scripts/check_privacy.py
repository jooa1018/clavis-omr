"""Reject profile paths and host identity fields without echoing their values."""

import argparse
import json
import re
import subprocess
from pathlib import Path

PROFILE = re.compile(
    r"(?:[A-Za-z]:[\\/]+Users[\\/]+|/(?:home|Users)/)"
    r"(?P<name>[^\\/\s\x00\"'`;,)}\]]+)",
    re.IGNORECASE,
)
HOST_FIELD = re.compile(
    r"""(?ix)(?:["'](?:host[_-]?name|computer[_-]?name)["']\s*:
    |(?:^|[\s{,])(?:host[_-]?name|computer[_-]?name)\s*[:=])"""
)
PLACEHOLDERS = frozenset({"YOU", "USER", "USERNAME", "<user>", "<username>", "<이름>"})


def inspect_text(path: str, text: str) -> list[dict[str, object]]:
    """Return locations only; placeholders are permitted in documentation."""
    document = path.startswith("docs/") or Path(path).suffix.lower() in {".md", ".rst"}
    findings: list[dict[str, object]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if any(
            not (document and match["name"] in PLACEHOLDERS) for match in PROFILE.finditer(line)
        ):
            findings.append({"file": path, "line": number, "rule": "PRIVACY-PROFILE"})
        if HOST_FIELD.search(line):
            findings.append({"file": path, "line": number, "rule": "PRIVACY-HOST-FIELD"})
    return findings


def scan(root: Path) -> dict[str, object]:
    """Inspect tracked checkout files, including unstaged edits, never external links."""
    root = root.resolve()
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
    paths = sorted(set(result.stdout.decode("utf-8").rstrip("\0").split("\0")) - {""})
    findings: list[dict[str, object]] = []
    for name in paths:
        path = root / name
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("external link")
            content = path.read_bytes().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            findings.append({"file": name, "line": 0, "rule": "PRIVACY-UNREADABLE"})
            continue
        findings.extend(inspect_text(name, content))
    return {
        "status": "FAIL" if findings else "PASS",
        "trackedFiles": len(paths),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        report = scan(args.root)
    except (OSError, ValueError, subprocess.CalledProcessError):
        report = {"status": "ERROR", "reason": "tracked-file enumeration failed"}
    output = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8", newline="\n")
    print(output, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
