"""W1 queue payload: quarantined 10-score / three-font renderer audit."""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from training.data.licenses import require_use
from training.data.smoke_inputs import score
from training.data.staff_svg import extract, label_document

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/data/smoke.json"


def digest(data: bytes) -> str:
    """Identify artifacts for resume/provenance, never for recognition decisions."""
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    """Atomic checkpoint replacement makes interrupted jobs safely resumable."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(output: Path, renderer_python: Path | None = None) -> dict[str, Any]:
    """Prepare offline fixtures; render only when dispatched by W1's night queue.

    Outputs stay in work/. No training manifest or shard is emitted before W4
    admission integration. A render success is not a completed visual audit.
    """
    output = output.resolve()
    if not output.is_relative_to(ROOT / "work"):
        raise ValueError("Smoke artifacts must remain quarantined under work/")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    require_use("clavis-smoke", "tool-test")
    require_use("verovio", "external-render-tool")
    for font in config["fonts"]:
        require_use(font.lower(), "render-font")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    for index in range(config["song_count"]):
        seed = f"train-smoke-{index}"
        xml = score(seed, fifths=index - 5, beats=3 + index % 2, staves=1 + index % 2).encode()
        for font in config["fonts"]:
            job = output / f"{seed}-{font}"
            job.mkdir(exist_ok=True)
            (job / "input.musicxml").write_bytes(xml)
            record: dict[str, Any] = {
                "seed": seed,
                "font": font,
                "status": "NOT_RUN",
                "source": "clavis-smoke",
                "input_sha256": digest(xml),
            }
            results.append(record)
            if renderer_python is None:
                continue
            sources = b"".join(p.read_bytes() for p in sorted(Path(__file__).parent.glob("*.py")))
            key = digest(
                xml + CONFIG.read_bytes() + sources + str(renderer_python.resolve()).encode()
            )
            checkpoint = job / "complete.json"
            if checkpoint.exists():
                try:
                    previous = json.loads(checkpoint.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    previous = {}
                if (
                    previous.get("key") == key
                    and all(
                        (job / name).exists() and digest((job / name).read_bytes()) == sha
                        for name, sha in previous.get("artifacts", {}).items()
                    )
                    and previous.get("artifacts")
                ):
                    record.update(previous)
                    continue
            phase = "storage"
            try:
                used = sum(
                    p.stat().st_size
                    for base in (ROOT / "data", ROOT / "work")
                    for p in base.rglob("*")
                    if p.is_file()
                )
                if used + config["job_reserve_bytes"] > config["data_budget_bytes"]:
                    raise ValueError("Data storage budget exceeded")
                if (
                    shutil.disk_usage(output).free
                    < config["min_free_bytes"] + config["job_reserve_bytes"]
                ):
                    raise ValueError("Insufficient free disk")
                env = {
                    **os.environ,
                    "OMP_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                    "PYTHONIOENCODING": "utf-8",
                }
                phase = "renderer"
                result = subprocess.run(
                    [
                        str(renderer_python),
                        "-m",
                        "training.data.verovio_worker",
                        str(CONFIG),
                        font,
                    ],
                    input=xml,
                    capture_output=True,
                    timeout=config["timeout_seconds"],
                    check=True,
                    env=env,
                    cwd=ROOT,
                )
                rendered = json.loads(result.stdout)
                phase = "svg-extraction"
                artifacts: dict[str, str] = {}
                for page, svg in enumerate(rendered["pages"], 1):
                    labels, overlay = extract(
                        svg,
                        max_bytes=config["max_svg_bytes"],
                        enabled=config["staff_path_extraction_enabled"],
                    )
                    content = {
                        f"page-{page}.svg.gz": gzip.compress(svg.encode(), mtime=0),
                        f"page-{page}.overlay.svg.gz": gzip.compress(overlay.encode(), mtime=0),
                        f"page-{page}.labels.json": json.dumps(label_document(labels)).encode(),
                    }
                    for name, data in content.items():
                        (job / name).write_bytes(data)
                        artifacts[name] = digest(data)
                record.update(
                    status="RENDERED_PENDING_VISUAL_AUDIT",
                    key=key,
                    artifacts=artifacts,
                    version=rendered["version"],
                    options=rendered["options"],
                    pages=len(rendered["pages"]),
                    peak_rss_bytes=rendered.get("peak_rss_bytes"),
                )
                write_json(checkpoint, record)
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                record.update(status="FAIL", phase=phase, reason=type(error).__name__)
            write_json(output / "results.json", results)
    report = {
        "status": "NOT_RUN" if renderer_python is None else "PARTIAL",
        "jobs": results,
        "training_admission": "BLOCKED_PENDING_W4_FINGERPRINT_FILTER",
        "visual_audit": "NOT_RUN",
        "wall_seconds": time.monotonic() - started,
        "scope": "synthetic self-authored fixtures; no Dev/sealed/real images",
    }
    write_json(output / "report.json", report)
    return report


def main() -> None:
    """CLI payload; --renderer-python must only be used by the W1 single queue."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--renderer-python", type=Path)
    args = parser.parse_args()
    report = run(args.output, args.renderer_python)
    print(json.dumps({"status": report["status"], "jobs": len(report["jobs"])}))
    if any(job["status"] == "FAIL" for job in report["jobs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
