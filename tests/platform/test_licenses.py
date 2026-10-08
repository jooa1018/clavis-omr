import json
import subprocess
from unittest.mock import patch

import pytest

from scripts.check_licenses import main, runtime_packages, violations


def test_runtime_closure_handles_cycles_and_markers() -> None:
    graph = {"a": ["b>=1", "c; python_version < '3'"], "b": ["a"]}
    with patch("scripts.check_licenses.requires", side_effect=graph.get):
        assert runtime_packages(["A"]) == ["a", "b"]


def test_runtime_extras_require_review() -> None:
    with pytest.raises(ValueError, match="license review"):
        runtime_packages(["example[extra]"])


@pytest.mark.parametrize("license_name", ["GPL-3.0", "AGPL-3.0", "UNKNOWN", "MIT AND GPL-3.0"])
def test_prohibited_and_unknown_licenses_fail(license_name: str) -> None:
    assert violations([{"Name": "A", "License": license_name}], ["a"]) == ["a"]


def test_missing_license_is_not_a_pass() -> None:
    assert violations([], ["a"]) == ["a"]


def test_allowed_license_and_canonical_names() -> None:
    assert violations([{"Name": "some_pkg", "License": "MIT"}], ["some-pkg"]) == []


@pytest.mark.parametrize("license_name,code", [("MIT", 0), ("UNKNOWN", 1)])
def test_audit_exit_status(license_name: str, code: int) -> None:
    result = subprocess.CompletedProcess(
        [], 0, json.dumps([{"Name": "a", "License": license_name}])
    )
    with (
        patch("scripts.check_licenses.runtime_packages", return_value=["a"]),
        patch("scripts.check_licenses.subprocess.run", return_value=result),
    ):
        assert main() == code


@pytest.mark.parametrize("name", ["pillow", "other-package"])
def test_mit_cmu_is_generally_allowed(name: str) -> None:
    assert violations([{"Name": name, "License": "MIT-CMU"}], [name]) == []
