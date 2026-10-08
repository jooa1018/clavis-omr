"""Synthetic identifiers are assembled to keep negative examples out of the tree."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import check_privacy as privacy


@pytest.mark.parametrize(
    "prefix", ["C:" + "\\Users\\", "C:" + "/Users/", "/" + "home/", "/" + "Users/"]
)
@pytest.mark.parametrize("encode", [str, json.dumps])
def test_profile_paths(prefix: str, encode: object) -> None:
    value = prefix + "synthetic-person" + "/file"
    text = json.dumps(value) if encode is json.dumps else value
    assert privacy.inspect_text("docs/report.md", text)[0]["rule"] == "PRIVACY-PROFILE"


@pytest.mark.parametrize("name", sorted(privacy.PLACEHOLDERS))
def test_document_placeholders_only(name: str) -> None:
    text = "C:" + "/Users/" + name + "/file"
    assert not privacy.inspect_text("docs/guide.md", text)
    assert privacy.inspect_text("src/example.py", text)


@pytest.mark.parametrize(
    "key", ["host" + "name", "computer" + "Name", "HOST_NAME", "computer-name"]
)
@pytest.mark.parametrize("style", ["json", "yaml", "assignment"])
def test_host_fields(key: str, style: str) -> None:
    text = {
        "json": json.dumps({key: "synthetic-device"}),
        "yaml": "- " + key + ": synthetic-device",
        "assignment": key + " = 'synthetic-device'",
    }[style]
    assert privacy.inspect_text("report.txt", text)[0]["rule"] == "PRIVACY-HOST-FIELD"


def test_safe_references() -> None:
    text = "%USERPROFILE% CLAVIS_PRIVATE_ROOT docs/a.md /tests/hostname hostname·computerName"
    assert not privacy.inspect_text("docs/report.md", text)


def test_tracked_files_and_redacted_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    tracked = tmp_path / "report.json"
    tracked.write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "report.json"], cwd=tmp_path, check=True)
    bad = json.dumps({"computer" + "Name": "synthetic-device"})
    (tmp_path / "untracked.json").write_text(bad, encoding="utf-8")
    assert privacy.scan(tmp_path)["status"] == "PASS"
    tracked.write_text(bad, encoding="utf-8")  # Unstaged edits must also be checked.
    output = tmp_path / "work" / "report.json"
    monkeypatch.setattr(sys, "argv", ["privacy", "--root", str(tmp_path), "--out", str(output)])
    assert privacy.main() == 1
    report = output.read_text(encoding="utf-8")
    assert "synthetic-device" not in report
    assert str(tmp_path) not in report
    assert json.loads(report)["findings"][0]["file"] == "report.json"
    tracked.write_text("{}", encoding="utf-8")
    assert privacy.main() == 0
    with patch.object(Path, "is_symlink", return_value=True):
        assert privacy.scan(tmp_path)["status"] == "FAIL"
    tracked.unlink()
    assert privacy.scan(tmp_path)["status"] == "FAIL"


def test_enumeration_failure_is_redacted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["privacy", "--root", str(tmp_path)])
    assert privacy.main() == 1


def test_privacy_gate_covers_docs_and_quality() -> None:
    import yaml

    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    for job in ("plan", "quality"):
        assert any(
            "scripts/check_privacy.py" in step.get("run", "")
            for step in workflow["jobs"][job]["steps"]
        )
