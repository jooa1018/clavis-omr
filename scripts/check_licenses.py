"""Audit the installed runtime dependency closure using pip-licenses metadata."""

import json
import subprocess
import sys
import tomllib
from importlib.metadata import requires
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# Proposed Pillow 11.2.1 metadata spelling; requires Orchestrator review in this PR.
PACKAGE_LICENSES = {("pillow", "11.2.1"): "MIT-CMU"}

ALLOWED = frozenset(
    {
        "MIT",
        "MIT License",
        "BSD",
        "BSD License",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "Apache-2.0",
        "Apache Software License",
        "ISC",
        "ISC License (ISCL)",
        "PSF-2.0",
        "Python Software Foundation License",
        "Zlib",
        "zlib/libpng License",
        "HPND",
        "Historical Permission Notice and Disclaimer (HPND)",
        "MPL-2.0",
        "Mozilla Public License 2.0 (MPL 2.0)",
    }
)


def runtime_packages(requirements: list[str]) -> list[str]:
    """Resolve installed default (non-extra) requirements; missing metadata fails closed."""
    pending = list(requirements)
    found: set[str] = set()
    while pending:
        requirement = Requirement(pending.pop())
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        if requirement.extras:
            raise ValueError("Runtime extras require an explicit license review")
        name = canonicalize_name(requirement.name)
        if name not in found:
            found.add(name)
            pending.extend(requires(name) or [])
    return sorted(found)


def violations(rows: list[dict[str, str]], expected: list[str]) -> list[str]:
    """Unknown, mixed and unreported licenses require review, never silent acceptance."""
    licenses: dict[str, dict[str, str]] = {canonicalize_name(row["Name"]): row for row in rows}
    return [
        name
        for name in expected
        if name not in licenses
        or (
            licenses[name]["License"] not in ALLOWED
            and PACKAGE_LICENSES.get((name, licenses[name].get("Version", "")))
            != licenses[name]["License"]
        )
    ]


def main() -> int:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    packages = runtime_packages(config["project"]["dependencies"])
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "piplicenses",
            "--format=json",
            "--with-system",
            "--packages",
            *packages,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    rows = json.loads(result.stdout)
    failures = violations(rows, packages)
    print(
        json.dumps({"scope": "runtime", "packages": rows, "violations": failures}, sort_keys=True)
    )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
