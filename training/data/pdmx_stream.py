"""Aggregate verified local sources; OR-004 range cache survives network interruption."""

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import tarfile
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from training.data.licenses import require_use
from training.data.pdmx_aggregate import eligible, notation_counts, unpack_mxl
from training.data.resources import peak_rss_bytes
from training.data.smoke import ROOT, write_json


class HashStream(io.RawIOBase):
    """Bound incoming bytes and authenticate the complete source stream."""

    def __init__(
        self,
        source: Any,
        maximum: int,
        telemetry: dict[str, Any] | None = None,
        progress_hook: Callable[[], None] | None = None,
    ) -> None:
        self.source, self.maximum, self.total = source, maximum, 0
        self.telemetry = telemetry
        self.progress_hook = progress_hook
        self.progress = 0
        self.md5, self.sha256 = hashlib.md5(usedforsecurity=False), hashlib.sha256()

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        data = self.source.read(len(buffer))
        self.total += len(data)
        if self.telemetry is not None:
            self.telemetry["transfer_bytes"] += len(data)
        progress = self.total // (16 * 1024 * 1024)
        if progress > self.progress:
            self.progress = progress
            if self.progress_hook is not None:
                self.progress_hook()
            print(json.dumps({"stream_bytes": self.total}), flush=True)
        if self.total > self.maximum:
            raise ValueError("Source stream exceeds configured limit")
        self.md5.update(data)
        self.sha256.update(data)
        buffer[: len(data)] = data
        return len(data)

    def verify(self, expected: dict[str, Any]) -> None:
        if self.total != expected["size"] or "md5:" + self.md5.hexdigest() != expected["checksum"]:
            raise ValueError("Source size/checksum mismatch")


