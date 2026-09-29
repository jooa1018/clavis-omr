# Synthetic degradation (W3)

First-PR scope (merged #6): rotation, projective homography, interline downsampling,
and repeated JPEG. Pure `apply(image, labels, rng, params)` returns image, labels and
resolved parameters; `run` samples YAML scalar `uniform` / `choice` distributions using
one explicit NumPy generator. Replay the recorded `operations` through `apply`.
No Dev, sealed, real-image texture, external service or engine code is used.

## Local CPU verification

From the repository root, Python 3.12:

```powershell
uv sync --locked --all-groups
.venv/Scripts/python.exe -m pytest tests/degrade --cov=training.degrade --cov-fail-under=80
.venv/Scripts/mypy.exe --strict training/degrade
.venv/Scripts/ruff.exe check training/degrade tests/degrade
.venv/Scripts/python.exe -m training.degrade.demo --output work/degrade-demo
```

On Linux use `.venv/bin/` instead of `.venv/Scripts/`. W1 PR #7 manages numerical/image
and YAML dependencies in the root `training` group and `uv.lock`; no secondary dependency
list exists. CI installs all groups and executes all tests, including W3. Missing W3
dependencies now fail collection instead of silently skipping the module. The engine's
dependency closure is unchanged. W3 strict typing and coverage are also checked locally.

## Geometry and labels

- uint8 grayscale `(H,W)` or **RGB** `(H,W,3)`. Maximum input pixels is configuration-owned.
- `Labels` is a W3-local training container, **not a versioned Clavis/W2 contract**.
  Points `(N,2)`, xyxy boxes `(N,4)`, arbitrary polylines, uint8/uint16 categorical masks,
  and sampled adjacent staff-line point pairs `(N,2,2)` are explicit inputs.
- Coordinates are integer pixel centers, origin at the top left. Homographies are forward
  input-to-output float64 matrices. Homographic composition is `H_last @ ... @ H_first`.
  Rotation/perspective keep the input canvas; white fills uncovered image pixels.
- Boxes transform all four corners and retain their unclipped axis-aligned envelope.
  Points and polylines are transformed without rounding; mask IDs use nearest sampling
  and background ID zero. Any out-of-frame geometry or mask extent sets sample-level
  `truncated`. This is conservative for sparse masks. Consumers must exclude these
  samples from whole-staff losses; there is no silent clipping or invented content.
- Interline is the perpendicular distance from each second anchor to the line through
  the first anchor and its local tangent. Initially omitted tangents are perpendicular
  to the pair. Transforming tangents retains local perspective variation; one global
  scalar is insufficient. The resize target refers to the **median** sampled spacing.
  Actual per-anchor spacings are recorded after integer dimension rounding.
- Resize uses `(x+0.5)*sx-0.5`, `(y+0.5)*sy-0.5`, matching OpenCV pixel centers.
  Area/bilinear/bicubic/exact-nearest image resampling is configurable. Masks always
  use exact-nearest on resize. JPEG preserves geometry and masks, supporting quality,
  chroma subsampling and 1–3 passes. Encoded JPEG bytes are decoded into the output array.
- Singular homographies and horizons crossing the input canvas are rejected. The
  caller can supply a homography or pinhole tilt angles with a positive focal ratio.

## Evidence and limits

Tests compare grayscale grid centroids to labels within 0.5 output pixels, box corners,
polylines, inverse maps, and categorical masks against an independent inverse-nearest
oracle (excluding sub-0.001-pixel ties). Binary-mask centroids alone are unsuitable:
integer raster quantization can exceed 0.5 px in Euclidean distance. Property tests
span rotation/perspective combinations. Replay and seed determinism run three times
at each of 1 and 4 OpenCV threads for grayscale and color.

The demo draws one original 2.048 MP **schematic**, without external fonts or pixels.
It emits source + five 16/12/10/8/7 px images, NPZ labels, an overview and JSON with
hashes, provenance, dependency versions, wall time and sampled parameters. This is
not a W2 MusicXML-backed renderer or a generalization/recognition benchmark. The
overview rescales thumbnails; native outputs are the pixel-resolution evidence.
The demo YAML remains a mechanical fixture; the separate preset catalog is adopted for G1 v0.
Rendering dimensions and note positions are fixture content, not input-dependent rules.

No real aggregate statistics have been supplied by W4. Realism, sustained
throughput, full G0/G1 gates and W2 integration are not claimed. Existing CPU smoke performance
is PASS under the Orchestrator's revised mean ≥5 pages/core-second and heaviest ≥3 targets.
Cross-version codec byte identity is not promised. Large jobs belong in W1's
01:00–07:00 single queue.

## G1 training v0 presets (ADR-011 provisionally adopted, 2026-09-29)

`configs/degrade/presets.yaml` adds **nine families** and all twelve route names:

| Family | Implemented operations |
|---|---|
| Geometry | Rotation, pinhole planar tilt/homography, vertical paper wave |
| Illumination | Linear gradient, vignette, smooth shadow |
| Optics | Gaussian blur in staff-space units |
| Resolution | Target median interline, four interpolation modes |
| Compression | JPEG quality, subsampling and repeated encoding |
| Sensor | Independent Gaussian channel noise |
| Scan | Global threshold, thinning/thickening morphology |
| Paper | Procedural low-frequency tone variation |
| Screen | Periodic interference with orientation/phase |

```python
from pathlib import Path
import numpy as np
import yaml
from training.degrade.presets import run_preset, replay

catalog = yaml.safe_load(Path("configs/degrade/presets.yaml").read_text())
output, moved, trace = run_preset(image, labels, np.random.default_rng(42), catalog, "phone-shadow")
reproduced, moved_again = replay(image, labels, np.random.default_rng(0), trace)
```

These are **unfitted experimental priors**, not a claim of matching particular cameras,
scan DPI or Kakao algorithms. Each YAML preset carries its rationale. The 40/35/20/5%
mixture follows the instruction; within-band sampling is uniform, and the last band's
upper endpoint is min(render interline, 40 px), additionally limited by the spacing before
resize to forbid enlargement after geometry. Select the band first; reject only if its
lower bound exceeds that available spacing. Never silently redraw or reweight.
Pass one caller-owned `SamplingStats(catalog["rejection_rate_limit"])` across the batch,
catch `SampleRejected` and retain its `.record`. Save `stats.summary()` including attempts,
rejections and per-band counts; report to W2 when `w2_report_required` is true (≥1%).
W2 renders start at ≥28 px. Rejected attempts remain in the denominator.

G1 training connection is authorized now. G2 adoption still requires all-operation label
error ≤0.5 px, W4 R-Dev-Tune KS/quantiles for interline, blur, JPEG quality and noise,
and domain-classifier AUC. Phone-curl stays experimental-unfitted until aggregate calibration.

Noise and paper texture use the caller's **one** NumPy Generator. JSON-safe bit-generator
state is recorded before consumption. Replay restores it into the supplied compatible
generator (PCG64 and MT19937 tested); caller RNG state advances normally. No random
pixels are copied from real data. Photometric operators preserve all label geometry.

Paper wave is `y'=y+A*sin(omega*x+phase)`, a smooth-curl approximation. It uses an inverse
raster map, exact box edge extrema, bounded-error polyline subdivision and Jacobian
tangents. A nonlinear trace returns **`matrix: null`**: replay the operation list, never
treat that output as a homography. This is a W3-private trace, not an engine contract.
No global mutable map cache is used; a bounded caller-owned mesh cache is future work.

The catalog's 6 px threshold sets `illegible_candidate` from the minimum actual sampled
interline; callers must separate flagged samples from normal training/evaluation losses.
Missing threshold configuration returns `None` rather than claiming legibility. The
flag is only a low-resolution candidate, not a human readability classifier.

```powershell
uv run --locked --all-groups python -m training.degrade.smoke --output work/preset-smoke
```

This bounded OR-001 smoke uses 72 synthetic pages, one CPU thread, 2.048/4 MP inputs and
two measured samples per route/size after one warmup. It outputs native route images,
traces, a contact sheet, peak process RSS and timings. Its fixture is a schematic, not
a full W2 score. Thin synthetic staff lines may disappear after reduction; these cases
remain visible in the results. A small smoke is not a sustained throughput or realism gate.
