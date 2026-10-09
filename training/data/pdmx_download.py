"""OR-004 range cache: bounded connections, durable segments, publisher verification."""

import hashlib
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from training.data.smoke import ROOT, write_json


@contextmanager
def cache_lock(cache: Path) -> Iterator[None]:
    """An OS lock is released even on process death; lock files contain no source data."""
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / "download.lock").open("a+b") as handle:
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def verify(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    """Verify the complete stored file, never trusting an old success marker."""
    md5, sha = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            md5.update(chunk)
            sha.update(chunk)
    if size != expected["size"] or "md5:" + md5.hexdigest() != expected["checksum"]:
        raise ValueError("Publisher size/MD5 verification failed")
    return {"size": size, "md5": md5.hexdigest(), "sha256": sha.hexdigest(), "verified": True}


def retry_delay(header: str | None, fallback: float) -> float:
    """Honor Retry-After seconds or HTTP date; otherwise use exponential backoff."""
    if header:
        try:
            return max(fallback, float(header))
        except ValueError:
            try:
                return max(
                    fallback,
                    (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds(),
                )
            except (ValueError, TypeError, OverflowError):
                pass
    return fallback


def download(
    expected: dict[str, Any],
    path: Path,
    settings: dict[str, Any],
    min_free: int,
    transferred: Callable[[int], None],
) -> dict[str, Any]:
    """Persist segment digests only after file fsync; missing/corrupt ranges are retried."""
    segment_bytes, workers = settings["segment_bytes"], settings["connections"]
    if not 1 <= workers <= 4 or not 1 <= segment_bytes <= settings["max_segment_bytes"]:
        raise ValueError("Invalid range resource limits")
    size = expected["size"]
    if size <= 0:
        raise ValueError("Invalid source size")
    journal = path.with_suffix(path.suffix + ".ranges.json")
    identity = {"source": expected, "segment_bytes": segment_bytes}
    state: dict[str, Any] = {**identity, "completed": {}}
    if journal.exists():
        state = json.loads(journal.read_text(encoding="utf-8"))
        if any(state.get(k) != v for k, v in identity.items()):
            raise ValueError("Range checkpoint provenance mismatch")
    if not path.exists():
        state["completed"] = {}
        with path.open("xb") as target:
            target.truncate(size)
    if path.stat().st_size != size:
        raise ValueError("Range cache size changed")
    starts = list(range(0, size, segment_bytes))
    with path.open("rb") as source:
        for key in list(state["completed"]):
            start = int(key)
            if start not in starts:
                raise ValueError("Invalid range checkpoint offset")
            source.seek(start)
            digest = hashlib.sha256(source.read(min(segment_bytes, size - start))).hexdigest()
            if digest != state["completed"][key]:
                del state["completed"][key]
    write_json(journal, state)
    mutex, stop = threading.Lock(), threading.Event()
    cooldown = 0.0

    def fetch(start: int) -> None:
        nonlocal cooldown
        end = min(start + segment_bytes, size) - 1
        for attempt in range(settings["attempts"]):
            if stop.is_set():
                return
            with mutex:
                delay = max(0.0, cooldown - time.monotonic())
            if stop.wait(delay):
                return
            if shutil.disk_usage(path.parent).free < min_free:
                raise ValueError("Free-space guard during range download")
            request = urllib.request.Request(
                expected["url"],
                headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=settings["timeout_seconds"]
                ) as response:
                    if (
                        response.status != 206
                        or response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}"
                        or response.headers.get("Content-Encoding", "identity") != "identity"
                    ):
                        raise ValueError("Server did not honor exact identity range")
                    body = bytearray()
                    while len(body) <= end - start:
                        chunk = response.read(min(64 * 1024, end - start + 1 - len(body)))
                        if not chunk:
                            raise OSError("Incomplete range response")
                        body.extend(chunk)
                        transferred(len(chunk))
                    if response.read(1):
                        transferred(1)
                        raise ValueError("Oversized range response")
                with path.open("r+b") as target:
                    target.seek(start)
                    target.write(body)
                    target.flush()
                    os.fsync(target.fileno())
                with mutex:
                    state["completed"][str(start)] = hashlib.sha256(body).hexdigest()
                    write_json(journal, state)
                return
            except (urllib.error.URLError, OSError) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 503):
                    raise
                if attempt + 1 == settings["attempts"]:
                    raise
                header = (
                    error.headers.get("Retry-After")
                    if isinstance(error, urllib.error.HTTPError)
                    else None
                )
                wait = retry_delay(
                    header,
                    min(settings["backoff_max_seconds"], settings["backoff_seconds"] * 2**attempt),
                )
                with mutex:
                    cooldown = max(cooldown, time.monotonic() + wait)
        raise RuntimeError("Range retry limit exhausted")

    pending = [start for start in starts if str(start) not in state["completed"]]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, start) for start in pending]
        try:
            for future in futures:
                future.result()
        except BaseException:
            stop.set()
            for future in futures:
                future.cancel()
            raise
    return verify(path, expected)


def prepare(
    config: dict[str, Any], cache: Path, transferred: Callable[[int], None]
) -> dict[str, Any]:
    """Reserve room for all input bytes plus the approved free-space margin."""
    cache = cache.resolve()
    if cache.is_relative_to(ROOT) or any((p / ".git").exists() for p in (cache, *cache.parents)):
        raise ValueError("Source cache must be outside repository/worktrees")
    cache.mkdir(parents=True, exist_ok=True)
    remaining = sum(
        max(0, item["size"] - ((cache / name).stat().st_size if (cache / name).exists() else 0))
        for name, item in config["files"].items()
    )
    free = shutil.disk_usage(cache).free
    required = remaining + config["min_free_disk_bytes"]
    if free < required:
        raise ValueError(f"Insufficient disk: need {required} bytes free, available {free}")
    evidence: dict[str, Any] = {"free_before_bytes": free, "required_free_bytes": required}
    for name in ("PDMX.csv", "mxl.tar.gz"):
        evidence[name] = download(
            config["files"][name],
            cache / name,
            config["download"],
            config["min_free_disk_bytes"],
            transferred,
        )
    return evidence
