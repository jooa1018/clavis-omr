import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.data.smoke_inputs import score
from training.data import smoke, verovio_worker
from training.data.licenses import require_use


def test_registry_required_fields_and_denied_uses() -> None:
    registry = json.loads((smoke.ROOT / "training/data/licenses/sources.json").read_text())
    ids = [row["id"] for row in registry["sources"]]
    assert len(ids) == len(set(ids))
    for row in registry["sources"]:
        assert {
            "name",
            "url",
            "version",
            "license",
            "allowed_uses",
            "attribution",
            "checked_on",
            "verification_method",
            "status",
        } <= row.keys()
        for purpose in ("train", "weights"):
            with pytest.raises(ValueError):
                require_use(row["id"], purpose)
    with pytest.raises(ValueError):
        require_use("unknown", "train")
    require_use("leipzig", "render-font")


def test_score_is_deterministic_valid_and_train_only() -> None:
    for fifths in range(-5, 5):
        xml = score("train-test", fifths=fifths, beats=3, staves=2)
        assert xml == score("train-test", fifths=fifths, beats=3, staves=2)
        root = ET.fromstring(xml)
        for measure in root.findall(".//measure"):
            for staff in ("1", "2"):
                assert (
                    sum(
                        int(n.findtext("duration"))
                        for n in measure.findall("note")
                        if n.findtext("staff") == staff
                    )
                    == 3
                )
    with pytest.raises(ValueError):
        score("eval-bad", fifths=0, beats=4, staves=1)
    contours = set()
    for index in range(10):
        root = ET.fromstring(score(f"train-smoke-{index}", fifths=0, beats=4, staves=1))
        pitches = [
            "CDEFGAB".index(p.findtext("step")) + 7 * int(p.findtext("octave"))
            for p in root.findall(".//pitch")
        ]
        contours.add(tuple(b - a for a, b in zip(pitches, pitches[1:], strict=False)))
    assert len(contours) == 10


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "ROOT", tmp_path)
    return tmp_path / "work/smoke"


def test_prepare_only_has_30_quarantined_jobs(sandbox) -> None:
    with patch.object(smoke.subprocess, "run") as process:
        result = smoke.run(sandbox)
    process.assert_not_called()
    assert result["status"] == "NOT_RUN"
    assert len(result["jobs"]) == 30
    assert len({job["input_sha256"] for job in result["jobs"]}) == 10
    assert "BLOCKED" in result["training_admission"]
    assert not (smoke.ROOT / "data/manifests/train").exists()


def test_output_outside_quarantine_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="quarantined"):
        smoke.run(tmp_path)


def test_mock_render_resume_and_failure(sandbox) -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
    payload = json.dumps({"version": "mock", "options": {}, "pages": [svg]})
    completed = subprocess.CompletedProcess([], 0, payload.encode())
    with (
        patch.object(smoke.subprocess, "run", return_value=completed),
        patch.object(smoke, "extract", return_value=([], svg)),
        patch.object(smoke.shutil, "disk_usage", return_value=MagicMock(free=10**10)),
    ):
        report = smoke.run(sandbox, Path(sys.executable))
        assert all(row["status"] == "RENDERED_PENDING_VISUAL_AUDIT" for row in report["jobs"])
        with patch.object(smoke.subprocess, "run") as process:
            smoke.run(sandbox, Path(sys.executable))
            process.assert_not_called()
        artifact = next(sandbox.rglob("page-1.labels.json"))
        artifact.write_text("corrupted")
        with patch.object(
            smoke.subprocess, "run", side_effect=subprocess.TimeoutExpired("mock", 1)
        ):
            report = smoke.run(sandbox, Path(sys.executable))
            assert sum(row["status"] == "FAIL" for row in report["jobs"]) == 1
        for checkpoint in sandbox.rglob("complete.json"):
            checkpoint.write_text("{")
        with patch.object(smoke.shutil, "disk_usage", return_value=MagicMock(free=0)):
            report = smoke.run(sandbox, Path(sys.executable))
            assert all(row["status"] == "FAIL" for row in report["jobs"])
            assert all(row["phase"] == "storage" for row in report["jobs"])


def test_worker_uses_pinned_version_and_checked_options(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["worker", str(smoke.CONFIG), "Leipzig"])
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"<score-partwise/>")))
    toolkit = MagicMock()
    toolkit.getPageCount.return_value = 1
    toolkit.getVersion.return_value = "6.3.0-mock"
    toolkit.renderToSVG.return_value = "<svg/>"
    with (
        patch.object(verovio_worker, "version", return_value="6.3.0"),
        patch.object(
            verovio_worker.importlib,
            "import_module",
            return_value=MagicMock(toolkit=lambda: toolkit),
        ),
    ):
        verovio_worker.main()
    result = json.loads(capsys.readouterr().out)
    assert result["pages"] == ["<svg/>"]
    assert result["options"]["svgAdditionalAttribute"] == ["staff@n"]
    with patch.object(verovio_worker, "version", return_value="0"):
        with pytest.raises(ValueError, match="version"):
            verovio_worker.main()
