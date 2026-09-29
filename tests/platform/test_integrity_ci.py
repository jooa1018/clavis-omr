"""CI summary refuses absent, failed or contradictory scanner evidence."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.integrity_status import main, summarize


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "broken-json",
        [],
        {},
        {"schema": "clavis-hardcode-scan-1", "status": "FAIL", "findings": [{"rule": "H4"}]},
        {"schema": "clavis-hardcode-scan-1", "status": "ERROR"},
        {"schema": "clavis-hardcode-scan-1", "status": "NOT_RUN"},
        {"schema": "clavis-hardcode-scan-1", "status": "PASS", "findings": [{"rule": "H4"}]},
        {"schema": "clavis-hardcode-scan-1", "status": "PASS"},
    ],
)
def test_ci_summary_never_turns_failures_into_pass(tmp_path, payload):
    path = tmp_path / "scan.json"
    if payload is not None:
        path.write_text(
            payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
        )
    summary, code = summarize(path)
    assert code == 1
    assert summary["status"] == "FAIL"
    assert summary["dataLeakage"]["trainingAdmissionAllowed"] is False


def test_ast_pass_keeps_real_leakage_not_run(tmp_path, monkeypatch, capsys):
    source = tmp_path / "ast.json"
    source.write_text(
        json.dumps({"schema": "clavis-hardcode-scan-1", "status": "PASS", "findings": []}),
        encoding="utf-8",
    )
    output = tmp_path / "reports/status.json"
    monkeypatch.setattr(
        sys, "argv", ["integrity_status", "--ast-report", str(source), "--out", str(output)]
    )
    assert main() == 0
    summary = json.loads(output.read_bytes())
    assert summary == json.loads(capsys.readouterr().out)
    assert summary["status"] == "PARTIAL"
    assert summary["hardcoding"]["status"] == "PASS"
    assert summary["dataLeakage"]["status"] == "NOT_RUN"
    assert summary["dataLeakage"]["trainingAdmissionAllowed"] is False


def test_cli_fails_closed_on_missing_ast_report(tmp_path):
    root = Path(__file__).resolve().parents[2]
    out = tmp_path / "status.json"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/integrity_status.py"),
            "--ast-report",
            str(tmp_path / "missing.json"),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert json.loads(out.read_bytes())["hardcoding"]["status"] == "ERROR"
