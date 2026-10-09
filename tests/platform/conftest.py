"""Per-test child stderr capture, retained only locally and redacted on assertions."""

import json
import subprocess
from pathlib import Path

import pytest


def redacted(text):
    for path, replacement in [(Path.cwd(), "."), (Path.home(), "%USERPROFILE%")]:
        text = text.replace(str(path), replacement).replace(path.as_posix(), replacement)
    return text


@pytest.fixture
def child_diagnostics(tmp_path, monkeypatch):
    original = subprocess.Popen
    logs = []

    def capture(*args, **kwargs):
        if kwargs.get("stderr") == subprocess.DEVNULL:
            path = tmp_path / f"child-stderr-{len(logs)}.txt"
            logs.append(path)
            with path.open("wb") as stream:
                kwargs["stderr"] = stream
                return original(*args, **kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", capture)

    def explain(report):
        return redacted(
            json.dumps(report)
            + "\nchild stderr:\n"
            + "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in logs)
        )

    return explain
