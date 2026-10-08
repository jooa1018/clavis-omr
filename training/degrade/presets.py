"""Experimental route composition; no real-image calibration is implied."""

import hashlib
import json

import numpy as np

from training.degrade.ops import Array, Labels, Params, apply, run
from training.degrade.sampling import SampleRejected, SamplingStats


def resolution_stage_variant(preset: Params, rng: np.random.Generator) -> tuple[list[Params], str]:
    """Place optical blur then sensor noise together before/after the sole resize."""
    variant = preset.get("resolution_stage_variant")
    if variant is None:
        raise ValueError("Preset has no resolution-stage variant")
    choices = variant["placements"]
    defaults = variant["operators"]
    operations = preset["operations"]
    if (
        not choices
        or any(choice not in ("before_resize", "after_resize") for choice in choices)
        or [step["op"] for step in defaults] != ["blur", "noise"]
        or sum(step["op"] == "resize" for step in operations) != 1
        or any(sum(step["op"] == op for step in operations) > 1 for op in ("blur", "noise"))
    ):
        raise ValueError("Invalid resolution-stage variant")
    placement = str(choices[int(rng.integers(len(choices)))])
    effects = [
        next((step for step in operations if step["op"] == fallback["op"]), fallback)
        for fallback in defaults
    ]
    ordered = [step for step in operations if step["op"] not in ("blur", "noise")]
    position = next(i for i, step in enumerate(ordered) if step["op"] == "resize")
    if placement == "before_resize":
        resize = {**ordered[position], "capture_factor": variant["intermediate_factor"]}
        return (
            ordered[:position]
            + [resize]
            + effects
            + [{"op": "resize", "finish_capture": True}]
            + ordered[position + 1 :],
            placement,
        )
    position += int(placement == "after_resize")
    return ordered[:position] + effects + ordered[position:], placement


def run_preset(
    image: Array,
    labels: Labels,
    rng: np.random.Generator,
    catalog: Params,
    name: str,
    stats: SamplingStats | None = None,
    *,
    vary_resolution_stage: bool | None = None,
) -> tuple[Array, Labels, Params]:
    """Use configured route operations and shared safety/scale settings."""
    preset = catalog["presets"][name]
    if vary_resolution_stage is None:
        variant = preset.get("resolution_stage_variant")
        probability = float(variant["default_use_probability"]) if variant else 0.0
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Invalid default variant probability")
        vary_resolution_stage = bool(rng.random() < probability) if probability else False
    operations, placement = (
        resolution_stage_variant(preset, rng)
        if vary_resolution_stage
        else (preset["operations"], None)
    )
    stats = stats if stats is not None else SamplingStats(catalog["rejection_rate_limit"])
    try:
        output, moved, record = run(
            image, labels, rng, {**catalog, "operations": operations}, stats
        )
    except SampleRejected as error:
        error.record.update(
            preset=name,
            render_interline_px=float(np.median(labels.interlines)),
            sampling_stats=stats.summary(),
        )
        if placement is not None:
            error.record["resolution_stage_placement"] = placement
        raise
    record.update(
        preset=name,
        status=catalog["status"],
        catalog_sha256=hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest(),
        adoption=catalog["adoption"],
    )
    if placement is not None:
        record["resolution_stage_placement"] = placement
    return output, moved, record


def replay(
    image: Array, labels: Labels, rng: np.random.Generator, record: Params
) -> tuple[Array, Labels]:
    """Replay the trace, including nonlinear maps and recorded random generator state."""
    for params in record["operations"]:
        image, labels, _ = apply(image, labels, rng, params)
    return image, labels
