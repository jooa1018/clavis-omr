"""Versioned deterministic output; source digest includes evaluator policy."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from eval.metrics import measure
from eval.projection import project
from eval.projection.model import EvaluationUnsupported

VERSION = "0.1.0"


def canonical(value: object) -> str:
    def encode(item: object) -> str:
        if isinstance(item, Fraction):
            return str(item)
        raise TypeError(type(item).__name__)

    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=encode) + "\n"


def evaluator_digest() -> str:
    root = Path(__file__).resolve().parents[2]
    files = [*sorted((root / "eval").rglob("*.py")), *sorted((root / "configs/eval").glob("*"))]
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(file.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def evaluate(reference: bytes, prediction: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    """Evaluate public XML bytes only. Unsupported input has no numeric score."""
    meta = {
        "evaluatorVersion": VERSION,
        "evaluatorDigest": evaluator_digest(),
        "protocol": "clavis-evaluation-1.1",
        "scope": "single-part-staff-voice",
        "inputDigests": {
            "reference": hashlib.sha256(reference).hexdigest(),
            "prediction": hashlib.sha256(prediction).hexdigest(),
        },
    }
    try:
        result, pairs = measure(project(reference), project(prediction))
        report = {
            "schema": "clavis-eval-report-0.1",
            **meta,
            "status": "evaluated",
            **result,
            "notImplemented": [
                "K2",
                "K3",
                "bootstrap",
                "multi-page-aggregation",
                "expanded-play-order",
                "regions",
                "geometry",
                "calibration",
            ],
        }
    except EvaluationUnsupported as exc:
        report = {
            "schema": "clavis-eval-report-0.1",
            **meta,
            "status": "evaluation-unsupported",
            "reason": str(exc),
            "metrics": {},
        }
        pairs = []
    return report, {
        "schema": "clavis-eval-pairs-0.1",
        **meta,
        "status": report["status"],
        "measures": pairs,
    }


def write_report(report: dict[str, Any], pairs: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, value in (("report.json", report), ("pairs.json", pairs)):
        (out / name).write_text(canonical(value), encoding="utf-8", newline="\n")
    lines = [
        "# Clavis evaluation",
        "",
        f"Status: {report['status']}",
        "",
        f"Evaluator: {report['evaluatorVersion']} / {report['evaluatorDigest']}",
        "",
        "| Metric | Numerator | Denominator | Value |",
        "|---|---:|---:|---:|",
    ]
    for key, value in report["metrics"].items():
        lines.append(
            f"| {key} | {value['numerator']} | {value['denominator']} | {value['value']} |"
        )
    if "reason" in report:
        lines.extend(["", f"Reason: {report['reason']}"])
    else:
        lines.extend(
            [
                "",
                f"K1 objects: {report['k1Operations']}",
                f"onsetOnlyMismatch: {report['onsetOnlyMismatch']}",
                "",
                "Unimplemented: " + ", ".join(report["notImplemented"]),
            ]
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
