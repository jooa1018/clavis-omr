"""Independent coverage gates and named evidence from one pytest invocation."""

import argparse
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def coverage_gates(report: dict[str, object]) -> dict[str, bool]:
    files = report["files"]
    assert isinstance(files, dict)
    groups: dict[str, list[dict[str, int]]] = {
        "overall": [],
        "platform": [],
        "eval": [],
        "jobs": [],
    }
    for name, entry in files.items():
        name = name.replace("\\", "/")
        summary = entry["summary"]
        groups["overall"].append(summary)
        if name.startswith(("src/clavis/", "scripts/")):
            groups["platform"].append(summary)
        if name.startswith("training/jobs/"):
            groups["jobs"].append(summary)
        if name.startswith("eval/"):
            groups["eval"].append(summary)
    return {
        name: bool(items)
        and sum(i["covered_lines"] for i in items) * 100
        >= 80 * sum(i["num_statements"] for i in items)
        for name, items in groups.items()
    }


def required_tests(path: Path) -> dict[str, dict[str, int | str]]:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    result: dict[str, dict[str, int | str]] = {}
    for name, prefix in {
        "contracts": "tests.contracts.",
        "integrity-positive-negative": "tests.eval.test_integrity",
    }.items():
        selected = [c for c in cases if c.get("classname", "").startswith(prefix)]
        bad = sum(
            any(c.find(tag) is not None for tag in ("failure", "error", "skipped"))
            for c in selected
        )
        result[name] = {
            "count": len(selected),
            "status": "PASS" if selected and not bad else "FAIL",
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["coverage", "required"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.mode == "coverage":
        gates = coverage_gates(json.loads(args.path.read_text(encoding="utf-8")))
        result: object = gates
        passed = all(gates.values())
    else:
        evidence = required_tests(args.path)
        result = evidence
        passed = all(row["status"] == "PASS" for row in evidence.values())
    encoded = json.dumps(result, indent=2)
    print(encoded)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(f"### {args.mode}\n```json\n{encoded}\n```\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
