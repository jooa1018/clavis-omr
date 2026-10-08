# staff

Owner: W5.

CPU staff models.

## Synthetic component smoke (not training)

Run W2's `python -m training.data.smoke work/w2-smoke --renderer-python <python>`
first. Then run `python -m training.models.staff.prepare_smoke --root work/w2-smoke
--output work/geometry-rasters` to prepare the independent symbol-only SVGs.
`raster_smoke.cjs` takes W2 root, raster output directory, and an installed
Sharp module path. Sharp is a development-only SVG rasterizer (as in W2's audit),
never imported by the engine. It selects scores 0–3 and every registered smoke
font before measurement, 12 full-page raster pairs at density 144.

`python -m training.models.staff.smoke --root work/w2-smoke
--rasters work/geometry-rasters --output work/geometry-smoke` applies W3 area
downsampling to 16/10/8 px, then measures all 36 pages including failures. It
produces detection/strip overlays, a contact sheet, metrics and empirical jitter.
Run under a caller-owned 540-second subprocess timeout and OR-001 resource limits.
Do not launch when disk free space is below 3 GB or available RAM is insufficient.
Peak RSS is measured; no training admission or batch-queue replacement is implied.

Ground truth comes from explicit W2 SVG staff paths, resolving the unchanged
ancestor viewport/translation chain, then from W3's pixel-center label transform.
Matching is a diagnostic test oracle, **not a new W4 evaluator**. Results are
synthetic smoke, not SYN-Val, and no paired improvement is claimed.

`prepare_smoke.py` additionally creates staff-removed SVGs by deleting only
explicit direct staff paths, for independent symbol-preservation measurements.
Grayscale staff ink residue and symbol ink damage are measured against these
separate raster pairs after the identical W3 resize and extraction mesh. Five
strip repetitions per matched staff record latency and check identical output
bytes. Measurements are conditional on detection; misses remain in recall.
These diagnostics are not W4's G2 acceptance metrics.
No model, weights, training shard, real data or sealed data is used.
