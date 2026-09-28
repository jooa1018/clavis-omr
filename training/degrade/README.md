# Synthetic degradation (W3)

First-PR scope: rotation, supplied projective homography, target-interline downsampling,
and repeated JPEG. Pure `apply(image, labels, rng, params)` returns image, labels and
resolved parameters; `run` samples YAML scalar `uniform` / `choice` distributions using
one explicit NumPy generator. Replay the recorded `operations` through `apply`.
No Dev, sealed, real-image texture, external service or engine code is used.

## Local CPU verification

From the repository root, Python 3.12:

```powershell
uv sync --locked
uv pip install --python .venv/Scripts/python.exe -r training/degrade/requirements.txt
.venv/Scripts/python.exe -m pytest tests/degrade --cov=training.degrade --cov-fail-under=80
.venv/Scripts/mypy.exe --strict training/degrade
.venv/Scripts/ruff.exe check training/degrade tests/degrade
.venv/Scripts/python.exe -m training.degrade.demo --output work/degrade-demo
```

On Linux use `.venv/bin/` instead of `.venv/Scripts/`. Do not run `uv sync` again between
installing the W3 requirements and these commands: W1's root lock does not yet contain
the optional training packages. Their absence explicitly skips the W3 test module;
a base-CI green result therefore does **not** establish W3 acceptance. W1 must integrate
the requirements and explicit W3 mypy/coverage commands before merge acceptance.
Requirements contain only already-permitted numerical/image libraries and YAML support;
the engine's dependency closure is unchanged. No root configuration is modified.

## Geometry and labels

- uint8 grayscale `(H,W)` or **RGB** `(H,W,3)`. Maximum input pixels is configuration-owned.
- `Labels` is a W3-local training container, **not a versioned Clavis/W2 contract**.
  Points `(N,2)`, xyxy boxes `(N,4)`, arbitrary polylines, uint8/uint16 categorical masks,
  and sampled adjacent staff-line point pairs `(N,2,2)` are explicit inputs.
- Coordinates are integer pixel centers, origin at the top left. Homographies are forward
  input-to-output float64 matrices. Pipeline composition is `H_last @ ... @ H_first`.
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
  caller supplies known synthetic homographies; camera-angle sampling is deferred.

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
Default YAML is a mechanical test distribution, not an adopted ADR-011 preset.
Rendering dimensions and note positions are fixture content, not input-dependent rules.

No real aggregate statistics have been supplied by W4. Realism, 8-family presets,
5 pages/core-second throughput, full G0, W2 integration and low-interline loss routing
are not claimed. Interline below 6 px must be routed separately by callers as the W3
instruction's illegible candidate; this first demo stays above that range. Cross-version
codec byte identity is not promised. Large jobs belong in W1's 01:00–07:00 single queue.
