import hashlib
import io
import json
import threading
import time
import urllib.error
from unittest.mock import MagicMock

import pytest

from training.data import pdmx_download as downloader


def settings() -> dict:
    return {
        "connections": 1,
        "segment_bytes": 4,
        "attempts": 2,
        "timeout_seconds": 1,
        "backoff_seconds": 0,
        "backoff_max_seconds": 0,
    }


def expected(payload: bytes) -> dict:
    return {
        "url": "https://example.org/source",
        "size": len(payload),
        "checksum": "md5:" + hashlib.md5(payload, usedforsecurity=False).hexdigest(),
    }


class Response(io.BytesIO):
    def __init__(self, body: bytes, start: int, end: int, size: int) -> None:
        super().__init__(body)
        self.status = 206
        self.headers = {"Content-Range": f"bytes {start}-{end}/{size}"}


def test_interruption_resume_and_corrupt_segment_repair(tmp_path, monkeypatch):
    payload = b"abcdefghijkl"
    ranges = []
    fail = True

    def open_range(request, timeout):
        nonlocal fail
        start, end = map(int, request.get_header("Range").removeprefix("bytes=").split("-"))
        ranges.append(start)
        if start == 4 and fail:
            raise ValueError("simulated process interruption")
        return Response(payload[start : end + 1], start, end, len(payload))

    monkeypatch.setattr(downloader.urllib.request, "urlopen", open_range)
    path = tmp_path / "source"
    with pytest.raises(ValueError, match="interruption"):
        downloader.download(expected(payload), path, settings(), 0, lambda n: None)
    completed = json.loads(path.with_suffix(".ranges.json").read_text())["completed"]
    assert "0" in completed
    fail = False
    ranges.clear()
    evidence = downloader.download(expected(payload), path, settings(), 0, lambda n: None)
    assert 0 not in ranges
    assert path.read_bytes() == payload
    assert evidence["sha256"] == hashlib.sha256(payload).hexdigest()
    with path.open("r+b") as file:
        file.write(b"X")
    ranges.clear()
    downloader.download(expected(payload), path, settings(), 0, lambda n: None)
    assert ranges == [0]
    assert path.read_bytes() == payload


@pytest.mark.parametrize("code", [429, 503])
def test_rate_limit_retry_and_transfer_measurement(tmp_path, monkeypatch, code):
    attempts, transferred = [], []

    def open_range(request, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(request.full_url, code, "busy", {"Retry-After": "0"}, None)
        return Response(b"abcd", 0, 3, 4)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", open_range)
    downloader.download(expected(b"abcd"), tmp_path / "s", settings(), 0, transferred.append)
    assert len(attempts) == 2 and sum(transferred) == 4


@pytest.mark.parametrize("fault", ["status", "range", "encoding", "oversize", "short", "md5"])
def test_untrusted_responses_never_verify(tmp_path, monkeypatch, fault):
    def open_range(request, timeout):
        body = {"oversize": b"abcde", "short": b"abc", "md5": b"XXXX"}.get(fault, b"abcd")
        response = Response(body, 0, 3, 4)
        if fault == "status":
            response.status = 200
        if fault == "range":
            response.headers["Content-Range"] = "bytes 1-4/4"
        if fault == "encoding":
            response.headers["Content-Encoding"] = "gzip"
        return response

    monkeypatch.setattr(downloader.urllib.request, "urlopen", open_range)
    with pytest.raises((ValueError, OSError)):
        downloader.download(expected(b"abcd"), tmp_path / "s", settings(), 0, lambda n: None)


def test_disk_guard_provenance_lock_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "ROOT", tmp_path / "repo")
    monkeypatch.setattr(downloader.shutil, "disk_usage", lambda p: MagicMock(free=5))
    config = {"files": {"PDMX.csv": expected(b"abcd")}, "min_free_disk_bytes": 3}
    with pytest.raises(ValueError, match="outside"):
        downloader.prepare(config, tmp_path / "repo", lambda n: None)
    with pytest.raises(ValueError, match="need 7"):
        downloader.prepare(config, tmp_path / "cache", lambda n: None)
    with downloader.cache_lock(tmp_path / "lock"):
        with pytest.raises(OSError), downloader.cache_lock(tmp_path / "lock"):
            pass
    with downloader.cache_lock(tmp_path / "lock"):
        pass
    with pytest.raises(ValueError, match="resource"):
        downloader.download(
            expected(b"a"), tmp_path / "s", {**settings(), "connections": 5}, 0, lambda n: None
        )
    assert downloader.retry_delay("invalid", 3) == 3
    assert downloader.retry_delay("10", 3) == 10
    assert downloader.retry_delay("Wed, 01 Jan 2020 00:00:00 GMT", 3) == 3
    (tmp_path / "s").write_bytes(b"bad")
    with pytest.raises(ValueError, match="size changed"):
        downloader.download(expected(b"a"), tmp_path / "s", settings(), 0, lambda n: None)
    journal = tmp_path / "s.ranges.json"
    journal.write_text(json.dumps({"source": {}}))
    with pytest.raises(ValueError, match="provenance"):
        downloader.download(expected(b"a"), tmp_path / "s", settings(), 0, lambda n: None)


def test_prepare_four_connections_and_cached_no_network(tmp_path, monkeypatch):
    payload = b"a" * 32
    active, peak = 0, 0
    lock = threading.Lock()

    def open_range(request, timeout):
        nonlocal active, peak
        start, end = map(int, request.get_header("Range").removeprefix("bytes=").split("-"))
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.01)
        with lock:
            active -= 1
        return Response(payload[start : end + 1], start, end, len(payload))

    monkeypatch.setattr(downloader.urllib.request, "urlopen", open_range)
    monkeypatch.setattr(downloader, "ROOT", tmp_path / "repo")
    config = {
        "files": {name: expected(payload) for name in ("PDMX.csv", "mxl.tar.gz")},
        "min_free_disk_bytes": 0,
        "download": {**settings(), "connections": 4},
    }
    evidence = downloader.prepare(config, tmp_path / "cache", lambda n: None)
    assert 1 < peak <= 4
    assert evidence["PDMX.csv"]["verified"]
    assert evidence["mxl.tar.gz"]["verified"]
    monkeypatch.setattr(
        downloader.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("cache hit went online")
    )
    assert (
        downloader.prepare(config, tmp_path / "cache", lambda n: None)["mxl.tar.gz"]
        == evidence["mxl.tar.gz"]
    )
