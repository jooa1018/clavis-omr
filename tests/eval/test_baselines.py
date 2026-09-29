import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from eval.baselines import command, run
from eval.baselines.__main__ import main
from eval.policy import config


@pytest.mark.parametrize("engine", ["audiveris", "homr", "oemer"])
def test_fixed_offline_commands(engine: str, tmp_path: Path) -> None:
    args = command(engine, "sha256:" + "a" * 64, tmp_path, ".png")
    assert "--network=none" in args and "--pull=never" in args
    assert "--read-only" in args and "--cap-drop=ALL" in args
    assert not any("gpu" in arg for arg in args)
    assert "/work/input.png" in args
    with pytest.raises(ValueError):
        command(engine, "latest", tmp_path, ".png")
    with pytest.raises(ValueError):
        command(engine, "sha256:" + "a" * 64, tmp_path, ".pdf")


@pytest.mark.parametrize("mode", ["success", "crash", "timeout", "empty", "wrong-version"])
def test_lifecycle_cache_and_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    image = "sha256:" + "a" * 64
    calls: list[list[str]] = []

    def fake(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(args)
        if args[1:3] == ["image", "inspect"]:
            labels = {
                "org.clavis.baseline": "homr",
                "org.clavis.version": config("baselines.json")["engines"]["homr"]["version"]
                if mode != "wrong-version"
                else "other",
                "org.clavis.lockDigest": "b" * 64,
                "org.clavis.weightsDigest": "c" * 64,
            }
            return subprocess.CompletedProcess(
                args, 0, json.dumps([{"Id": image, "Config": {"Labels": labels}}]).encode()
            )
        if args[1] == "run":
            directory = Path(args[args.index("--cidfile") + 1]).parent
            (directory / "container.id").write_text("d" * 64)
            if mode == "timeout":
                raise subprocess.TimeoutExpired(args, 480)
            if mode == "success":
                (directory / "out/one.musicxml").write_text('<score-partwise version="4.0"/>')
                (directory / "out/two.musicxml").write_text('<score-partwise version="4.0"/>')
            return subprocess.CompletedProcess(args, 1 if mode == "crash" else 0, b"")
        return subprocess.CompletedProcess(args, 0, b"")

    monkeypatch.setattr(subprocess, "run", fake)
    source = tmp_path / "page.png"
    source.write_bytes(b"synthetic fixture")
    if mode == "wrong-version":
        with pytest.raises(ValueError, match="provenance"):
            run("homr", image, source, tmp_path / "cache", "e" * 64)
        assert not any(call[1] == "run" for call in calls)
        return
    result = run("homr", image, source, tmp_path / "cache", "e" * 64)
    assert result["status"] == ("PASS" if mode == "success" else "FAIL")
    assert any(call[1] == "rm" for call in calls)
    assert len(result["outputs"]) == (2 if mode == "success" else 0)
    assert run("homr", image, source, tmp_path / "cache", "e" * 64) == result
    assert sum(call[1] == "run" for call in calls) == 1
    if mode == "success":
        cached = tmp_path / "cache" / result["cacheKey"] / result["outputs"][0]["file"]
        cached.write_bytes(b"corrupt")
        with pytest.raises(ValueError, match="corrupted"):
            run("homr", image, source, tmp_path / "cache", "e" * 64)


def test_real_external_stub_is_separate_process(tmp_path: Path) -> None:
    # Exercise the runner through real processes; this does not test Docker itself.
    stub = tmp_path / "stub.py"
    image = "sha256:" + "a" * 64
    infos = [
        {
            "Id": image,
            "Config": {
                "Labels": {
                    "org.clavis.baseline": "oemer",
                    "org.clavis.version": "0.1.8",
                    "org.clavis.lockDigest": "b" * 64,
                    "org.clavis.weightsDigest": "c" * 64,
                }
            },
        }
    ]
    stub.write_text(
        "import pathlib,sys\n"
        f"if sys.argv[1:3] == ['image', 'inspect']: print({json.dumps(json.dumps(infos))})\n"
        "elif sys.argv[1] == 'run':\n"
        " assert '--network=none' in sys.argv\n"
        " folder = pathlib.Path(sys.argv[sys.argv.index('--cidfile') + 1]).parent\n"
        " (folder/'container.id').write_text('d'*64)\n"
        " (folder/'out/result.musicxml').write_text('<score-partwise/>')\n"
    )
    source = tmp_path / "page.png"
    source.write_bytes(b"synthetic")
    result = run("oemer", image, source, tmp_path / "cache", "e" * 64, (sys.executable, str(stub)))
    assert result["status"] == "PASS" and len(result["outputs"]) == 1


def test_cli_missing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAVIS_PRIVATE_ROOT", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "baseline",
            "oemer",
            "--image-id",
            "sha256:" + "a" * 64,
            "--input",
            "x.png",
            "--cache",
            "cache",
            "--dataset-digest",
            "b" * 64,
            "--manual-or001",
        ],
    )
    assert main() == 2
