"""Routing, fail-closed evidence and independent coverage regression checks."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import ci_plan, ci_results


@pytest.mark.parametrize(
    ("event", "files", "draft", "changed", "runners"),
    [
        (
            "pull_request",
            ["src/clavis/core/a.py"],
            False,
            True,
            ["ubuntu-latest", "windows-latest"],
        ),
        ("pull_request", ["uv.lock"], False, True, ["ubuntu-latest", "windows-latest"]),
        (
            "pull_request",
            [".github/workflows/a.yml"],
            False,
            True,
            ["ubuntu-latest", "windows-latest"],
        ),
        ("pull_request", ["scripts/a.py"], False, True, ["ubuntu-latest", "windows-latest"]),
        ("pull_request", ["docs/a.md", "README.md"], False, True, []),
        (
            "pull_request",
            ["README.md", "tests/platform/test_example.py"],
            False,
            True,
            ["ubuntu-latest", "windows-latest"],
        ),
        ("pull_request", [], False, True, ["ubuntu-latest", "windows-latest"]),
        ("pull_request", ["scripts/a.py"], True, True, []),
        ("push", ["docs/a.md"], False, True, ["ubuntu-latest"]),
        ("schedule", [], False, False, []),
        ("schedule", [], False, True, ["windows-latest"]),
        ("workflow_dispatch", [], False, False, ["windows-latest"]),
    ],
)
def test_routing(
    event: str, files: list[str], draft: bool, changed: bool, runners: list[str]
) -> None:
    result = ci_plan.plan(event, files, draft=draft, changed=changed)
    assert result["quality"] == bool(runners)
    if runners:
        assert result["matrix"]["os"] == runners


def test_independent_coverage() -> None:
    def item(covered: int, statements: int) -> dict[str, object]:
        return {"summary": {"covered_lines": covered, "num_statements": statements}}

    data: dict[str, object] = {
        "files": {
            "src/clavis/a.py": item(100, 100),
            "scripts/a.py": item(100, 100),
            "eval/a.py": item(7, 10),
        }
    }
    assert ci_results.coverage_gates(data) == {
        "overall": True,
        "platform": True,
        "eval": False,
        "jobs": False,
    }
    assert not any(ci_results.coverage_gates({"files": {}}).values())


def test_public_workflow_permissions_and_draft_gate() -> None:
    import yaml

    workflow = yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    assert workflow["permissions"]["contents"] == "read"
    assert set(workflow["permissions"].values()) == {"read"}
    assert "pull_request_target" not in workflow["on"]
    assert "ready_for_review" in workflow["on"]["pull_request"]["types"]
    assert "!github.event.pull_request.draft" in workflow["jobs"]["plan"]["if"]


@pytest.mark.parametrize("outcome", ["", "<skipped/>", "<failure/>", "<error/>"])
def test_required_outcomes(tmp_path: Path, outcome: str) -> None:
    path = tmp_path / "tests.xml"
    path.write_text(
        '<testsuites><testsuite><testcase classname="tests.contracts.test_a"/>'
        '<testcase classname="tests.eval.test_integrity">'
        + outcome
        + "</testcase></testsuite></testsuites>"
    )
    result = ci_results.required_tests(path)
    assert result["contracts"]["status"] == "PASS"
    assert result["integrity-positive-negative"]["status"] == ("FAIL" if outcome else "PASS")
    path.write_text("<testsuites/>")
    assert all(r["status"] == "FAIL" for r in ci_results.required_tests(path).values())


@pytest.mark.parametrize("mode", ["coverage", "required"])
def test_results_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    path = tmp_path / "input"
    path.write_text('{"files": {}}' if mode == "coverage" else "<testsuites/>")
    monkeypatch.setattr(sys, "argv", ["ci_results", mode, str(path)])
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    assert ci_results.main() == 1
    assert mode in (tmp_path / "summary").read_text()


@pytest.mark.parametrize("event", ["pull_request", "schedule", "push", "workflow_dispatch"])
def test_plan_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, event: str) -> None:
    monkeypatch.chdir(tmp_path)
    payload = {
        "number": 3,
        "pull_request": {"draft": False, "changed_files": 1, "base": {"sha": "base"}},
    }
    (tmp_path / "event.json").write_text(json.dumps(payload))
    (tmp_path / "README.md").write_text("# test")
    for key, value in {
        "GITHUB_EVENT_NAME": event,
        "GITHUB_EVENT_PATH": "event.json",
        "GITHUB_OUTPUT": "output",
        "GITHUB_RUN_ID": "2",
        "GITHUB_SHA": "same",
    }.items():
        monkeypatch.setenv(key, value)
    response = (
        [{"filename": "README.md", "previous_filename": "docs/old.md"}]
        if event == "pull_request"
        else {"workflow_runs": [{"id": 1, "head_sha": "same"}]}
    )
    with (
        patch.object(ci_plan, "api", return_value=response),
        patch.object(ci_plan.subprocess, "run"),
    ):
        ci_plan.main()
    assert "quality=" in (tmp_path / "output").read_text()


def test_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "GITHUB_API_URL": "https://api.example.invalid",
        "GITHUB_REPOSITORY": "owner/repo",
        "GH_TOKEN": "test",
    }.items():
        monkeypatch.setenv(key, value)
    path = tmp_path / "response"
    path.write_text('{"ok": true}')
    with (
        path.open("rb") as response,
        patch.object(ci_plan.urllib.request, "urlopen", return_value=response),
    ):
        assert ci_plan.api("runs") == {"ok": True}
