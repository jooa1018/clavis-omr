"""Experimental route composition; no real-image calibration is implied."""

import hashlib
import json

import numpy as np

from training.degrade.ops import Array, Labels, Params, apply, run


def run_preset(
    image: Array, labels: Labels, rng: np.random.Generator, catalog: Params, name: str
) -> tuple[Array, Labels, Params]:
    """Use configured route operations and shared safety/scale settings."""
    preset = catalog["presets"][name]
    output, moved, record = run(image, labels, rng, {**catalog, "operations": preset["operations"]})
    record.update(
        preset=name,
        status=catalog["status"],
        catalog_sha256=hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest(),
    )
    return output, moved, record


def replay(
    image: Array, labels: Labels, rng: np.random.Generator, record: Params
) -> tuple[Array, Labels]:
    """Replay the trace, including nonlinear maps and recorded random generator state."""
    for params in record["operations"]:
        image, labels, _ = apply(image, labels, rng, params)
    return image, labels