def run(
    config: dict[str, Any],
    output: Path,
    cache: Path,
    telemetry: dict[str, Any] | None = None,
    progress_hook: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Reread local immutable archives to resume without persisting song IDs."""
    from training.data.pdmx_download import verify

    for name, expected in config["files"].items():
        verify(cache / name, expected)
    require_use("pdmx", "aggregate-statistics")
    output = output.resolve()
    if not output.is_relative_to(ROOT / "work"):
        raise ValueError("Aggregate output must remain under work")
    used = sum(
        p.stat().st_size
        for folder in (ROOT / "work", ROOT / "data")
        if folder.exists()
        for p in folder.rglob("*")
        if p.is_file()
    )
    if (
        used >= config["data_budget_bytes"]
        or shutil.disk_usage(ROOT).free < config["min_free_disk_bytes"]
    ):
        raise ValueError("Storage budget/free-space guard")
    output.mkdir(parents=True, exist_ok=True)
    config_digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

    def progress() -> None:
        if shutil.disk_usage(ROOT).free < config["min_free_disk_bytes"]:
            raise ValueError("Free-space guard during streaming")
        if progress_hook is not None:
            progress_hook()

    manifest = config["files"]["PDMX.csv"]
    paths: set[str] = set()
    licensing: Counter[str] = Counter()
    with (cache / "PDMX.csv").open("rb") as response:
        raw = HashStream(response, config["max_csv_bytes"], None, progress)
        with io.TextIOWrapper(io.BufferedReader(raw), encoding="utf-8-sig", newline="") as text:
            rows = csv.DictReader(text)
            required = {"mxl", "license_url", "license_conflict", "subset:no_license_conflict"}
            if not required.issubset(rows.fieldnames or []):
                raise ValueError("Missing required manifest columns")
            for row in rows:
                licensing["rows"] += 1
                if eligible(row):
                    name = row["mxl"].removeprefix("./")
                    if name in paths:
                        raise ValueError("Duplicate eligible MXL path")
                    paths.add(name)
                    licensing["eligible"] += 1
                else:
                    licensing["excluded"] += 1
        raw.verify(manifest)
        manifest_digest = raw.sha256.hexdigest()
    checkpoint = output / "checkpoint.json"
    counts: dict[str, dict[str, int]] = {}
    statistics: Counter[str] = Counter()
    completed = 0
    if checkpoint.exists():
        previous = json.loads(checkpoint.read_text(encoding="utf-8"))
        if (
            previous["config_digest"] != config_digest
            or previous["manifest_digest"] != manifest_digest
        ):
            raise ValueError("Checkpoint provenance mismatch")
        counts, statistics = previous["counts"], Counter(previous["statistics"])
        completed = previous["members_processed"]
    state: dict[str, Any] = {
        "status": "INCOMPLETE_NOT_A_TARGET",
        "config_digest": config_digest,
        "manifest_digest": manifest_digest,
        "counts": counts,
        "statistics": statistics,
        "licensing": licensing,
        "members_processed": completed,
        "training_admission": "BLOCKED",
    }
    archive = config["files"]["mxl.tar.gz"]
    seen: set[str] = set()
    with (cache / "mxl.tar.gz").open("rb") as response:
        raw = HashStream(response, config["max_archive_bytes"], None, progress)
        stream = io.BufferedReader(raw)
        with tarfile.open(fileobj=stream, mode="r|gz") as bundle:
            for ordinal, member in enumerate(bundle, start=1):
                cast(Any, bundle).members.clear()
                if (
                    ordinal > config["max_tar_members"]
                    or member.size > config["max_tar_member_bytes"]
                ):
                    raise ValueError("TAR member limit exceeded")
                name = member.name.removeprefix("./")
                selected = name in paths
                if selected:
                    if name in seen:
                        raise ValueError("Duplicate selected archive member")
                    seen.add(name)
                if ordinal <= completed:
                    continue
                if selected:
                    if not member.isfile() or member.size > config["max_mxl_bytes"]:
                        raise ValueError("Selected MXL must be a bounded regular file")
                    source = bundle.extractfile(member)
                    if source is None:
                        raise ValueError("Missing member body")
                    try:
                        xml = unpack_mxl(
                            source.read(),
                            max_xml_bytes=config["max_xml_bytes"],
                            max_ratio=config["max_ratio"],
                        )
                        per_song = notation_counts(xml, set(config["meters"]))
                    except ET.ParseError:
                        # T2.2 excludes unreadable notation; never repair or infer its contents.
                        # Resource, integrity and unsupported-format errors remain fatal.
                        statistics["rejected_invalid_xml"] += 1
                    else:
                        statistics["parsed_songs"] += 1
                        for meter, values in per_song.items():
                            merged = Counter(counts.get(meter, {}))
                            merged.update(values)
                            merged["songs"] += 1
                            counts[meter] = dict(merged)
                state["members_processed"] = ordinal
                if ordinal % config["checkpoint_every"] == 0:
                    write_json(checkpoint, state)
                    progress()
                    print(
                        json.dumps(
                            {
                                "members_processed": ordinal,
                                "parsed_songs": statistics["parsed_songs"],
                            }
                        ),
                        flush=True,
                    )
        while stream.read(io.DEFAULT_BUFFER_SIZE):
            pass
        raw.verify(archive)
    if paths != seen:
        raise ValueError("Eligible MXL members missing from archive")
    state["status"] = "COMPLETE_AGGREGATE_ONLY"
    state["archive_digest"] = raw.sha256.hexdigest()
    write_json(checkpoint, state)
    write_json(
        output / "aggregate.json",
        {
            "manifest_digest": manifest_digest,
            "counts": counts,
            "licensing": dict(licensing),
            "statistics": dict(statistics),
        },
    )
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    from training.data.pdmx_download import cache_lock, prepare
    from training.data.pdmx_windows import constrain

    job = constrain(config["process_memory_bytes"], config["max_compute_threads"])
    started, cpu_started = time.perf_counter(), time.process_time()
    metrics_path = args.output / "run-metrics.json"
    prior = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    telemetry: dict[str, Any] = {
        "transfer_bytes": prior.get("transfer_bytes", 0),
        "status": "RUNNING",
    }
    metric_lock = threading.Lock()
    last_report = time.monotonic()

    def report_metrics() -> None:
        wall = prior.get("wall_seconds", 0) + time.perf_counter() - started
        cpu = prior.get("cpu_seconds", 0) + time.process_time() - cpu_started
        telemetry.update(
            wall_seconds=wall,
            cpu_seconds=cpu,
            peak_rss_bytes=max(prior.get("peak_rss_bytes", 0), peak_rss_bytes()),
            average_cpu_one_core_percent=100 * cpu / wall,
            average_cpu_machine_percent=100 * cpu / wall / (os.cpu_count() or 1),
            job_handle_active=bool(job),
        )
        args.output.mkdir(parents=True, exist_ok=True)
        write_json(metrics_path, telemetry)

    def transferred(size: int) -> None:
        nonlocal last_report
        with metric_lock:
            telemetry["transfer_bytes"] += size
            if time.monotonic() - last_report >= config["download"]["metrics_seconds"]:
                report_metrics()
                last_report = time.monotonic()

    try:
        with cache_lock(args.cache):
            telemetry["phase"] = "DOWNLOAD"
            report_metrics()
            evidence = prepare(config, args.cache, transferred)
            write_json(args.output / "source-verification.json", evidence)
            telemetry["phase"] = "AGGREGATE"
            report_metrics()
            run(config, args.output, args.cache, telemetry, report_metrics)
            # Explicitly authorized cleanup: only this job's two source files and journals.
            for name in ("PDMX.csv", "mxl.tar.gz"):
                path = args.cache / name
                path.unlink()
                path.with_suffix(path.suffix + ".ranges.json").unlink()
            telemetry["source_cache_removed"] = True
        telemetry["status"] = "COMPLETE"
    except Exception:
        telemetry["status"] = "INTERRUPTED"
        raise
    finally:
        report_metrics()


if __name__ == "__main__":
    main()
