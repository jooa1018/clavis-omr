"""Original-channel ablation at 8 px using W2 smoke; NOT SYN-Val or accuracy."""

import argparse
import gzip
import io
import json
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from clavis.contracts.common import Producer
from clavis.geometry import StaffCandidate, load_config
from clavis.symbols.detection import Settings, Template, detect
from clavis.symbols.reading import draft_reading
from clavis.symbols.staff import read_staff
from training.data.resources import peak_rss_bytes
from training.jobs.model import atomic_json
from training.models.staff.smoke import ground_truth
from training.models.symbols.jitter import jitter_staff, sample_row
from training.models.symbols.measurement_data import digest


def run(smoke: Path, bank: Path, output: Path) -> dict:
    import resvg_py

    started = time.perf_counter()
    document = json.loads((smoke / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads((bank / "manifest.json").read_text(encoding="utf-8"))
    if digest(bank / "templates.npz") != manifest["template_sha256"]:
        raise ValueError("Template digest mismatch")
    with np.load(bank / "templates.npz", allow_pickle=False) as arrays:
        templates = [Template(name, arrays[f"t{i}"]) for i, name in enumerate(manifest["classes"])]
    config = load_config(Path("configs/geometry"))
    settings = Settings.load(Path("configs/symbols/constants.yaml"))
    producer = Producer(
        name="symbols-8px-channel-smoke", version="0.1.1", sha256=digest(Path(__file__))
    )
    jitter = Path("configs/geometry/jitter.yaml")
    rng = np.random.default_rng(6)
    observations, sources = [], []
    for job in document["jobs"][:2]:
        if job["source"] != "clavis-smoke" or not job["seed"].startswith("train-smoke-"):
            raise ValueError("Only W2 development smoke is allowed")
        folder = (smoke / f"{job['seed']}-{job['font']}").resolve()
        if not folder.is_relative_to(smoke.resolve()):
            raise ValueError("Source escapes smoke root")
        for name in ("page-1.svg.gz", "page-1.labels.json"):
            if digest(folder / name) != job["artifacts"][name]:
                raise ValueError("W2 artifact digest mismatch")
        png = resvg_py.svg_to_bytes(
            svg_string=gzip.decompress((folder / "page-1.svg.gz").read_bytes()).decode(),
            width=1200,
            background="white",
            skip_system_fonts=True,
        )
        page = np.asarray(Image.open(io.BytesIO(png)).convert("L"))
        lines = ground_truth(folder, page.shape[1], page.shape[0])
        spacing = float(np.median([np.median(np.diff(line[:, :, 1], axis=0)) for line in lines]))
        page = cv2.resize(page, None, fx=8 / spacing, fy=8 / spacing, interpolation=cv2.INTER_AREA)
        for index, line in enumerate(ground_truth(folder, page.shape[1], page.shape[0])):
            space = float(np.median(np.diff(line[:, :, 1], axis=0)))
            staff = StaffCandidate(line, space, space / 16, 10000).as_staff(
                f"pg0-sy{index}-st0", f"pg0-sy{index}"
            )
            row = sample_row(jitter, 8, rng)
            for kind, geometry in (("clean", staff), ("jitter", jitter_staff(staff, row))):
                result = read_staff(
                    page,
                    geometry,
                    templates=templates,
                    settings=settings,
                    producer=producer,
                    geometry_config=config,
                )
                original = result.channels[:, :, 0]
                original_graph = detect(
                    original,
                    np.full_like(original, 255),
                    staff_id=geometry.staff_id,
                    staff_space=config["strip.s_star"],
                    v_top=config["strip.above"] * config["strip.s_star"],
                    templates=templates,
                    settings=settings,
                    producer=producer,
                )
                for mode, graph, reading in (
                    ("both", result.graph, result.reading),
                    ("original-only", original_graph, draft_reading(original_graph, producer)),
                ):
                    observations.append(
                        {
                            "font": job["font"],
                            "staff": index,
                            "geometry": kind,
                            "mode": mode,
                            "input_interline_px": space,
                            "symbols": len(graph.symbols),
                            "template_candidates": sum(
                                "template" in s.sources for s in graph.symbols
                            ),
                            "vertical_candidates": sum("vline" in s.sources for s in graph.symbols),
                            "relations": len(graph.relations),
                            "unresolved": len(reading.unresolved_symbol_ids),
                            "lattice_items": sum(len(h.items) for h in reading.lattice.hypotheses),
                        }
                    )
        sources.append({"seed": job["seed"], "font": job["font"], "artifacts": job["artifacts"]})
    report = {
        "scope": "synthetic path smoke, NOT SYN-Val, NOT detection accuracy",
        "input_target_interline_px": 8,
        "source_report_sha256": digest(smoke / "report.json"),
        "template_sha256": manifest["template_sha256"],
        "jitter_sha256": digest(jitter),
        "code_sha256": digest(Path(__file__)),
        "sources": sources,
        "observations": observations,
        "summary": {
            mode: {
                key: sum(row[key] for row in observations if row["mode"] == mode)
                for key in (
                    "symbols",
                    "template_candidates",
                    "vertical_candidates",
                    "relations",
                    "unresolved",
                    "lattice_items",
                )
            }
            for mode in ("both", "original-only")
        },
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_rss_bytes(),
        "limitations": [
            "Known synthetic staff geometry; missed staves are not tested or repaired",
            "W5 jitter excludes misses; synthetic-v0 is not a real-image error distribution",
            "Counts are candidates without W2 symbol labels, not recall/precision/oracle@k",
            "Empty lattice remains unresolved; missing attributes are never generated",
            "No training, parameter tuning, checkpoint selection or real/sealed data",
        ],
    }
    atomic_json(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("smoke", type=Path)
    parser.add_argument("templates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.smoke, args.templates, args.output)


if __name__ == "__main__":
    main()
