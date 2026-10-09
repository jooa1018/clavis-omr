"""Bounded measurement-only patch cache from W2 smoke and shared W5 strips."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from clavis.contracts.common import Producer
from clavis.geometry import StaffCandidate
from clavis.symbols.detection import Settings, Template
from clavis.symbols.staff import read_staff
from training.jobs.model import atomic_json
from training.models.staff.smoke import ground_truth
from training.models.symbols.jitter import jitter_staff, sample_row


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(smoke: Path, bank: Path, output: Path, config_path: Path, jitter: Path) -> dict:
    import resvg_py

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["purpose"] != "measurement-only":
        raise ValueError("This cache cannot be used for admitted training")
    document = json.loads((smoke / "report.json").read_text(encoding="utf-8"))
    template_manifest = json.loads((bank / "manifest.json").read_text(encoding="utf-8"))
    if digest(bank / "templates.npz") != template_manifest["template_sha256"]:
        raise ValueError("Template digest mismatch")
    with np.load(bank / "templates.npz", allow_pickle=False) as arrays:
        templates = [
            Template(name, arrays[f"t{i}"]) for i, name in enumerate(template_manifest["classes"])
        ]
    settings = Settings.load(Path("configs/symbols/constants.yaml"))
    producer = Producer(
        name="symbols-measurement-smoke", version="0.1.1", sha256=digest(config_path)
    )
    rng = np.random.default_rng(config["seed"])
    strips, provenance, observations = [], [], []
    for job in document["jobs"][: config["source_jobs"]]:
        if job["source"] != "clavis-smoke" or not job["seed"].startswith("train-smoke-"):
            raise ValueError("Only non-eval W2 development smoke is allowed")
        folder = (smoke / f"{job['seed']}-{job['font']}").resolve()
        if not folder.is_relative_to(smoke.resolve()):
            raise ValueError("Source escapes smoke root")
        for name in ("page-1.svg.gz", "page-1.labels.json"):
            if digest(folder / name) != job["artifacts"][name]:
                raise ValueError("W2 artifact digest mismatch")
        png = resvg_py.svg_to_bytes(
            svg_string=gzip.decompress((folder / "page-1.svg.gz").read_bytes()).decode(),
            width=config["raster_width"],
            background="white",
            skip_system_fonts=True,
        )
        page = np.asarray(Image.open(io.BytesIO(png)).convert("L"))
        lines = ground_truth(folder, page.shape[1], page.shape[0])
        space = float(np.median([np.median(np.diff(line[:, :, 1], axis=0)) for line in lines]))
        scale = config["jitter_target_interline"] / space
        page = cv2.resize(page, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        lines = ground_truth(folder, page.shape[1], page.shape[0])
        for index, line in enumerate(lines):
            spacing = float(np.median(np.diff(line[:, :, 1], axis=0)))
            staff = StaffCandidate(line, spacing, spacing / 16, 10000).as_staff(
                f"pg0-sy{index}-st0", f"pg0-sy{index}"
            )
            row = sample_row(jitter, config["jitter_target_interline"], rng)
            for geometry in (staff, jitter_staff(staff, row)):
                result = read_staff(
                    page, geometry, templates=templates, settings=settings, producer=producer
                )
                strips.append(result.channels)
                observations.append(
                    {
                        "symbols": len(result.graph.symbols),
                        "relations": len(result.graph.relations),
                        "lattice_hypotheses": len(result.reading.lattice.hypotheses),
                        "lattice_items": sum(
                            len(h.items) for h in result.reading.lattice.hypotheses
                        ),
                        "unresolved": len(result.reading.unresolved_symbol_ids),
                        "channel_changed_pixels": int(
                            np.count_nonzero(result.channels[:, :, 0] != result.channels[:, :, 1])
                        ),
                    }
                )
        provenance.append({"seed": job["seed"], "font": job["font"], "artifacts": job["artifacts"]})
    size = config["patch_size"]
    patches = []
    for index in range(config["patch_records"]):
        strip = strips[index % len(strips)]
        if index % 2:
            ys, xs = np.where(strip[:, :, 1] < 128)
            chosen = int(rng.integers(len(xs)))
            x, y = int(xs[chosen]) - size // 2, int(ys[chosen]) - size // 2
        else:
            x, y = (
                int(rng.integers(strip.shape[1] - size + 1)),
                int(rng.integers(len(strip) - size + 1)),
            )
        x = int(np.clip(x, 0, strip.shape[1] - size))
        y = int(np.clip(y, 0, len(strip) - size))
        patches.append(strip[y : y + size, x : x + size].transpose(2, 0, 1))
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / "patches.npz", patches=np.stack(patches))
    manifest = {
        "purpose": "measurement-only",
        "scope": "W2 train-smoke / W5 synthetic-v0; NOT SYN-Val",
        "patch_records": len(patches),
        "patch_shape": [2, size, size],
        "patches_sha256": digest(output / "patches.npz"),
        "config_sha256": digest(config_path),
        "jitter_sha256": digest(jitter),
        "w2_report_sha256": digest(smoke / "report.json"),
        "sources": provenance,
        "strip_observations": observations,
        "limitations": [
            "sampling with replacement from two development pages, not independent songs",
            "surrogate labels only; unresolved music attributes remain unknown",
            "not admitted training; no checkpoint selection or engine use",
        ],
    }
    atomic_json(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("smoke", type=Path)
    parser.add_argument("templates", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/symbols/measurement.json"))
    parser.add_argument("--descriptor", type=Path)
    args = parser.parse_args()
    descriptor_digest = None
    if args.descriptor:
        from training.jobs.context import Context

        context = Context()
        request = json.loads((context.directory / "request.json").read_text(encoding="utf-8"))
        descriptor_digest = digest(args.descriptor)
        if descriptor_digest != request["data_digest"]:
            raise ValueError("Source descriptor differs from queued input")
        descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
        for entry in descriptor["files"]:
            if digest(Path(entry["path"])) != entry["sha256"]:
                raise ValueError("Frozen source/configuration digest mismatch")
    manifest = prepare(
        args.smoke, args.templates, args.output, args.config, Path("configs/geometry/jitter.yaml")
    )
    if descriptor_digest:
        manifest["source_descriptor_sha256"] = descriptor_digest
        atomic_json(args.output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
