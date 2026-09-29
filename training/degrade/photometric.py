"""Label-preserving CPU effects, generated from scalar parameters only."""

import json
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

Array = NDArray[Any]
Params = dict[str, Any]
OPERATIONS = frozenset(
    {"illumination", "blur", "noise", "threshold", "photocopy", "paper", "screen"}
)


def bounded(params: Params, key: str, low: float, high: float) -> float:
    """Validate an explicit physical/resource range without silently clipping inputs."""
    value = float(params[key])
    if not np.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{key} must be in [{low}, {high}]")
    return value


def random_state(rng: np.random.Generator, params: Params) -> Params:
    """Record/restore caller-owned generator state; never instantiate a second RNG."""
    if "rng_state" in params:
        if params["rng_state"]["bit_generator"] != rng.bit_generator.__class__.__name__:
            raise ValueError("Replay requires the recorded NumPy bit-generator type")
        rng.bit_generator.state = params["rng_state"]
    state = json.loads(json.dumps(rng.bit_generator.state, default=lambda value: value.tolist()))
    return {**params, "rng_state": state}


def apply_effect(
    image: Array, rng: np.random.Generator, params: Params, space: float
) -> tuple[Array, Params]:
    """Apply one bounded photometric effect; uint8 shape/channel order is preserved."""
    name = params["op"]
    h, w = image.shape[:2]
    unit: Array = image.astype(np.float32) / 255
    if name == "illumination":
        x = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
        y = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
        gain = 1 + bounded(params, "x_slope", -1, 1) * x + bounded(params, "y_slope", -1, 1) * y
        gain = gain - bounded(params, "vignette", 0, 1) * (x * x + y * y) / 2
        shadow = bounded(params, "shadow_strength", 0, 1)
        radius = bounded(params, "shadow_radius", float(np.finfo(np.float32).eps), 2)
        cx, cy = (bounded(params, key, -1, 1) for key in ("shadow_x", "shadow_y"))
        gain -= shadow * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * radius**2))
        unit *= gain if image.ndim == 2 else gain[..., None]
    elif name == "blur":
        sigma = bounded(params, "sigma_spaces", 0, params["max_filter_spaces"]) * space
        if sigma:
            unit = cv2.GaussianBlur(unit, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
    elif name == "noise":
        sigma = bounded(params, "sigma", 0, 1)
        params = random_state(rng, params)
        unit += sigma * rng.standard_normal(image.shape, dtype=np.float32)
    elif name == "threshold":
        threshold = bounded(params, "level", 0, 1)
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) / 255 if image.ndim == 3 else unit
        unit = (gray > threshold).astype(np.float32)
        if image.ndim == 3:
            unit = np.repeat(unit[..., None], 3, axis=2)
    elif name == "photocopy":
        radius = bounded(params, "radius_spaces", 0, params["max_filter_spaces"]) * space
        half = round(radius)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * half + 1, 2 * half + 1))
        if params["mode"] not in ("thicken", "thin"):
            raise ValueError("Photocopy mode must be thicken or thin")
        unit = (cv2.erode if params["mode"] == "thicken" else cv2.dilate)(unit, kernel)
    elif name == "paper":
        strength = bounded(params, "strength", 0, 1)
        grain = bounded(params, "grain_spaces", 1, params["max_grain_spaces"]) * space
        params = random_state(rng, params)
        small = rng.random(
            (max(2, int(np.ceil(h / grain))), max(2, int(np.ceil(w / grain)))), dtype=np.float32
        )
        field = 1 - strength * cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
        unit *= field if image.ndim == 2 else field[..., None]
    elif name == "screen":
        period = (
            bounded(
                params, "period_spaces", params["min_period_spaces"], params["max_period_spaces"]
            )
            * space
        )
        strength = bounded(params, "strength", 0, 1)
        phase = bounded(params, "phase_radians", -np.pi, np.pi)
        angle = np.deg2rad(bounded(params, "angle_degrees", -180, 180))
        x = np.arange(w, dtype=np.float32)[None, :]
        y = np.arange(h, dtype=np.float32)[:, None]
        wave = (
            1 + np.cos((x * np.cos(angle) + y * np.sin(angle)) * 2 * np.pi / period + phase)
        ) / 2
        field = 1 - strength * wave
        unit *= field if image.ndim == 2 else field[..., None]
    else:
        raise ValueError(f"Unknown photometric operation: {name}")
    return np.rint(np.clip(unit, 0, 1) * 255).astype(np.uint8), params
