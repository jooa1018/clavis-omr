"""CI evidence summary; absent real inventories never grant training admission."""

import argparse
import json
from pathlib import Path
from typing import Any


def summarize(ast_report: Path) -> tuple[dict[str, Any], int]:
    try:
        ast = json.loads(ast_report.read_text(encoding="utf-8"))
        if not isinstance(ast, dict) or ast.get("schema") != "clavis-hardcode-scan-1":
            raise ValueError("invalid AST report")
        passed = ast.get("status") == "PASS" and ast.get("findings") == []
    except (OSError, ValueError):
        ast = {"status": "ERROR", "reason": "missing-or-invalid-ast-report"}
        passed = False
    return {
        "status": "PARTIAL" if passed else "FAIL",
        "hardcoding": ast,
        "dataLeakage": {
            "status": "NOT_RUN",
            "reason": (
                "No real train/reserved inventories are supplied to CI; unit fixtures are separate."
            ),
            "trainingAdmissionAllowed": False,
        },
    }, 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ast-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report, code = summarize(args.ast_report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    args.out.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
