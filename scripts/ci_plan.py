"""Select CI jobs using event metadata; never inspect private data."""

import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


def plan(
    event: str, files: list[str], *, draft: bool = False, changed: bool = True
) -> dict[str, Any]:
    docs = bool(files) and all(p.startswith("docs/") or p.endswith(".md") for p in files)
    windows = any(
        p in {"pyproject.toml", "uv.lock"} or p.startswith((".github/", "scripts/")) for p in files
    )
    if event == "pull_request":
        runners = (
            [] if draft or docs else ["ubuntu-latest"] + (["windows-latest"] if windows else [])
        )
    elif event == "push":
        runners = ["ubuntu-latest"]
    else:
        runners = ["windows-latest"] if event == "workflow_dispatch" or changed else []
    return {
        "docs": event == "pull_request" and docs and not draft,
        "quality": bool(runners),
        "matrix": {"os": runners or ["ubuntu-latest"]},
    }


def api(path: str) -> Any:
    request = urllib.request.Request(
        f"{os.environ['GITHUB_API_URL']}/repos/{os.environ['GITHUB_REPOSITORY']}/{path}",
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    event = os.environ["GITHUB_EVENT_NAME"]
    payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    files: list[str] = []
    changed = True
    if event == "pull_request":
        page = 1
        while True:
            batch = api(f"pulls/{payload['number']}/files?per_page=100&page={page}")
            for item in batch:
                files.append(item["filename"])
                if "previous_filename" in item:
                    files.append(item["previous_filename"])
            if len(batch) < 100:
                break
            page += 1
        # API has a 3000-file cap: never classify a truncated list as documentation-only.
        if payload["pull_request"]["changed_files"] > 3000:
            files.extend(["src/unknown", "scripts/unknown"])
    elif event == "schedule":
        runs = api("actions/workflows/ci.yml/runs?event=schedule&status=success&per_page=100")
        prior = [r for r in runs["workflow_runs"] if str(r["id"]) != os.environ["GITHUB_RUN_ID"]]
        changed = not prior or prior[0]["head_sha"] != os.environ["GITHUB_SHA"]
    result = plan(
        event, files, draft=payload.get("pull_request", {}).get("draft", False), changed=changed
    )
    if result["docs"]:
        for name in files:
            path = Path(name)
            if path.is_file() and path.suffix in {".md", ".json", ".yaml", ".yml"}:
                text = path.read_text(encoding="utf-8")
                if path.suffix == ".json":
                    json.loads(text)
                if "\x00" in text:
                    raise ValueError(f"NUL in document: {name}")
        subprocess.run(
            ["git", "diff", "--check", payload["pull_request"]["base"]["sha"], "HEAD"], check=True
        )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        for key, value in result.items():
            output.write(f"{key}={json.dumps(value)}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
