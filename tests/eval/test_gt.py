from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval.gt import Manifest, Sidecar
from eval.gt.__main__ import (
    REPOSITORY,
    audit,
    contained,
    digest,
    main,
    private_root,
    selected_systems,
    validate_page,
)


def sample(root: Path) -> dict:
    for name, content in (
        ("original.png", b"synthetic fixture bytes"),
        ("render.pdf", b"synthetic render bytes"),
        (
            "score.musicxml",
            b'<score-partwise version="4.0"><part id="P1"><measure number="1"/>'
            b'<measure number="2"/></part></score-partwise>',
        ),
    ):
        (root / name).write_bytes(content)
    data = {
        "schemaVersion": "clavis-gt-1",
        "pageId": "dev-001",
        "songId": "song-001",
        "captureId": "session-001",
        "printId": None,
        "tier": "R-TGT",
        "split": "dev",
        "devPartition": "Dev-Tune",
        "sourceKind": "camera-photo",
        "captureChannel": "messenger",
        "captureDevice": None,
        "engravingTool": None,
        "musicFont": None,
        "measuredInterlinePx": 10.0,
        "meter": "4/4",
        "keyMode": "major",
        "features": [],
        "notationFeatures": [],
        "leadStaff": {"part": "P1", "staff": 1, "voices": ["1"]},
        "imagePath": "original.png",
        "imageDigest": digest(root / "original.png"),
        "musicXmlPath": "score.musicxml",
        "groundTruthDigest": digest(root / "score.musicxml"),
        "renderPath": "render.pdf",
        "renderDigest": digest(root / "render.pdf"),
        "evalRegions": [
            {
                "systemIndex": 1,
                "sourceMeasureLabels": ["1"],
                "xmlMeasureStart": 1,
                "xmlMeasureEnd": 1,
                "bbox": [0, 0, 100, 50],
            },
            {
                "systemIndex": 2,
                "sourceMeasureLabels": ["2"],
                "xmlMeasureStart": 2,
                "xmlMeasureEnd": 2,
                "bbox": [0, 50, 100, 50],
            },
        ],
        "illegibleRegions": [],
        "selection": {
            "method": "sha256-rank-v1",
            "seed": "test",
            "totalSystems": 2,
            "selectedSystems": [1, 2],
            "recordedOn": "2026-09-01",
        },
        "rights": {
            "basis": "user-confirmed-rights",
            "allowedUses": ["evaluation"],
            "reference": "synthetic fixture",
        },
        "review": {
            "transcribedOn": "2026-09-01",
            "renderedComparedOn": "2026-09-01",
            "reviewedOn": "2026-09-02",
            "reviewer": "custodian",
            "independentReviewer": False,
            "allSelectedMeasuresChecked": True,
        },
        "legacy": False,
        "contaminated": False,
        "assisted": False,
        "notes": "synthetic only",
    }
    (root / "gt.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_schema_and_private_validation(tmp_path: Path) -> None:
    sample(tmp_path)
    page = validate_page(tmp_path, "gt.json")
    assert audit([page])["status"] == "PARTIAL"
    assert "Dev-v0-below20" in audit([page])["coverageGaps"]
    assert "duplicate-page" in audit([page, page])["issues"]
    other = page.model_copy(update={"pageId": "other", "devPartition": "Dev-Check"})
    assert "split-overlap:songId" in audit([page, other])["issues"]
    for name, model in (("gt", Sidecar), ("gt-manifest", Manifest)):
        actual = json.loads((REPOSITORY / "configs/eval" / f"{name}.schema.json").read_text())
        assert actual == model.model_json_schema()
    (tmp_path / "original.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest"):
        validate_page(tmp_path, "gt.json")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("split", "sealed"),
        ("tier", "R-LEGACY"),
        ("legacy", True),
        ("evalRegions", []),
        ("devPartition", None),
    ],
)
def test_provenance_rejection(tmp_path: Path, field: str, value: object) -> None:
    data = sample(tmp_path)
    if field == "evalRegions":
        data["selection"]["totalSystems"] = 4
    data[field] = value
    with pytest.raises(ValidationError):
        Sidecar.model_validate_json(json.dumps(data))


def test_review_regions_rights_and_selection(tmp_path: Path) -> None:
    data = sample(tmp_path)
    data["review"]["reviewedOn"] = "2026-09-01"
    with pytest.raises(ValidationError, match="later day"):
        Sidecar.model_validate_json(json.dumps(data))
    data = sample(tmp_path)
    data["rights"]["allowedUses"].append("training")
    with pytest.raises(ValidationError, match="evaluation-only"):
        Sidecar.model_validate_json(json.dumps(data))
    data = sample(tmp_path)
    data["evalRegions"][1]["xmlMeasureStart"] = 1
    with pytest.raises(ValidationError, match="map mismatch"):
        Sidecar.model_validate_json(json.dumps(data))
    expected = selected_systems("page", 7, 3, "seed")
    assert expected == selected_systems("page", 7, 3, "seed")
    assert len(set(expected)) == 3
    with pytest.raises(ValueError):
        selected_systems("page", 2, 3, "seed")


def test_root_and_path_restrictions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAVIS_PRIVATE_ROOT", raising=False)
    with pytest.raises(ValueError):
        private_root()
    monkeypatch.setenv("CLAVIS_PRIVATE_ROOT", str(REPOSITORY))
    with pytest.raises(ValueError):
        private_root()
    monkeypatch.setenv("CLAVIS_PRIVATE_ROOT", str(tmp_path))
    monkeypatch.chdir(REPOSITORY)
    assert private_root() == tmp_path.resolve()
    for bad in ("../escape", "C:/escape", "a\\b", "/absolute"):
        with pytest.raises(ValueError):
            contained(tmp_path, bad)
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError):
        private_root()


def test_cli_and_sealed_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLAVIS_PRIVATE_ROOT", str(tmp_path))
    monkeypatch.chdir(REPOSITORY)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gt",
            "select",
            "--page-id",
            "dev-001",
            "--systems",
            "4",
            "--seed",
            "chosen-first",
            "--date",
            "2026-09-01",
            "--out",
            "dev/dev-001/selection.json",
        ],
    )
    assert main() == 0
    assert (tmp_path / "dev/dev-001/selection.json").is_file()
    assert not (REPOSITORY / "dev/dev-001/selection.json").exists()
    assert main() == 1
    data = sample(tmp_path)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": "clavis-gt-manifest-1",
                "datasetVersion": "test",
                "sidecars": ["gt.json"],
            }
        )
    )
    monkeypatch.setattr(
        sys, "argv", ["gt", "validate", "--manifest", "manifest.json", "--out", "report.json"]
    )
    assert main() == 0
    data["split"] = "sealed"
    data["imagePath"] = "private-secret-path"
    (tmp_path / "gt.json").write_text(json.dumps(data))
    monkeypatch.setattr(
        sys,
        "argv",
        ["gt", "validate", "--manifest", "manifest.json", "--out", "second-report.json"],
    )
    assert main() == 1
    assert "private-secret-path" not in capsys.readouterr().out
